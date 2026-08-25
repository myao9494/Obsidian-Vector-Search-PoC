"""
FAISS ベクトルインデックス管理モジュール
仕様:
- faiss.IndexFlatIP を用いた内積（L2正規化済みベクトルのコサイン類似度）高速検索。
- SQLiteのドキュメントID / チャンクIDとFAISS内部連番インデックスの双方向マッピング管理。
- インデックスのメモリ保持、ディスク保存 (.faiss) および復元。
- スレッドセーフな検索およびインデックス更新。
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import torch
except ImportError:
    pass

import faiss
import numpy as np


class FaissVectorIndex:
    """
    FAISS を用いた高精度・高速ベクトル検索インデックスクラス
    """
    def __init__(self, dim: int):
        self.dim = dim
        self.lock = threading.Lock()
        self._init_index()

    def _init_index(self):
        """内部FAISSインデックスとIDマッピングを初期化"""
        self.index = faiss.IndexFlatIP(self.dim)
        self.internal_to_id: List[int] = []
        self.id_to_internal: Dict[int, int] = {}

    @property
    def total_count(self) -> int:
        """インデックス内の総ベクトル数"""
        with self.lock:
            return self.index.ntotal

    def clear(self):
        """インデックスを全消去して再初期化"""
        with self.lock:
            self._init_index()

    def add_items(self, ids: List[int], vectors: np.ndarray) -> None:
        """
        IDとベクトルのリストを一括でインデックスに追加する
        
        Args:
            ids: 外部ID（document_id または chunk_id）のリスト
            vectors: shape (N, dim) の L2正規化 float32 配列
        """
        if len(ids) == 0:
            return

        if not isinstance(vectors, np.ndarray) or vectors.dtype != np.float32:
            vectors = np.ascontiguousarray(vectors, dtype=np.float32)

        if len(vectors.shape) == 1:
            vectors = vectors.reshape(1, -1)

        if vectors.shape[1] != self.dim:
            raise ValueError(f"ベクトルの次元数 ({vectors.shape[1]}) がインデックス次元数 ({self.dim}) と一致しません。")

        with self.lock:
            start_internal_idx = self.index.ntotal
            self.index.add(vectors)
            for i, external_id in enumerate(ids):
                internal_idx = start_internal_idx + i
                self.internal_to_id.append(external_id)
                self.id_to_internal[external_id] = internal_idx

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        クエリベクトルでTop-K類似度検索を行う
        
        Args:
            query_vector: shape (dim,) または (1, dim) の L2正規化 float32 ベクトル
            top_k: 取得する上位件数
            
        Returns:
            [{"id": external_id, "score": float}, ...]
        """
        with self.lock:
            if self.index.ntotal == 0:
                return []

            if not isinstance(query_vector, np.ndarray) or query_vector.dtype != np.float32:
                query_vector = np.ascontiguousarray(query_vector, dtype=np.float32)

            if len(query_vector.shape) == 1:
                query_vector = query_vector.reshape(1, -1)

            k = min(top_k, self.index.ntotal)
            scores, indices = self.index.search(query_vector, k)

            results: List[Dict[str, Any]] = []
            for score, internal_idx in zip(scores[0], indices[0]):
                if internal_idx < 0 or internal_idx >= len(self.internal_to_id):
                    continue
                external_id = self.internal_to_id[internal_idx]
                results.append({
                    "id": external_id,
                    "score": float(score)
                })

            return results

    def save(self, file_path: str) -> None:
        """
        インデックスとIDマッピングをファイルに保存する
        """
        save_path = Path(file_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path = save_path.with_suffix(".json")

        with self.lock:
            faiss.write_index(self.index, str(save_path))
            metadata = {
                "dim": self.dim,
                "internal_to_id": self.internal_to_id
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False)

    @classmethod
    def load(cls, file_path: str, dim: int) -> "FaissVectorIndex":
        """
        保存されたファイルからインデックスとIDマッピングを復元する
        """
        save_path = Path(file_path)
        meta_path = save_path.with_suffix(".json")

        if not save_path.exists():
            raise FileNotFoundError(f"FAISSインデックスファイルが存在しません: {file_path}")

        instance = cls(dim=dim)
        instance.index = faiss.read_index(str(save_path))
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                instance.internal_to_id = metadata.get("internal_to_id", [])
                instance.id_to_internal = {
                    ext_id: idx for idx, ext_id in enumerate(instance.internal_to_id)
                }
        return instance
