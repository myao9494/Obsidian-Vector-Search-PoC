"""
FAISS ベクトル検索インデックスのテスト仕様
- faiss.IndexFlatIP を用いたコサイン類似度検索（L2正規化ベクトル対応）
- ベクトルの追加 (add)、削除 (remove)、更新 (update)
- Top-K 類似度検索と ID マッピング（FAISS internal ID -> chunk_id / doc_id）
- インデックスのファイル永続化とロード (.faiss)
- 空インデックスに対する検索時の安全な振る舞い
"""

import os
import tempfile
import numpy as np
import pytest
from app.faiss_index import FaissVectorIndex


def test_faiss_index_basic_search():
    """FAISSインデックスの基本検索動作テスト"""
    dim = 64
    index = FaissVectorIndex(dim=dim)
    assert index.dim == dim
    assert index.total_count == 0

    # 3件のベクトルを作成（ID: 101, 102, 103）
    rng = np.random.RandomState(42)
    v1 = rng.randn(dim).astype(np.float32)
    v1 /= np.linalg.norm(v1)
    
    v2 = rng.randn(dim).astype(np.float32)
    v2 /= np.linalg.norm(v2)

    # v3はv1に極めて近いベクトル
    v3 = v1 + 0.01 * rng.randn(dim).astype(np.float32)
    v3 /= np.linalg.norm(v3)

    index.add_items(ids=[101, 102, 103], vectors=np.vstack([v1, v2, v3]))
    assert index.total_count == 3

    # v1をクエリとして検索 -> 1位: 101 (score ~1.0), 2位: 103
    results = index.search(query_vector=v1, top_k=2)
    assert len(results) == 2
    assert results[0]["id"] == 101
    assert np.isclose(results[0]["score"], 1.0, atol=1e-4)
    assert results[1]["id"] == 103


def test_faiss_index_save_and_load():
    """インデックスの保存とロードテスト"""
    dim = 32
    index = FaissVectorIndex(dim=dim)
    rng = np.random.RandomState(123)
    vectors = rng.randn(10, dim).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ids = list(range(1, 11))
    
    index.add_items(ids=ids, vectors=vectors)

    with tempfile.TemporaryDirectory() as tmpdir:
        index_file = os.path.join(tmpdir, "test.faiss")
        index.save(index_file)
        assert os.path.exists(index_file)

        loaded_index = FaissVectorIndex.load(index_file, dim=dim)
        assert loaded_index.total_count == 10

        # 同じクエリで同一の結果が得られること
        q = vectors[0]
        r1 = index.search(q, top_k=3)
        r2 = loaded_index.search(q, top_k=3)
        assert [x["id"] for x in r1] == [x["id"] for x in r2]
        assert np.allclose([x["score"] for x in r1], [x["score"] for x in r2], atol=1e-5)


def test_faiss_index_empty_query():
    """空のインデックスに対して検索しても例外が発生しないこと"""
    index = FaissVectorIndex(dim=64)
    q = np.random.randn(64).astype(np.float32)
    results = index.search(q, top_k=5)
    assert results == []
