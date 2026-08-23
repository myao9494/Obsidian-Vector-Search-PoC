"""
SQLite Database モジュールのテスト仕様
- <Vault>/.vector_search/index.db へのテーブル作成（documents, chunks）
- ドキュメントの新規登録、更新（Upsert）、削除
- チャンクの登録、親ドキュメント削除時のチャンク連動削除
- Embedding（BLOB）の保存および復元
- DocumentおよびChunkのEmbedding一括取得
- 前後チャンク（文脈）の取得
"""

import os
import numpy as np
import pytest
from app.db import (
    init_db,
    upsert_document,
    insert_chunks,
    delete_document,
    get_document_by_path,
    get_all_documents_metadata,
    get_all_document_embeddings,
    get_all_chunk_embeddings,
    get_chunk_with_context,
    get_db_stats,
)


@pytest.fixture
def db_path(tmp_path):
    """テスト用一時SQLiteデータベースパス"""
    db_file = tmp_path / ".vector_search" / "index.db"
    init_db(str(db_file))
    return str(db_file)


def test_init_db_and_tables(db_path):
    """DB初期化とテーブル作成のテスト"""
    assert os.path.exists(db_path)
    stats = get_db_stats(db_path)
    assert stats["document_count"] == 0
    assert stats["chunk_count"] == 0


def test_upsert_and_get_document(db_path):
    """Documentの追加と取得、Embeddingの保存・復元テスト"""
    doc_embedding = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    doc_id = upsert_document(
        db_path,
        path="Notes/Test.md",
        title="Test Note",
        mtime=1700000000.0,
        size=1024,
        sha256="abc123hash",
        text="# Test Note\nHello world",
        embedding=doc_embedding.tobytes(),
    )
    assert doc_id > 0

    doc = get_document_by_path(db_path, "Notes/Test.md")
    assert doc is not None
    assert doc["title"] == "Test Note"
    assert doc["sha256"] == "abc123hash"
    assert doc["size"] == 1024

    # 復元したEmbeddingの検証
    loaded_vec = np.frombuffer(doc["embedding"], dtype=np.float32)
    assert np.allclose(loaded_vec, doc_embedding)


def test_chunks_and_context(db_path):
    """Chunkの登録と前後文脈（prev / current / next）取得テスト"""
    doc_id = upsert_document(
        db_path,
        path="Doc1.md",
        title="Doc 1",
        mtime=1700000000.0,
        size=500,
        sha256="hash1",
        text="Full text",
        embedding=None,
    )

    c0_vec = np.array([1.0, 0.0], dtype=np.float32)
    c1_vec = np.array([0.0, 1.0], dtype=np.float32)
    c2_vec = np.array([0.5, 0.5], dtype=np.float32)

    chunks_data = [
        (0, "Chunk 0 text content", c0_vec.tobytes(), 2),
        (1, "Chunk 1 text content", c1_vec.tobytes(), 2),
        (2, "Chunk 2 text content", c2_vec.tobytes(), 2),
    ]
    insert_chunks(db_path, doc_id, chunks_data)

    stats = get_db_stats(db_path)
    assert stats["document_count"] == 1
    assert stats["chunk_count"] == 3

    # 全Chunk Embeddingsの取得
    chunk_rows = get_all_chunk_embeddings(db_path)
    assert len(chunk_rows) == 3
    assert chunk_rows[1]["chunk_index"] == 1

    # Chunk 1 のコンテキスト取得（前: Chunk 0, 今: Chunk 1, 次: Chunk 2）
    target_chunk_id = chunk_rows[1]["id"]
    ctx = get_chunk_with_context(db_path, target_chunk_id)
    assert ctx is not None
    assert ctx["current"]["text"] == "Chunk 1 text content"
    assert ctx["prev"]["text"] == "Chunk 0 text content"
    assert ctx["next"]["text"] == "Chunk 2 text content"


def test_delete_document_cascades_chunks(db_path):
    """Document削除時に紐づくChunkも削除されることのテスト"""
    doc_id = upsert_document(
        db_path,
        path="ToDelete.md",
        title="To Delete",
        mtime=1700000000.0,
        size=100,
        sha256="hashdel",
        text="text",
        embedding=None,
    )
    insert_chunks(
        db_path,
        doc_id,
        [(0, "chunk text", np.array([1.0], dtype=np.float32).tobytes(), 1)],
    )

    assert get_db_stats(db_path)["document_count"] == 1
    assert get_db_stats(db_path)["chunk_count"] == 1

    delete_document(db_path, "ToDelete.md")

    assert get_db_stats(db_path)["document_count"] == 0
    assert get_db_stats(db_path)["chunk_count"] == 0
