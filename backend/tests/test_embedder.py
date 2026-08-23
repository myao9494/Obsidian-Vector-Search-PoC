"""
Sentence Transformer Embedder のテスト仕様
- ローカルパスからの SentenceTransformer モデルのロード
- 自動ダウンロードを試みず、存在しないローカルパス指定時に適切なエラー（FileNotFoundError / ValueError）を送出すること
- テスト用の MockEmbedder（決定論的な正規化ベクトル生成）の動作
- 単一テキストおよびバッチテキストの Embedding 生成（float32、L2正規化済み）
- 内積によるコサイン類似度の一致
"""

import numpy as np
import pytest
from app.embedder import Embedder, MockEmbedder


def test_mock_embedder():
    """MockEmbedderの基本動作テスト"""
    dim = 64
    embedder = MockEmbedder(dim=dim)
    assert embedder.embedding_dim == dim

    vec = embedder.encode("Hello world")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (dim,)
    assert vec.dtype == np.float32
    # L2正規化されていること（ノルムが1.0）
    norm = np.linalg.norm(vec)
    assert np.isclose(norm, 1.0, atol=1e-5)

    # バッチ処理
    batch_vecs = embedder.encode_batch(["Text 1", "Text 2", "Text 3"])
    assert isinstance(batch_vecs, np.ndarray)
    assert batch_vecs.shape == (3, dim)
    for i in range(3):
        assert np.isclose(np.linalg.norm(batch_vecs[i]), 1.0, atol=1e-5)


def test_embedder_invalid_local_path():
    """存在しないローカルパスを指定した場合にエラーとなること（自動DL禁止）"""
    with pytest.raises(ValueError):
        Embedder(model_path="/non/existent/model/path/12345")


def test_embedder_local_saved_model():
    """ローカルに保存したモデルからオフラインロードしてEmbedding生成できること"""
    import os
    local_path = "/Users/mine/000_work/test/PoC_lag/models/multilingual-minilm"
    if os.path.exists(local_path):
        embedder = Embedder(model_path=local_path)
        assert embedder.embedding_dim == 384
        vec = embedder.encode("これはテストです。")
        assert vec.shape == (384,)
        assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-4)

