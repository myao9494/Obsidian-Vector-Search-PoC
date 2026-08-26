"""
FastAPI メインサーバーモジュール
仕様:
- ポート 60000 で起動する REST API サーバー。
- React フロントエンド（ポート 60001）からのアクセスを許可する CORS 設定。
- ネイティブダイアログ起動、モデルロード、インデックス実行（進捗管理）、DB統計取得、ベクトル検索の各APIを提供。
"""

import asyncio
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import get_db_stats
from app.dialog import open_folder_dialog
from app.dictionary import GlossaryDictionary
from app.embedder import BaseEmbedder, Embedder, MockEmbedder
from app.indexer import IndexManager, IndexProgress, IndexResult
from app.searcher import SearchMode, VectorSearcher


class AppState:
    """サーバーのグローバル状態管理"""
    def __init__(self):
        self.vault_path: Optional[str] = None
        self.model_path: Optional[str] = None
        self.is_mock_model: bool = False
        self.embedder: Optional[BaseEmbedder] = None
        self.is_indexing: bool = False
        self.current_progress: Optional[IndexProgress] = None
        self.last_index_result: Optional[IndexResult] = None
        self.lock = threading.Lock()


state = AppState()
app = FastAPI(title="Obsidian Vector Search PoC API")

# CORS設定（ポート 60001 等からの通信を許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:60001", "http://localhost:60001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === リクエスト / レスポンスモデル ===
class DialogRequest(BaseModel):
    title: Optional[str] = "フォルダを選択してください"


class DialogResponse(BaseModel):
    selected_path: Optional[str]


class ModelLoadRequest(BaseModel):
    model_path: str
    use_mock: bool = False


class ModelLoadResponse(BaseModel):
    loaded: bool
    model_path: str
    dim: int
    is_mock: bool


class IndexStartRequest(BaseModel):
    vault_path: str
    chunk_size: int = 600
    chunk_overlap: int = 80
    force_reindex: bool = False
    target_extensions: Optional[List[str]] = None


class SearchRequest(BaseModel):
    vault_path: str
    query: str
    mode: str = "chunk"  # "document" or "chunk"
    top_k: int = 20
    min_score: float = 0.0
    keyword_boost: bool = True
    boost_weight: float = 0.08


# === エンドポイント ===
@app.get("/api/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "app": "Obsidian Vector Search PoC"}


@app.post("/api/dialog/select-folder", response_model=DialogResponse)
def select_folder(req: DialogRequest):
    """OSネイティブフォルダ選択ダイアログを表示しパスを取得"""
    path = open_folder_dialog(title=req.title or "フォルダを選択してください")
    return DialogResponse(selected_path=path)


@app.post("/api/model/load", response_model=ModelLoadResponse)
def load_model(req: ModelLoadRequest):
    """ローカルSentenceTransformerモデル（またはMockモデル）をロード"""
    with state.lock:
        if req.use_mock or req.model_path.lower() in ("mock", "test", "dummy"):
            state.embedder = MockEmbedder(dim=384)
            state.model_path = "mock"
            state.is_mock_model = True
        else:
            if not os.path.exists(req.model_path):
                raise HTTPException(status_code=400, detail=f"指定されたモデルパスが存在しません: {req.model_path}")
            try:
                state.embedder = Embedder(model_path=req.model_path)
                state.model_path = req.model_path
                state.is_mock_model = False
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"モデルのロードに失敗しました: {str(e)}")

        return ModelLoadResponse(
            loaded=True,
            model_path=state.model_path or "",
            dim=state.embedder.embedding_dim,
            is_mock=state.is_mock_model,
        )


@app.get("/api/model/status")
def get_model_status():
    """現在のモデルロード状況を取得"""
    with state.lock:
        return {
            "loaded": state.embedder is not None,
            "model_path": state.model_path,
            "is_mock": state.is_mock_model,
            "dim": state.embedder.embedding_dim if state.embedder else None,
        }


@app.post("/api/index/start")
def start_index(req: IndexStartRequest, background_tasks: BackgroundTasks = None):
    """インデックス処理の開始"""
    if not os.path.exists(req.vault_path):
        raise HTTPException(status_code=400, detail=f"Vaultパスが存在しません: {req.vault_path}")

    with state.lock:
        if state.embedder is None:
            raise HTTPException(status_code=400, detail="モデルがロードされていません。先にモデルをロードしてください。")
        if state.is_indexing:
            raise HTTPException(status_code=409, detail="既にインデックス処理が実行中です。")

    state.vault_path = req.vault_path

    manager = IndexManager(vault_path=req.vault_path, embedder=state.embedder)
    
    def on_progress(p: IndexProgress):
        state.current_progress = p

    res = manager.run_index(
        progress_callback=on_progress,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
        force_reindex=req.force_reindex,
        target_extensions=req.target_extensions,
    )
    state.last_index_result = res
    return asdict(res)


@app.get("/api/index/progress")
def get_index_progress():
    """インデックス進捗の取得"""
    return {
        "is_indexing": state.is_indexing,
        "progress": asdict(state.current_progress) if state.current_progress else None,
        "last_result": asdict(state.last_index_result) if state.last_index_result else None,
    }


@app.get("/api/index/stats")
def get_stats(vault_path: str):
    """VaultのSQLite DB統計を取得"""
    db_path = os.path.join(vault_path, ".vector_search", "index.db")
    stats = get_db_stats(db_path)
    return stats


@app.post("/api/search")
def search(req: SearchRequest):
    """ベクトル検索の実行"""
    if not os.path.exists(req.vault_path):
        raise HTTPException(status_code=400, detail=f"Vaultパスが存在しません: {req.vault_path}")

    db_path = os.path.join(req.vault_path, ".vector_search", "index.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=400, detail="インデックスが存在しません。先にインデックスを作成してください。")

    if state.embedder is None:
        raise HTTPException(status_code=400, detail="モデルがロードされていません。")

    mode = SearchMode.DOCUMENT if req.mode.lower() == "document" else SearchMode.CHUNK
    searcher = VectorSearcher(db_path=db_path, embedder=state.embedder)
    
    try:
        response = searcher.search(
            query=req.query,
            mode=mode,
            top_k=req.top_k,
            min_score=req.min_score,
            keyword_boost=req.keyword_boost,
            boost_weight=req.boost_weight,
        )
        return asdict(response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"検索処理中にエラーが発生しました: {str(e)}")

@app.get("/api/dictionary/status")
def get_dictionary_status(vault_path: str):
    """Vault内の専門用語・類似語辞書（.xlsx / .csv）の読み込み状況を取得"""
    if not os.path.exists(vault_path):
        return {"loaded": False, "total_entries": 0, "file_name": None, "terms": []}

    vault_dir = Path(vault_path).resolve()
    candidates = [
        "glossary.xlsx", "dictionary.xlsx", "synonyms.xlsx",
        "glossary.csv", "dictionary.csv", "synonyms.csv",
        "用語集.xlsx", "用語集.csv"
    ]
    target_file = None
    for c in candidates:
        p = vault_dir / c
        if p.exists():
            target_file = str(p)
            break

    if not target_file:
        return {"loaded": False, "total_entries": 0, "file_name": None, "terms": []}

    try:
        glossary = GlossaryDictionary.from_file(target_file)
        sample_terms = [
            {"term": e.term, "synonyms": e.synonyms, "description": e.description}
            for e in glossary.entries[:10]
        ]
        return {
            "loaded": True,
            "total_entries": len(glossary.entries),
            "file_name": Path(target_file).name,
            "file_path": target_file,
            "terms": sample_terms,
        }
    except Exception as e:
        return {"loaded": False, "error": str(e), "total_entries": 0, "file_name": Path(target_file).name}


# === 静的配信マウント (会社環境などNode.jsが無い環境用) ===
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # assetsなどの静的ファイルをマウント
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))
