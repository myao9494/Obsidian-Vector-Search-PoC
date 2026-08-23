"""
SQLite データベース管理モジュール
仕様:
- <Vault>/.vector_search/index.db の作成およびテーブル定義（documents, chunks）を管理する。
- ドキュメント情報およびチャンク情報の永続化、更新、削除を高速に行う。
- Embedding（BLOB）の格納とメモリロードをサポートする。
- チャンクIDから同一文書内の直前（prev）および直後（next）のチャンクを含む文脈情報を取得する。
- DBファイルサイズ、登録件数等の統計情報を集計する。
"""

import os
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
