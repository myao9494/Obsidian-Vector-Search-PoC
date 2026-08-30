"""
Embedding 生成モジュール
仕様:
- ローカルパスに配置された Sentence Transformers モデル（ruri-v3-310m, E5, SimCSE等）からEmbeddingを生成する。
- 実行時のモデル自動ダウンロードは禁止し、指定パスが存在しない場合は即座に例外を発生させる。
- デバイス自動選択: Mac（Apple Silicon）環境では MPS (Metal GPU)、Windows/CPU環境では CPU（CUDA検知時はCUDA）を自動設定。
- プロンプト/プレフィックス制御:
  - ruri系モデル (ruri-v3): クエリには「検索クエリ: 」、文書には「検索文書: 」を付与。
  - e5系モデル: クエリには「query: 」、文書には「passage: 」を付与。
- 全てのEmbeddingベクトルはL2正規化（float32）されたNumPy配列として返却され、FAISS / 内積計算のみでコサイン類似度が得られる。
- テスト・オフライン動作用の MockEmbedder を提供する。
"""

import hashlib
import os
import sys
from pathlib import Path
from typing import List, Optional, Union
import numpy as np


def auto_detect_device() -> str:
    """
    実行環境の最適なPyTorchデバイス（MPS/CUDA/CPU）を自動検出する
    - Mac (Apple Silicon): torch.backends.mps.is_available() -> "mps"
    - NVIDIA GPU: torch.cuda.is_available() -> "cuda"
    - Windows / 一般CPU: "cpu"
    """
    try:
        import torch
        if sys.platform == "darwin" and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


class BaseEmbedder:
    """Embedderの基底抽象インターフェース"""
    model_path: Optional[str] = None

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
    def __init__(self, dim: int = 768, model_path: Optional[str] = None):
        self._dim = dim
        self.model_path = model_path

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
    ruri-v3 / E5 などのプレフィックス仕様に自動対応し、MPS/CPUでの高速推論を実行する。
    """
    def __init__(self, model_path: str, device: Optional[str] = None):
        resolved_path = Path(model_path).resolve()
        if not resolved_path.exists() or not resolved_path.is_dir():
            raise ValueError(f"指定されたローカルモデルパスが存在しないかディレクトリではありません: {model_path}")

        self.model_path = str(resolved_path)
        self.model_path_str = str(resolved_path)
        path_lower = self.model_path_str.lower()
        self.is_ruri = "ruri" in path_lower
        self.is_e5 = "e5" in path_lower


        if device is None or device == "auto":
            self.device = auto_detect_device()
        else:
            self.device = device

        from sentence_transformers import SentenceTransformer
        
        # ローカルファイルのみからロード（自動ダウンロード禁止）
        try:
            self.model = SentenceTransformer(
                self.model_path_str,
                device=self.device,
                local_files_only=True
            )
        except TypeError:
            self.model = SentenceTransformer(self.model_path_str, device=self.device)

        if hasattr(self.model, "get_embedding_dimension"):
            self._dim = self.model.get_embedding_dimension()
        else:
            self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def _prepare_text(self, text: str, is_query: bool) -> str:
        """
        モデル種別（ruri / e5）に応じたプレフィックスを付与する
        """
        if self.is_ruri:
            # ruri-v3: 検索クエリ: / 検索文書:
            prefix = "検索クエリ: " if is_query else "検索文書: "
            if text.startswith("検索クエリ: ") or text.startswith("検索文書: "):
                return text
            return f"{prefix}{text}"
        
        if self.is_e5:
            # e5: query: / passage:
            prefix = "query: " if is_query else "passage: "
            if text.startswith("query: ") or text.startswith("passage: "):
                return text
            return f"{prefix}{text}"

        return text

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
