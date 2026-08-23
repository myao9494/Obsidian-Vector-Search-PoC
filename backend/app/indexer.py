"""
インデックス管理モジュール
仕様:
- Vault全体の走査、差分検出（新規・変更・変更なしスキップ・削除）、Chunk分割、Embedding生成、SQLiteへの一括登録を統括する。
- 差分判定は path, mtime, size, sha256 を比較して行い、無駄な再Embeddingを防止する。
- 処理中の進捗状況（処理数/全件数、パーセンテージ、経過時間、推定残り時間）をリアルタイムにコールバック通知する。
- インデックス完了時に詳細な統計情報（新規/更新/スキップ/削除数、チャンク数、Embedding所要時間、DBサイズ等）を集計・返却する。
"""

import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.chunker import chunk_markdown
from app.db import (
    clear_all_data,
    delete_document,
    get_all_documents_metadata,
    get_db_embedding_dim,
    get_db_stats,
    init_db,
    insert_chunks,
    upsert_document,
)
from app.embedder import BaseEmbedder
from app.scanner import DocumentMetadata, scan_vault


@dataclass
class IndexProgress:
    """インデックス進捗情報"""
    processed_files: int
    total_files: int
    progress_pct: float
    current_file: str
    elapsed_sec: float
    estimated_remaining_sec: float


@dataclass
class IndexResult:
    """インデックス完了結果サマリー"""
    total_files: int
    new_count: int
    updated_count: int
    skipped_count: int
    deleted_count: int
    document_count: int
    chunk_count: int
    indexing_time_sec: float
    embedding_time_sec: float
    db_size_mb: float


class IndexManager:
    """Vaultのインデックス作成・差分更新・進捗管理を行うマネージャークラス"""

    def __init__(self, vault_path: str, embedder: BaseEmbedder):
        self.vault_path = Path(vault_path).resolve()
        self.embedder = embedder
        self.db_dir = self.vault_path / ".vector_search"
        self.db_path = str(self.db_dir / "index.db")
        init_db(self.db_path)

    def run_index(
        self,
        progress_callback: Optional[Callable[[IndexProgress], None]] = None,
        chunk_size: int = 600,
        chunk_overlap: int = 80,
        force_reindex: bool = False,
    ) -> IndexResult:
        """
        インデックス処理（初回または差分、強制再構築）を実行する。
        """
        start_time = time.time()
        embedding_time_accum = 0.0

        # モデルの次元数チェック（既存DBの次元と現在のEmbedderの次元が異なる場合は全件クリアして再作成）
        existing_dim = get_db_embedding_dim(self.db_path)
        if existing_dim is not None and existing_dim != self.embedder.embedding_dim:
            force_reindex = True

        if force_reindex:
            clear_all_data(self.db_path)

        # 1. 現在のVault内ファイルをスキャン
        current_docs = scan_vault(str(self.vault_path))
        current_map: Dict[str, DocumentMetadata] = {
            doc.relative_path: doc for doc in current_docs
        }

        # 2. DB内の既存ファイルメタデータを取得
        existing_meta = get_all_documents_metadata(self.db_path)

        # 3. 差分判定
        current_paths = set(current_map.keys())
        existing_paths = set(existing_meta.keys())

        # 削除されたファイル
        deleted_paths = existing_paths - current_paths
        for del_p in deleted_paths:
            delete_document(self.db_path, del_p)
        deleted_count = len(deleted_paths)

        # 新規、更新、スキップの分類
        to_process: List[Tuple[str, DocumentMetadata, str]] = []  # (action, doc, rel_path)
        skipped_count = 0

        for rel_p, doc in current_map.items():
            if rel_p not in existing_meta:
                to_process.append(("new", doc, rel_p))
            else:
                db_doc = existing_meta[rel_p]
                # sha256ハッシュが異なる場合のみ更新対象
                if db_doc["sha256"] != doc.sha256:
                    to_process.append(("updated", doc, rel_p))
                else:
                    skipped_count += 1

        total_files = len(current_docs)
        processed_files = skipped_count
        new_count = 0
        updated_count = 0

        # 初期進捗通知
        if progress_callback and total_files > 0:
            elapsed = time.time() - start_time
            pct = round((processed_files / total_files) * 100, 1)
            progress_callback(
                IndexProgress(
                    processed_files=processed_files,
                    total_files=total_files,
                    progress_pct=pct,
                    current_file="Starting...",
                    elapsed_sec=round(elapsed, 2),
                    estimated_remaining_sec=0.0,
                )
            )

        # 4. 新規・更新ファイルのEmbeddingおよび保存
        process_start_time = time.time()
        for idx, (action, doc, rel_p) in enumerate(to_process, start=1):
            file_start = time.time()
            if action == "new":
                new_count += 1
            else:
                updated_count += 1

            # チャンク分割
            chunks = chunk_markdown(
                doc.text, chunk_size=chunk_size, overlap=chunk_overlap
            )

            # Embedding生成
            t_emb_0 = time.time()
            # ① Document Embedding (先頭部分から作成)
            doc_embedding_vec = self.embedder.encode(doc.text[:2000] if doc.text else "", is_query=False)
            doc_embedding_blob = doc_embedding_vec.tobytes()

            # ② Chunk Embedding (バッチ作成)
            chunk_records = []
            if chunks:
                chunk_texts = [c.text for c in chunks]
                chunk_vecs = self.embedder.encode_batch(chunk_texts, is_query=False)
                for c, v in zip(chunks, chunk_vecs):
                    chunk_records.append(
                        (c.chunk_index, c.text, v.tobytes(), self.embedder.embedding_dim)
                    )
            t_emb_1 = time.time()
            embedding_time_accum += (t_emb_1 - t_emb_0)

            # SQLiteへ保存
            doc_id = upsert_document(
                db_path=self.db_path,
                path=doc.relative_path,
                title=doc.title,
                mtime=doc.mtime,
                size=doc.size,
                sha256=doc.sha256,
                text=doc.text,
                embedding=doc_embedding_blob,
            )
            insert_chunks(self.db_path, doc_id, chunk_records)

            processed_files += 1

            # 進捗通知
            if progress_callback:
                now = time.time()
                elapsed = now - start_time
                pct = round((processed_files / total_files) * 100, 1) if total_files > 0 else 100.0
                
                # 残り推定時間計算
                num_done = idx
                num_remain = len(to_process) - num_done
                avg_time_per_file = (now - process_start_time) / num_done if num_done > 0 else 0
                est_remain = avg_time_per_file * num_remain

                progress_callback(
                    IndexProgress(
                        processed_files=processed_files,
                        total_files=total_files,
                        progress_pct=pct,
                        current_file=rel_p,
                        elapsed_sec=round(elapsed, 2),
                        estimated_remaining_sec=round(est_remain, 2),
                    )
                )

        total_time = time.time() - start_time
        stats = get_db_stats(self.db_path)

        return IndexResult(
            total_files=total_files,
            new_count=new_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            deleted_count=deleted_count,
            document_count=stats["document_count"],
            chunk_count=stats["chunk_count"],
            indexing_time_sec=round(total_time, 3),
            embedding_time_sec=round(embedding_time_accum, 3),
            db_size_mb=stats["db_size_mb"],
        )
