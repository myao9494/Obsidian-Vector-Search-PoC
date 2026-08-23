"""
Embedding 生成モジュール
仕様:
- ローカルパスに配置された Sentence Transformers モデルからEmbeddingを生成する。
- 実行時のモデル自動ダウンロードは禁止し、指定パスが存在しない場合は即座に例外を発生させる。
- 全てのEmbeddingベクトルはL2正規化（float32）されたNumPy配列として返却され、内積計算のみでコサイン類似度が得られる。
- テスト・オフライン動作用の MockEmbedder を提供する。
"""

import hashlib
import os
from pathlib import Path
from typing import List, Optional, Union
import numpy as np


class BaseEmbedder:
    """Embedderの基底抽象インターフェース"""
    @property
    def embedding_dim(self) -> int:
        raise NotImplementedError

    def encode(self, text: str, is_query: bool = False) -> np.ndarray:
        raise NotImplementedError

    def encode_batch(self, texts: List[str], is_query: bool = False, batch_size: int = 32) -> np.ndarray:
        raise NotImplementedError


class MockEmbedder(BaseEmbedder):
    """
    テスト・PoC初期検証用の決定論的モックEmbedder
    文字列のハッシュ値から一定次元の正規化乱数ベクトルを生成する。
    """
    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def _generate_vector(self, text: str) -> np.ndarray:
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self._dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def encode(self, text: str, is_query: bool = False) -> np.ndarray:
        return self._generate_vector(text)

    def encode_batch(self, texts: List[str], is_query: bool = False, batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        return np.vstack([self._generate_vector(t) for t in texts])


class Embedder(BaseEmbedder):
    """
    Sentence Transformers をローカルディレクトリからロードするEmbedder
    E5系モデルの場合は自動で query: / passage: プレフィックスを付与する。
    """
    def __init__(self, model_path: str, device: str = "cpu"):
        resolved_path = Path(model_path).resolve()
        if not resolved_path.exists() or not resolved_path.is_dir():
            raise ValueError(f"指定されたローカルモデルパスが存在しないかディレクトリではありません: {model_path}")

        self.model_path_str = str(resolved_path)
        self.is_e5 = "e5" in self.model_path_str.lower()

        from sentence_transformers import SentenceTransformer
        
        # ローカルファイルのみからロード（自動ダウンロード禁止）
        try:
            self.model = SentenceTransformer(
                self.model_path_str,
                device=device,
                local_files_only=True
            )
        except TypeError:
            # 古い/新しいバージョンの互換性対応
            self.model = SentenceTransformer(self.model_path_str, device=device)

        if hasattr(self.model, "get_embedding_dimension"):
            self._dim = self.model.get_embedding_dimension()
        else:
            self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def _prepare_text(self, text: str, is_query: bool) -> str:
        if not self.is_e5:
            return text
        prefix = "query: " if is_query else "passage: "
        if text.startswith("query: ") or text.startswith("passage: "):
            return text
        return f"{prefix}{text}"

    def encode(self, text: str, is_query: bool = False) -> np.ndarray:
        formatted = self._prepare_text(text, is_query)
        vec = self.model.encode(
            formatted,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return vec.astype(np.float32)

    def encode_batch(self, texts: List[str], is_query: bool = False, batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        formatted_texts = [self._prepare_text(t, is_query) for t in texts]
        vecs = self.model.encode(
            formatted_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return vecs.astype(np.float32)
