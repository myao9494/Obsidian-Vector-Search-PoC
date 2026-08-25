"""
FAISS 高速ベクトル検索モジュール
仕様:
- FAISS (faiss.IndexFlatIP) を用いた高速・高精度コサイン類似度検索。
- Document検索モード: 1 Markdown = 1 Embedding による文書単位の類似度検索と上位Top Kの返却。本文プレビューを付与。
- Chunk検索モード: チャンク単位の類似度検索と上位Top Kの返却。ヒット文章および前後文脈（前/ヒット/後）を取得して付与。
- 日本語形態素キーワードブースト (Lexical/Hybrid Boost) による表記揺れ・固有名詞スコア加算。
- 反応文特定 (Salient Sentence Extraction) による最もクエリに合致した根拠文の抽出。
- 検索処理性能の分離計測（Query Embedding生成時間、FAISS類似度計算時間、合計時間）。
"""

import enum
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from app.db import (
    get_all_chunk_embeddings,
    get_all_document_embeddings,
    get_chunk_with_context,
    get_document_by_id,
)
from app.embedder import BaseEmbedder
from app.faiss_index import FaissVectorIndex


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
    クエリ文字列から助詞や記号を除いた重要キーワードリストを抽出する。
    漢字ブロック、カタカナブロック、英数単語の文字種境界や助詞で自然文を分解する。
    """
    stop_words = {
        "について", "に関する", "の基礎", "とは", "概要", "詳細", "まとめ", "方法",
        "どう", "なに", "なぜ", "これ", "それ", "あれ", "どこ", "だれ", "ので",
        "から", "たい", "です", "ます", "ある", "いる", "する", "こと", "もの"
    }

    # 1. 記号や空白で大まかに分割
    coarse_tokens = re.split(r"[\s\.,、。!?！？\-_/()（）「」『』【】]+", query)
    
    keywords_set = set()
    for token in coarse_tokens:
        t = token.strip()
        if not t:
            continue
        
        # 2. 漢字の連続、カタカナの連続、英単語の連続を抽出
        chunks = re.findall(r"[\u4e00-\u9fff]+|[\u30a0-\u30ff]{2,}|[a-zA-Z0-9]{2,}|[\u3040-\u309f]{2,}", t)
        for chunk in chunks:
            c = chunk.strip()
            # 助詞・活用語尾の簡易トリミング
            c = re.sub(r"^(?:ので|から|より|など|へと|には|では|への|での)", "", c)
            c = re.sub(r"(?:について|に関する|なので|でした|ました|したい|たい|です|ます|ので|から|ない|れた|った|いた)$", "", c)
            if len(c) >= 2 and c not in stop_words:
                keywords_set.add(c)

    return sorted(list(keywords_set), key=lambda x: -len(x))


def strip_markdown_to_plain(text: str) -> str:
    """Markdown記法（リンク、画像、装飾、テーブル枠）を自然言語プレーンテキストに変換する"""
    # [テキスト](URL) -> テキスト
    t = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # ![[画像/埋め込み]] -> 空白
    t = re.sub(r"!\[\[[^\]]+\]\]", "", t)
    # [[ノート名|表示名]] -> 表示名 / [[ノート名]] -> ノート名
    t = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", t)
    # URLの除去 (http://... や https://...)
    t = re.sub(r"https?://[^\s\)\>]+", "", t)
    # テーブル枠線やセル区切り |
    t = re.sub(r"\|", " ", t)
    # 見出し記号 #
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    # リスト記号 -, *, 1.
    t = re.sub(r"^[\s\t]*[-\*\+]\s+|^[\s\t]*\d+\.\s+", "", t, flags=re.MULTILINE)
    # 太字、斜体、インラインコード
    t = re.sub(r"[\*_`~]", "", t)
    # 連続する空白を1つにまとめる
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def is_natural_sentence(s: str) -> bool:
    """文が意味のある自然言語文であるか判定する"""
    if not s or len(s) < 8:
        return False

    jp_chars = re.findall(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]", s)
    if jp_chars:
        jp_ratio = len(jp_chars) / len(s)
        hiragana = re.findall(r"[\u3040-\u309f]", s)
        kanji = re.findall(r"[\u4e00-\u9fff]", s)
        if len(hiragana) == 0 and len(kanji) == 0:
            return False
        if jp_ratio < 0.25:
            return False

    return True


def find_salient_sentence(
    text: str,
    query_vec: np.ndarray,
    embedder: BaseEmbedder,
    min_sentence_score: float = 0.65,
) -> Optional[str]:
    """
    チャンクテキストの中から、クエリベクトルと最も類似度の高い「反応文（核となる一文）」を特定する。
    """
    if not text:
        return None

    plain_text = strip_markdown_to_plain(text)
    if not plain_text:
        return None

    raw_sentences = re.split(r"(?:\n+|(?<=[。！？\.\?!]))", plain_text)
    valid_sentences = []

    for raw_s in raw_sentences:
        s = raw_s.strip()
        cleaned_s = re.sub(r"^[\s#\-*|>|`\(\)\[\]]+|[\s#\-*|>|`\(\)\[\]]+$", "", s).strip()
        
        if len(cleaned_s) < 8:
            continue

        natural_chars = re.findall(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\w]", cleaned_s)
        if len(natural_chars) < 6:
            continue

        if re.search(r"\.(?:jp|com|net|html|php|aspx|ipynb|excalidraw)", cleaned_s, re.IGNORECASE):
            continue

        if not is_natural_sentence(cleaned_s):
            continue

        valid_sentences.append(cleaned_s)

    if not valid_sentences:
        return None

    try:
        s_vecs = embedder.encode_batch(valid_sentences, is_query=False)
        scores = s_vecs @ query_vec
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        
        if best_score < min_sentence_score:
            return None
        return valid_sentences[best_idx]
    except Exception:
        return None


class VectorSearcher:
    """FAISSによる高速オフラインベクトル検索エンジン（キーワードブースト & スコア調整 & 反応文特定機能付き）"""

    def __init__(self, db_path: str, embedder: BaseEmbedder):
        self.db_path = db_path
        self.embedder = embedder
        self._doc_faiss_index: Optional[FaissVectorIndex] = None
        self._chunk_faiss_index: Optional[FaissVectorIndex] = None
        self._doc_rows_cache: Optional[Dict[int, Dict[str, Any]]] = None
        self._chunk_rows_cache: Optional[Dict[int, Dict[str, Any]]] = None

    def _ensure_faiss_indexes(self, mode: SearchMode):
        """FAISSインデックスをロードまたはSQLiteから構築"""
        dim = self.embedder.embedding_dim

        if mode == SearchMode.DOCUMENT:
            if self._doc_faiss_index is None or self._doc_faiss_index.dim != dim:
                doc_rows = get_all_document_embeddings(self.db_path)
                index = FaissVectorIndex(dim=dim)
                self._doc_rows_cache = {}
                if doc_rows:
                    ids = []
                    vectors = []
                    for r in doc_rows:
                        vec = np.frombuffer(r["embedding"], dtype=np.float32)
                        if vec.shape[0] == dim:
                            ids.append(r["id"])
                            vectors.append(vec)
                            self._doc_rows_cache[r["id"]] = dict(r)
                    if ids:
                        index.add_items(ids=ids, vectors=np.vstack(vectors))
                self._doc_faiss_index = index

        elif mode == SearchMode.CHUNK:
            if self._chunk_faiss_index is None or self._chunk_faiss_index.dim != dim:
                chunk_rows = get_all_chunk_embeddings(self.db_path)
                index = FaissVectorIndex(dim=dim)
                self._chunk_rows_cache = {}
                if chunk_rows:
                    ids = []
                    vectors = []
                    for r in chunk_rows:
                        vec = np.frombuffer(r["embedding"], dtype=np.float32)
                        if vec.shape[0] == dim:
                            ids.append(r["id"])
                            vectors.append(vec)
                            self._chunk_rows_cache[r["id"]] = dict(r)
                    if ids:
                        index.add_items(ids=ids, vectors=np.vstack(vectors))
                self._chunk_faiss_index = index

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
        指定されたクエリでFAISSベクトル検索を実行する。
        """
        t_total_start = time.perf_counter()

        # 1. クエリのEmbedding生成
        t_emb_start = time.perf_counter()
        query_vec = self.embedder.encode(query, is_query=True)
        t_emb_end = time.perf_counter()
        query_emb_time_ms = round((t_emb_end - t_emb_start) * 1000, 2)

        # 2. FAISS インデックスの確保 & 検索
        t_sim_start = time.perf_counter()
        self._ensure_faiss_indexes(mode)

        faiss_idx = self._doc_faiss_index if mode == SearchMode.DOCUMENT else self._chunk_faiss_index
        total_candidates = faiss_idx.total_count if faiss_idx else 0

        results: List[SearchResultItem] = []
        keywords = extract_query_keywords(query) if keyword_boost else []

        if faiss_idx and total_candidates > 0:
            # 余裕を持ったTop-K件を取得し、キーワードブースト等を適用
            fetch_k = min(top_k * 3, total_candidates)
            raw_hits = faiss_idx.search(query_vec, top_k=fetch_k)

            if mode == SearchMode.DOCUMENT:
                for hit in raw_hits:
                    doc_id = hit["id"]
                    sim = hit["score"]
                    row = self._doc_rows_cache.get(doc_id)
                    if not row:
                        continue

                    # キーワードブースト
                    boosted_score = float(sim)
                    if keyword_boost and keywords:
                        title_lower = (row["title"] or "").lower()
                        text_lower = (row["text"] or "").lower()
                        match_count = 0
                        for kw in keywords:
                            kw_l = kw.lower()
                            if kw_l in title_lower or kw_l in text_lower:
                                match_count += 1
                        if match_count > 0:
                            boost_factor = 1.0 + (boost_weight * min(match_count, 3))
                            boosted_score = min(float(sim) * boost_factor, 1.0)

                    if min_score > 0.0 and boosted_score < min_score:
                        continue

                    preview_text = (row["text"] or "")[:200]
                    if len(row["text"] or "") > 200:
                        preview_text += "..."

                    results.append(
                        SearchResultItem(
                            document_id=row["id"],
                            path=row["path"],
                            title=row["title"] or Path(row["path"]).name,
                            score=round(boosted_score, 4),
                            preview=preview_text,
                        )
                    )

            elif mode == SearchMode.CHUNK:
                for hit in raw_hits:
                    chunk_id = hit["id"]
                    sim = hit["score"]
                    row = self._chunk_rows_cache.get(chunk_id)
                    if not row:
                        continue

                    boosted_score = float(sim)
                    chunk_text = row["text"] or ""

                    # キーワードブースト
                    if keyword_boost and keywords:
                        text_lower = chunk_text.lower()
                        path_lower = (row.get("path") or "").lower()
                        match_count = 0
                        for kw in keywords:
                            kw_l = kw.lower()
                            if kw_l in text_lower or kw_l in path_lower:
                                match_count += 1
                        if match_count > 0:
                            boost_factor = 1.0 + (boost_weight * min(match_count, 3))
                            boosted_score = min(float(sim) * boost_factor, 1.0)

                    if min_score > 0.0 and boosted_score < min_score:
                        continue

                    # 文脈情報取得
                    ctx = get_chunk_with_context(self.db_path, chunk_id=chunk_id)
                    
                    # 反応文の特定（レスポンス高速化のため上位3件のみに適用）
                    salient = None
                    if len(results) < 3:
                        salient = find_salient_sentence(
                            text=chunk_text,
                            query_vec=query_vec,
                            embedder=self.embedder,
                            min_sentence_score=0.60,
                        )

                    results.append(
                        SearchResultItem(
                            document_id=row["document_id"],
                            path=row["path"],
                            title=row["title"] or Path(row["path"]).name,
                            score=round(boosted_score, 4),
                            chunk_id=chunk_id,
                            chunk_index=row["chunk_index"],
                            hit_text=chunk_text,
                            context=ctx,
                            salient_sentence=salient,
                        )
                    )

            # スコア降順にソートして top_k 件に制限
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[:top_k]

        t_sim_end = time.perf_counter()
        search_time_ms = round((t_sim_end - t_sim_start) * 1000, 2)
        total_time_ms = round((t_sim_end - t_total_start) * 1000, 2)

        return SearchResponse(
            query=query,
            mode=mode,
            results=results,
            total_candidates=total_candidates,
            query_embedding_time_ms=query_emb_time_ms,
            search_time_ms=search_time_ms,
            total_time_ms=total_time_ms,
        )
