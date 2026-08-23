"""
ベクトル検索モジュール
仕様:
- NumPy を用いた Cosine Similarity 全件比較（scores = Matrix @ query_vector）を実行する。
- Document検索モード: 1 Markdown = 1 Embedding による文書単位の類似度検索と上位Top Kの返却。本文プレビューを付与。
- Chunk検索モード: チャンク単位の類似度検索と上位Top Kの返却。ヒット文章および前後文脈（前/ヒット/後）を取得して付与。
- 検索処理性能の分離計測（Query Embedding生成時間、類似度計算・ソート時間、合計時間）を行う。
"""

import enum
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np

from app.db import (
    get_all_chunk_embeddings,
    get_all_document_embeddings,
    get_chunk_with_context,
)
from app.embedder import BaseEmbedder


class SearchMode(str, enum.Enum):
    DOCUMENT = "document"
    CHUNK = "chunk"


@dataclass
class SearchResultItem:
    """検索結果の1件分のデータ"""
    document_id: int
    path: str
    title: str
    score: float
    chunk_id: Optional[int] = None
    chunk_index: Optional[int] = None
    hit_text: Optional[str] = None
    preview: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    salient_sentence: Optional[str] = None


@dataclass
class SearchResponse:
    """検索レスポンス"""
    query: str
    mode: SearchMode
    results: List[SearchResultItem]
    total_candidates: int
    query_embedding_time_ms: float
    search_time_ms: float
    total_time_ms: float


def extract_query_keywords(query: str) -> List[str]:
    """
    クエリ文字列から助詞や記号を除いた重要キーワードリスト（2文字以上）を抽出する
    """
    import re
    # 記号や空白で分割
    tokens = re.split(r"[\s\.,、。!?！？\-_/()（）「」『』【】]+", query)
    stop_words = {"について", "に関する", "の基礎", "とは", "概要", "詳細", "まとめ", "方法", "どう", "なに", "なぜ", "これ", "それ"}
    
    keywords = []
    for t in tokens:
        t_clean = t.strip()
        if len(t_clean) >= 2 and t_clean not in stop_words:
            keywords.append(t_clean)
    return keywords


def find_salient_sentence(
    text: str,
    query_vec: np.ndarray,
    embedder: BaseEmbedder
) -> Optional[str]:
    """
    チャンクテキストを文（Sentences）に分割し、クエリベクトルに最も強く反応（類似）した文を特定する
    """
    import re
    if not text:
        return None
    # 句点、改行、箇条書きなどで文分割
    raw_sentences = re.split(r"(?:\n+|(?<=[。！？\.\?!]))", text)
    sentences = [
        s.strip()
        for s in raw_sentences
        if len(s.strip()) >= 10 and not re.match(r"^[-*#>\s]+$", s.strip())
    ]
    if not sentences:
        return None
    if len(sentences) == 1:
        return sentences[0]

    try:
        s_vecs = embedder.encode_batch(sentences, is_query=False)
        scores = s_vecs @ query_vec
        best_idx = int(np.argmax(scores))
        return sentences[best_idx]
    except Exception:
        return sentences[0]


class VectorSearcher:
    """NumPyによるオフラインベクトル検索エンジン（キーワードブースト & スコア調整 & 反応文特定機能付き）"""

    def __init__(self, db_path: str, embedder: BaseEmbedder):
        self.db_path = db_path
        self.embedder = embedder

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.CHUNK,
        top_k: int = 20,
        min_score: float = 0.0,
        keyword_boost: bool = True,
        boost_weight: float = 0.08,
    ) -> SearchResponse:
        """
        指定されたクエリでベクトル検索を実行する。
        """
        t_total_start = time.perf_counter()

        # 1. クエリのEmbedding生成と時間計測
        t_emb_start = time.perf_counter()
        query_vec = self.embedder.encode(query, is_query=True)
        t_emb_end = time.perf_counter()
        query_emb_time_ms = round((t_emb_end - t_emb_start) * 1000, 2)

        # 2. 検索対象のEmbedding行列の準備
        t_sim_start = time.perf_counter()
        results: List[SearchResultItem] = []
        total_candidates = 0

        keywords = extract_query_keywords(query) if keyword_boost else []

        if mode == SearchMode.DOCUMENT:
            doc_rows = get_all_document_embeddings(self.db_path)
            total_candidates = len(doc_rows)

            if total_candidates > 0:
                emb_list = [
                    np.frombuffer(r["embedding"], dtype=np.float32) for r in doc_rows
                ]
                
                # 次元数チェック
                if emb_list[0].shape[0] != query_vec.shape[0]:
                    raise ValueError(
                        f"インデックスのベクトル次元数 ({emb_list[0].shape[0]}d) と現在のモデルの次元数 ({query_vec.shape[0]}d) が異なります。Index Vault を実行して再インデックスしてください。"
                    )

                matrix = np.vstack(emb_list)  # (N, D)
                scores = matrix @ query_vec  # (N,)

                # キーワード一致ブースト
                if keywords:
                    for i, row in enumerate(doc_rows):
                        full_content = f"{row['title'] or ''} {row['path']} {row['text'] or ''}"
                        match_count = sum(1 for kw in keywords if kw in full_content)
                        if match_count > 0:
                            scores[i] += boost_weight * min(match_count, 3)

                # 閾値フィルタおよびTop K 抽出
                valid_indices = np.where(scores >= min_score)[0]
                if len(valid_indices) > 0:
                    sorted_indices = valid_indices[np.argsort(scores[valid_indices])[::-1][:top_k]]

                    for idx in sorted_indices:
                        row = doc_rows[idx]
                        score_val = float(scores[idx])
                        raw_text = row["text"] or ""
                        preview_text = (
                            raw_text[:300] + "..." if len(raw_text) > 300 else raw_text
                        )

                        salient_s = find_salient_sentence(raw_text[:800], query_vec, self.embedder)

                        results.append(
                            SearchResultItem(
                                document_id=row["id"],
                                path=row["path"],
                                title=row["title"] or row["path"],
                                score=round(score_val, 4),
                                preview=preview_text,
                                salient_sentence=salient_s,
                            )
                        )

        elif mode == SearchMode.CHUNK:
            chunk_rows = get_all_chunk_embeddings(self.db_path)
            total_candidates = len(chunk_rows)

            if total_candidates > 0:
                emb_list = [
                    np.frombuffer(r["embedding"], dtype=np.float32) for r in chunk_rows
                ]

                # 次元数チェック
                if emb_list[0].shape[0] != query_vec.shape[0]:
                    raise ValueError(
                        f"インデックスのベクトル次元数 ({emb_list[0].shape[0]}d) と現在のモデルの次元数 ({query_vec.shape[0]}d) が異なります。Index Vault を実行して再インデックスしてください。"
                    )

                matrix = np.vstack(emb_list)
                scores = matrix @ query_vec

                # キーワード一致ブースト
                if keywords:
                    for i, row in enumerate(chunk_rows):
                        chunk_content = f"{row['title'] or ''} {row['path']} {row['text']}"
                        match_count = sum(1 for kw in keywords if kw in chunk_content)
                        if match_count > 0:
                            scores[i] += boost_weight * min(match_count, 3)

                valid_indices = np.where(scores >= min_score)[0]
                if len(valid_indices) > 0:
                    sorted_indices = valid_indices[np.argsort(scores[valid_indices])[::-1][:top_k]]

                    for idx in sorted_indices:
                        row = chunk_rows[idx]
                        score_val = float(scores[idx])
                        chunk_id = row["id"]
                        chunk_text = row["text"]

                        # 前後文脈の取得
                        context_info = get_chunk_with_context(self.db_path, chunk_id)

                        # 最も反応した一文の特定
                        salient_s = find_salient_sentence(chunk_text, query_vec, self.embedder)

                        results.append(
                            SearchResultItem(
                                document_id=row["document_id"],
                                path=row["path"],
                                title=row["title"] or row["path"],
                                score=round(score_val, 4),
                                chunk_id=chunk_id,
                                chunk_index=row["chunk_index"],
                                hit_text=chunk_text,
                                context=context_info,
                                salient_sentence=salient_s,
                            )
                        )

        t_sim_end = time.perf_counter()
        sim_calc_time_ms = round((t_sim_end - t_sim_start) * 1000, 2)
        total_time_ms = round((t_sim_end - t_total_start) * 1000, 2)

        return SearchResponse(
            query=query,
            mode=mode,
            results=results,
            total_candidates=total_candidates,
            query_embedding_time_ms=query_emb_time_ms,
            search_time_ms=sim_calc_time_ms,
            total_time_ms=total_time_ms,
        )
