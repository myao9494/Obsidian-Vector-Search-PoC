"""
Sentence Transformer Embedder のテスト仕様
- ローカルパスからの SentenceTransformer モデルのロード
- 自動ダウンロードを試みず、存在しないローカルパス指定時に適切なエラー（ValueError）を送出すること
- ruri-v3 プレフィックス付与（「検索クエリ: 」「検索文書: 」）の自動処理
- テスト用の MockEmbedder（決定論的な正規化ベクトル生成）の動作
- 単一テキストおよびバッチテキストの Embedding 生成（float32、L2正規化済み）
- デバイス自動判定（auto_detect_device）
"""

import os
import numpy as np
import pytest
from app.embedder import Embedder, MockEmbedder, auto_detect_device


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


def test_auto_detect_device():
    """デバイス自動検出のテスト"""
    device = auto_detect_device()
    assert device in ("mps", "cuda", "cpu")


def test_embedder_invalid_local_path():
    """存在しないローカルパスを指定した場合にエラーとなること（自動DL禁止）"""
    with pytest.raises(ValueError):
        Embedder(model_path="/non/existent/model/path/12345")


def test_embedder_ruri_model_loading_and_inference():
    """ローカルに保存した ruri-v3-310m モデルからロードしてプレフィックス付与 & 推論できること"""
    local_path = "/Users/mine/000_work/test/PoC_lag/models/ruri-v3-310m"
    if os.path.exists(local_path):
        embedder = Embedder(model_path=local_path, device="auto")
        assert embedder.is_ruri is True
        assert embedder.embedding_dim == 768

        # プレフィックスの自動付与確認
        assert embedder._prepare_text("確定申告", is_query=True) == "検索クエリ: 確定申告"
        assert embedder._prepare_text("確定申告のメモ", is_query=False) == "検索文書: 確定申告のメモ"
        # 既存プレフィックスがある場合の二重付与防止
        assert embedder._prepare_text("検索クエリ: 確定申告", is_query=True) == "検索クエリ: 確定申告"

        # 推論
        vec = embedder.encode("これはテストです。", is_query=True)
        assert vec.shape == (768,)
        assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-4)
