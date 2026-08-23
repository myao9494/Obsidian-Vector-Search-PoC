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
    クエリ文字列から助詞や記号を除いた重要キーワードリストを抽出する。
    スペース区切りだけでなく、漢字ブロック、カタカナブロック、英数単語の文字種境界や助詞で自然文を分解する。
    """
    import re
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
    import re
    # [テキスト](URL) -> テキスト
    t = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # ![[画像/埋め込み]] -> 空白
    t = re.sub(r"!\[\[[^\]]+\]\]", "", t)
    # URLの除去 (http://... や https://...)
    t = re.sub(r"https?://[^\s\)\>]+", "", t)
    # テーブル枠線やセル区切り |
    t = re.sub(r"\|", " ", t)
    # 見出し記号 # や箇条書き記号 - *
    t = re.sub(r"^[#\-*>]+\s*", "", t, flags=re.MULTILINE)
    # 装飾記号 ` * _
    t = re.sub(r"[`*_~]+", "", t)
    # 連続空白の圧縮
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def is_natural_sentence(s: str) -> bool:
    """文が意味のある自然言語文かどうかを判定する（メタデータ行、打鍵ミス、タイムスタンプを排除）"""
    import re
    lower = s.lower()
    
    # 1. メタデータプレフィックスの除外
    metadata_keys = ("created:", "updated:", "tags:", "aliases:", "date:", "id:", "pw:", "sha256:")
    if any(lower.startswith(k) for k in metadata_keys):
        return False
    
    # 2. 日時・タイムスタンプのみの行を除外 (例: "2026-01-11 05:32:23", "1 時間 32 分 34 秒")
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{1,2}(?::\d{1,2})?)?$", s):
        return False
    if re.match(r"^(?:\d+\s*(?:時間|分|秒)\s*)+$", s):
        return False

    # 3. 打鍵ミス・意味不明な子音連続の除外 (例: "mthk", "thm", "asdf" 等の母音なし英字ブロック)
    # 英字が含まれる場合、母音（a, i, u, e, o）のない3文字以上の子音連続は除外
    for word in re.findall(r"[a-zA-Z]{3,}", s):
        if not re.search(r"[aiueoAIUEO]", word):
            return False

    # 4. セミコロンや記号が不自然に混ざった文字列の除外 (例: "あmthk;ま;thm")
    if re.search(r"[;\/\\_]{2,}|[a-zA-Z]+;[a-zA-Z]+", s):
        return False

    return True


def find_salient_sentence(
    text: str,
    query_vec: np.ndarray,
    embedder: BaseEmbedder,
    min_sentence_score: float = 0.78
) -> Optional[str]:
    """
    チャンクテキストを文（Sentences）に分割し、クエリベクトルに最も強く反応（類似）した文を特定する。
    Markdown記法、メタデータ行、打鍵ミス行を除去し、スコアがしきい値（min_sentence_score）以上の文のみを抽出する。
    """
    import re
    if not text:
        return None

    # 1. プレーンテキスト化
    plain_text = strip_markdown_to_plain(text)
    if not plain_text:
        return None

    # 2. 句点、改行、句読点で文分割
    raw_sentences = re.split(r"(?:\n+|(?<=[。！？\.\?!]))", plain_text)
    valid_sentences = []

    for raw_s in raw_sentences:
        s = raw_s.strip()
        # 記号除去
        cleaned_s = re.sub(r"^[\s#\-*|>|`\(\)\[\]]+|[\s#\-*|>|`\(\)\[\]]+$", "", s).strip()
        
        # 最小長チェック
        if len(cleaned_s) < 8:
            continue

        # 自然言語文字（日本語・英数字）が最低6文字以上
        natural_chars = re.findall(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\w]", cleaned_s)
        if len(natural_chars) < 6:
            continue

        # URLやパスの残骸を除外
        if re.search(r"\.(?:jp|com|net|html|php|aspx|ipynb|excalidraw)", cleaned_s, re.IGNORECASE):
            continue

        # 自然言語妥当性チェック（メタデータ行、打鍵ミス行の排除）
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
        
        # しきい値チェック: クエリと真に関連した文章でない場合は None を返却
        if best_score < min_sentence_score:
            return None
        return valid_sentences[best_idx]
    except Exception:
        return None


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
