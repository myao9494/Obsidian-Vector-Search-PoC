"""
SQLite データベース管理モジュール
仕様:
- <Vault>/.vector_search/index_<model_name>.db の作成およびテーブル定義（documents, chunks）をモデル別に独立管理する。
- ドキュメント情報およびチャンク情報の永続化、更新、削除を高速に行う。
- Embedding（BLOB）の格納とメモリロードをサポートする。
- チャンクIDから同一文書内の直前（prev）および直後（next）のチャンクを含む文脈情報を取得する。
- DBファイルサイズ、登録件数等の統計情報をモデル別に集計する。
- モデル識別子の抽出（get_model_identifier）およびモデル別DBパスの解決（get_model_db_path）を提供する。
"""

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple



def get_db_connection(db_path: str) -> sqlite3.Connection:
    """SQLiteコネクションを取得し、行を辞書形式で取得できるように設定する"""
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: str) -> None:
    """テーブルおよびインデックスを初期化する"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # documents テーブル
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            title TEXT,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            text TEXT,
            embedding BLOB,
            indexed_at REAL
        );
        """)

        # chunks テーブル
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            embedding_dim INTEGER NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        """)

        # インデックス
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_document
        ON chunks(document_id);
        """)
        
        conn.commit()


def get_document_by_path(db_path: str, path: str) -> Optional[Dict[str, Any]]:
    """パスでドキュメントを検索して辞書形式で返す"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE path = ?", (path,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_document_by_id(db_path: str, doc_id: int) -> Optional[Dict[str, Any]]:
    """IDでドキュメントを検索して辞書形式で返す"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_documents_metadata(db_path: str) -> Dict[str, Dict[str, Any]]:
    """
    差分比較用に全ドキュメントのメタデータ（path, mtime, size, sha256）を辞書で返す
    キー: path
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, path, mtime, size, sha256 FROM documents")
        rows = cursor.fetchall()
        return {row["path"]: dict(row) for row in rows}


def upsert_document(
    db_path: str,
    path: str,
    title: str,
    mtime: float,
    size: int,
    sha256: str,
    text: str,
    embedding: Optional[bytes] = None,
) -> int:
    """
    ドキュメントを追加または更新（Upsert）し、document_id を返す。
    更新時は既存のチャンクを削除する。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        now = time.time()
        
        cursor.execute("""
        INSERT INTO documents (path, title, mtime, size, sha256, text, embedding, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            title=excluded.title,
            mtime=excluded.mtime,
            size=excluded.size,
            sha256=excluded.sha256,
            text=excluded.text,
            embedding=excluded.embedding,
            indexed_at=excluded.indexed_at
        RETURNING id;
        """, (path, title, mtime, size, sha256, text, embedding, now))
        
        doc_id = cursor.fetchone()[0]
        
        # 既存チャンクをクリア
        cursor.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        conn.commit()
        return doc_id


def insert_chunks(
    db_path: str,
    document_id: int,
    chunks: List[Tuple[int, str, bytes, int]],
) -> None:
    """
    チャンクリストを一括登録する。
    chunks要素: (chunk_index, text, embedding_blob, embedding_dim)
    """
    if not chunks:
        return

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany("""
        INSERT INTO chunks (document_id, chunk_index, text, embedding, embedding_dim)
        VALUES (?, ?, ?, ?, ?)
        """, [(document_id, c[0], c[1], c[2], c[3]) for c in chunks])
        conn.commit()


def delete_document(db_path: str, path: str) -> bool:
    """指定パスのドキュメント（および紐づくチャンク）を削除する"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE path = ?", (path,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def get_all_document_embeddings(db_path: str) -> List[Dict[str, Any]]:
    """全ドキュメントのEmbeddingおよび基本情報を取得する"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, path, title, text, embedding
        FROM documents
        WHERE embedding IS NOT NULL
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_all_chunk_embeddings(db_path: str) -> List[Dict[str, Any]]:
    """全チャンクのEmbeddingおよび紐づくドキュメント情報を取得する"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            c.id,
            c.document_id,
            c.chunk_index,
            c.text,
            c.embedding,
            c.embedding_dim,
            d.path,
            d.title
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_chunk_with_context(db_path: str, chunk_id: int) -> Optional[Dict[str, Any]]:
    """
    指定チャンクとその直前（prev）および直後（next）のチャンク情報を取得する。
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT c.id, c.document_id, c.chunk_index, c.text, d.path, d.title
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.id = ?
        """, (chunk_id,))
        row = cursor.fetchone()
        if not row:
            return None

        current = dict(row)
        doc_id = current["document_id"]
        c_idx = current["chunk_index"]

        # prev
        cursor.execute("""
        SELECT id, chunk_index, text FROM chunks
        WHERE document_id = ? AND chunk_index = ?
        """, (doc_id, c_idx - 1))
        prev_row = cursor.fetchone()
        prev_chunk = dict(prev_row) if prev_row else None

        # next
        cursor.execute("""
        SELECT id, chunk_index, text FROM chunks
        WHERE document_id = ? AND chunk_index = ?
        """, (doc_id, c_idx + 1))
        next_row = cursor.fetchone()
        next_chunk = dict(next_row) if next_row else None

        return {
            "current": current,
            "prev": prev_chunk,
            "next": next_chunk,
        }


def get_db_stats(db_path: str) -> Dict[str, Any]:
    """データベースの統計情報（ドキュメント数、チャンク数、DBサイズ）を取得する"""
    if not os.path.exists(db_path):
        return {
            "document_count": 0,
            "chunk_count": 0,
            "db_size_bytes": 0,
            "db_size_mb": 0.0,
        }

    file_size = os.path.getsize(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]

        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "db_size_bytes": file_size,
            "db_size_mb": round(file_size / (1024 * 1024), 2),
        }


def get_db_embedding_dim(db_path: str) -> Optional[int]:
    """DB内に保存されているチャンクのembedding_dimを取得する"""
    if not os.path.exists(db_path):
        return None
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT embedding_dim FROM chunks LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None


def clear_all_data(db_path: str) -> None:
    """DB内のすべてのドキュメントおよびチャンクを削除する"""
    if not os.path.exists(db_path):
        return
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunks")
        cursor.execute("DELETE FROM documents")
        conn.commit()


def sanitize_model_name(name: str) -> str:
    """ファイル名として安全なモデル名に正規化・サニタイズする"""
    if not name:
        return "default"
    # 末尾スラッシュやパスセパレータを取り除いてファイル/フォルダ名を取得
    base_name = Path(name.rstrip("/\\")).name
    if not base_name:
        base_name = name.strip("/\\")
    # 使用禁止文字をアンダースコアに置換
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base_name)
    sanitized = re.sub(r"_+", "_", sanitized).strip("._")
    return sanitized or "default"


def get_model_identifier(
    model_path: Optional[str] = None,
    embedder: Optional[Any] = None
) -> str:
    """
    モデルパスまたはEmbedderインスタンスから識別子文字列を生成する。
    例: "ruri-v3-310m", "ruri-v3-30m", "mock"
    """
    if embedder is not None:
        if hasattr(embedder, "model_path") and embedder.model_path:
            return sanitize_model_name(str(embedder.model_path))
        embedder_cls_name = embedder.__class__.__name__.lower()
        if "mock" in embedder_cls_name:
            dim = getattr(embedder, "embedding_dim", 384)
            return f"mock_{dim}"
        return sanitize_model_name(embedder_cls_name)

    if model_path:
        if model_path.lower() in ("mock", "test", "dummy"):
            return "mock"
        return sanitize_model_name(model_path)

    return "default"


def get_model_db_path(
    vault_path: str,
    model_path: Optional[str] = None,
    embedder: Optional[Any] = None
) -> str:
    """
    Vaultパスとモデル情報から、該当モデル専用のSQLite DBパスを解決する。
    例: <vault_path>/.vector_search/index_ruri-v3-310m.db
    """
    model_id = get_model_identifier(model_path=model_path, embedder=embedder)
    vault_dir = Path(vault_path).resolve()
    db_dir = vault_dir / ".vector_search"
    db_dir.mkdir(parents=True, exist_ok=True)
    target_db = db_dir / f"index_{model_id}.db"

    # レガシー index.db の自動移行（もし index_<model_id>.db が無く、次元数が一致する index.db がある場合）
    if not target_db.exists():
        legacy_db = db_dir / "index.db"
        if legacy_db.exists():
            legacy_dim = get_db_embedding_dim(str(legacy_db))
            expected_dim = getattr(embedder, "embedding_dim", None) if embedder else None
            if expected_dim is None:
                if "310m" in model_id:
                    expected_dim = 768
                elif "30m" in model_id:
                    expected_dim = 256

            if legacy_dim is not None and expected_dim is not None and legacy_dim == expected_dim:
                try:
                    # 安全にリネーム移行
                    legacy_db.rename(target_db)
                    for ext in ["-shm", "-wal"]:
                        shm_wal = db_dir / f"index.db{ext}"
                        if shm_wal.exists():
                            shm_wal.rename(db_dir / f"index_{model_id}.db{ext}")
                except Exception:
                    return str(legacy_db)

    return str(target_db)


def get_all_vault_models_stats(vault_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Vault内の .vector_search ディレクトリにある全モデルのDB統計情報を集計する。
    返却形式:
    {
        "ruri-v3-310m": {"document_count": 100, "chunk_count": 500, "db_size_mb": 3.2, "db_path": "..."},
        "ruri-v3-30m": {"document_count": 100, "chunk_count": 500, "db_size_mb": 1.1, "db_path": "..."}
    }
    """
    stats_map: Dict[str, Dict[str, Any]] = {}
    vault_dir = Path(vault_path).resolve()
    db_dir = vault_dir / ".vector_search"
    if not db_dir.exists():
        return stats_map


    for db_file in db_dir.glob("*.db"):
        file_name = db_file.name
        # index_<model>.db または index.db
        if file_name.startswith("index_") and file_name.endswith(".db"):
            model_key = file_name[len("index_"):-len(".db")]
        elif file_name == "index.db":
            # 次元の自動判定
            dim = get_db_embedding_dim(str(db_file))
            if dim == 256:
                model_key = "ruri-v3-30m"
            elif dim == 768:
                model_key = "ruri-v3-310m"
            else:
                model_key = f"legacy_dim_{dim}" if dim else "legacy_default"
        else:
            continue

        db_stat = get_db_stats(str(db_file))
        db_stat["db_path"] = str(db_file)
        db_stat["embedding_dim"] = get_db_embedding_dim(str(db_file))
        stats_map[model_key] = db_stat

    return stats_map


