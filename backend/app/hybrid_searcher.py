"""
ハイブリッド検索エンジンモジュール (HybridSearcher)
仕様:
- ベクトル検索 (VectorSearcher: FAISS + ruri-v3) と キーワード検索 (Local-fulltext-search API) を統合。
- RRF (Reciprocal Rank Fusion) および Weighted Score Fusion による高精度リランキング。
- キーワードAPIへの並行/安全通信および自動フォールバック（APIダウン時もベクトル検索単体で応答）。
- 抽出キーワードによる OR クエリ（例: `A OR B`）をキーワード検索APIへ自動連携。
- 統合結果からの RAG コンテキスト (XML / Markdown) 生成。
"""

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.searcher import SearchMode, SearchResponse, SearchResultItem, VectorSearcher, generate_rag_contexts

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResultItem:
    """ハイブリッド検索結果の1件分のデータ"""
    document_id: Optional[int]
    path: str
    title: str
    full_path: str
    hybrid_score: float
    match_type: Literal["both", "vector_only", "keyword_only"]
    vector_rank: Optional[int] = None
    vector_score: Optional[float] = None
    keyword_rank: Optional[int] = None
    keyword_score: Optional[float] = None
    chunk_id: Optional[int] = None
    chunk_index: Optional[int] = None
    hit_text: Optional[str] = None
    preview: Optional[str] = None
    snippet: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    salient_sentence: Optional[str] = None


@dataclass
class HybridSearchResponse:
    """ハイブリッド検索レスポンス"""
    query: str
    mode: str
    hybrid_results: List[HybridSearchResultItem]
    vector_results: List[Dict[str, Any]]
    keyword_results: List[Dict[str, Any]]
    extracted_keywords: List[str]
    keyword_query: str
    fusion_method: str
    vector_weight: float
    keyword_weight: float
    metrics: Dict[str, float]
    keyword_api_status: Dict[str, Any]
    rag_context_xml: str = ""
    rag_context_markdown: str = ""
    detected_terms: List[Dict[str, Any]] = field(default_factory=list)


def normalize_path_key(path_str: str) -> str:
    """パスの比較用キー（小文字化・区切り文字統一）を生成"""
    if not path_str:
        return ""
    p = Path(path_str).as_posix().lower()
    return p


def reciprocal_rank_fusion(
    vector_items: List[SearchResultItem],
    keyword_items: List[Dict[str, Any]],
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
    k: int = 60,
) -> List[HybridSearchResultItem]:
    """
    RRF (Reciprocal Rank Fusion) アルゴリズムにより、ベクトル検索とキーワード検索の結果を順位ベースで融合する。
    Score(d) = w_v / (k + rank_v) + w_k / (k + rank_k)
    """
    # パスキーによるドキュメントマップ
    doc_map: Dict[str, Dict[str, Any]] = {}

    # 1. ベクトル検索結果の登録
    for rank, item in enumerate(vector_items, start=1):
        key = normalize_path_key(item.full_path or item.path)
        if not key:
            continue
        doc_map[key] = {
            "path": item.path,
            "title": item.title,
            "full_path": item.full_path or item.path,
            "document_id": item.document_id,
            "chunk_id": item.chunk_id,
            "chunk_index": item.chunk_index,
            "hit_text": item.hit_text,
            "preview": item.preview,
            "context": item.context,
            "salient_sentence": item.salient_sentence,
            "snippet": None,
            "vector_rank": rank,
            "vector_score": item.score,
            "keyword_rank": None,
            "keyword_score": None,
        }

    # 2. キーワード検索結果の登録 & マージ
    for rank, item in enumerate(keyword_items, start=1):
        full_p = item.get("full_path") or ""
        target_root = item.get("target_path") or ""
        key = normalize_path_key(full_p or target_root)
        if not key:
            continue

        kw_score = float(item.get("utility_score", 0.0) or item.get("click_count", 0.0) or 1.0)
        snippet = item.get("snippet") or ""

        if key in doc_map:
            doc_map[key]["keyword_rank"] = rank
            doc_map[key]["keyword_score"] = kw_score
            if not doc_map[key]["snippet"]:
                doc_map[key]["snippet"] = snippet
        else:
            file_name = item.get("file_name") or Path(full_p).name
            # 相対パスの算出
            rel_path = full_p
            if target_root and full_p.startswith(target_root):
                rel_path = full_p[len(target_root):].lstrip("/\\")

            doc_map[key] = {
                "path": rel_path or full_p,
                "title": file_name,
                "full_path": full_p,
                "document_id": item.get("file_id"),
                "chunk_id": None,
                "chunk_index": None,
                "hit_text": None,
                "preview": snippet,
                "context": None,
                "salient_sentence": None,
                "snippet": snippet,
                "vector_rank": None,
                "vector_score": None,
                "keyword_rank": rank,
                "keyword_score": kw_score,
            }

    # 3. RRF スコアの計算
    results: List[HybridSearchResultItem] = []
    for info in doc_map.values():
        v_rank = info["vector_rank"]
        k_rank = info["keyword_rank"]

        score = 0.0
        if v_rank is not None and vector_weight > 0:
            score += vector_weight * (1.0 / (k + v_rank))
        if k_rank is not None and keyword_weight > 0:
            score += keyword_weight * (1.0 / (k + k_rank))

        if v_rank is not None and k_rank is not None:
            match_type = "both"
        elif v_rank is not None:
            match_type = "vector_only"
        else:
            match_type = "keyword_only"

        results.append(
            HybridSearchResultItem(
                document_id=info["document_id"],
                path=info["path"],
                title=info["title"],
                full_path=info["full_path"],
                hybrid_score=round(score, 6),
                match_type=match_type,
                vector_rank=v_rank,
                vector_score=info["vector_score"],
                keyword_rank=k_rank,
                keyword_score=info["keyword_score"],
                chunk_id=info["chunk_id"],
                chunk_index=info["chunk_index"],
                hit_text=info["hit_text"],
                preview=info["preview"],
                snippet=info["snippet"],
                context=info["context"],
                salient_sentence=info["salient_sentence"],
            )
        )

    # 4. スコア降順にソート
    results.sort(key=lambda x: x.hybrid_score, reverse=True)
    return results


def weighted_score_fusion(
    vector_items: List[SearchResultItem],
    keyword_items: List[Dict[str, Any]],
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
) -> List[HybridSearchResultItem]:
    """
    スコア正規化合成 (Weighted Score Fusion) アルゴリズム。
    ベクトルスコア (0.0〜1.0) とキーワードスコア（0.0〜1.0正規化）を重み付け加算する。
    """
    doc_map: Dict[str, Dict[str, Any]] = {}

    # キーワードの最大スコアを求めて正規化基準とする
    max_kw_score = 1.0
    for item in keyword_items:
        s = float(item.get("utility_score", 0.0) or 1.0)
        if s > max_kw_score:
            max_kw_score = s

    for rank, item in enumerate(vector_items, start=1):
        key = normalize_path_key(item.full_path or item.path)
        if not key:
            continue
        doc_map[key] = {
            "path": item.path,
            "title": item.title,
            "full_path": item.full_path or item.path,
            "document_id": item.document_id,
            "chunk_id": item.chunk_id,
            "chunk_index": item.chunk_index,
            "hit_text": item.hit_text,
            "preview": item.preview,
            "context": item.context,
            "salient_sentence": item.salient_sentence,
            "snippet": None,
            "vector_rank": rank,
            "vector_score": item.score,
            "keyword_rank": None,
            "keyword_score": None,
        }

    for rank, item in enumerate(keyword_items, start=1):
        full_p = item.get("full_path") or ""
        target_root = item.get("target_path") or ""
        key = normalize_path_key(full_p or target_root)
        if not key:
            continue

        kw_score = float(item.get("utility_score", 0.0) or item.get("click_count", 0.0) or 1.0)
        snippet = item.get("snippet") or ""

        if key in doc_map:
            doc_map[key]["keyword_rank"] = rank
            doc_map[key]["keyword_score"] = kw_score
            if not doc_map[key]["snippet"]:
                doc_map[key]["snippet"] = snippet
        else:
            file_name = item.get("file_name") or Path(full_p).name
            rel_path = full_p
            if target_root and full_p.startswith(target_root):
                rel_path = full_p[len(target_root):].lstrip("/\\")

            doc_map[key] = {
                "path": rel_path or full_p,
                "title": file_name,
                "full_path": full_p,
                "document_id": item.get("file_id"),
                "chunk_id": None,
                "chunk_index": None,
                "hit_text": None,
                "preview": snippet,
                "context": None,
                "salient_sentence": None,
                "snippet": snippet,
                "vector_rank": None,
                "vector_score": None,
                "keyword_rank": rank,
                "keyword_score": kw_score,
            }

    results: List[HybridSearchResultItem] = []
    for info in doc_map.values():
        v_score = info["vector_score"] or 0.0
        k_raw = info["keyword_score"] or 0.0
        k_score = k_raw / max_kw_score if max_kw_score > 0 else 0.0

        score = (vector_weight * v_score) + (keyword_weight * k_score)

        if info["vector_rank"] is not None and info["keyword_rank"] is not None:
            match_type = "both"
        elif info["vector_rank"] is not None:
            match_type = "vector_only"
        else:
            match_type = "keyword_only"

        results.append(
            HybridSearchResultItem(
                document_id=info["document_id"],
                path=info["path"],
                title=info["title"],
                full_path=info["full_path"],
                hybrid_score=round(score, 4),
                match_type=match_type,
                vector_rank=info["vector_rank"],
                vector_score=info["vector_score"],
                keyword_rank=info["keyword_rank"],
                keyword_score=info["keyword_score"],
                chunk_id=info["chunk_id"],
                chunk_index=info["chunk_index"],
                hit_text=info["hit_text"],
                preview=info["preview"],
                snippet=info["snippet"],
                context=info["context"],
                salient_sentence=info["salient_sentence"],
            )
        )

    results.sort(key=lambda x: x.hybrid_score, reverse=True)
    return results


class HybridSearcher:
    """
    ベクトル検索とキーワード検索APIを統合するハイブリッド検索サービス
    """

    def __init__(
        self,
        vector_searcher: VectorSearcher,
        keyword_api_url: str = "http://127.0.0.1:8079",
    ):
        self.vector_searcher = vector_searcher
        self.keyword_api_url = (keyword_api_url or "http://127.0.0.1:8079").rstrip("/")

    def check_keyword_api_status(self) -> Dict[str, Any]:
        """キーワード検索APIの稼働状態（ヘルスチェック）を確認"""
        health_url = f"{self.keyword_api_url}/api/health"
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "Obsidian-Hybrid-Search-PoC"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return {"connected": True, "url": self.keyword_api_url, "message": "正常に接続中"}
        except Exception as e:
            return {"connected": False, "url": self.keyword_api_url, "message": f"接続エラー: {str(e)}"}
        return {"connected": False, "url": self.keyword_api_url, "message": "応答なし"}

    def _call_keyword_search_api(
        self,
        query: str,
        vault_path: str,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], float, Dict[str, Any]]:
        """キーワード検索API（/api/search）を呼び出す"""
        t_start = time.perf_counter()
        search_endpoint = f"{self.keyword_api_url}/api/search"
        payload = {
            "q": query,
            "full_path": vault_path,
            "limit": limit,
            "search_all_enabled": False,
            "source_type": "local",
            "search_target": "all",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                search_endpoint,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "Obsidian-Hybrid-Search-PoC"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                resp_body = resp.read().decode("utf-8")
                data = json.loads(resp_body)
                items = data.get("items", [])
                t_end = time.perf_counter()
                time_ms = round((t_end - t_start) * 1000, 2)
                return items, time_ms, {"connected": True, "url": self.keyword_api_url, "message": f"{len(items)}件ヒット"}
        except Exception as e:
            t_end = time.perf_counter()
            time_ms = round((t_end - t_start) * 1000, 2)
            logger.warning(f"Keyword search API call failed: {e}")
            return [], time_ms, {"connected": False, "url": self.keyword_api_url, "message": f"キーワードAPI通信エラー: {str(e)}"}

    def search(
        self,
        query: str,
        vault_path: str,
        mode: str = "chunk",
        top_k: int = 20,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        fusion_method: str = "rrf",
        rrf_k: int = 60,
        keyword_query_override: Optional[str] = None,
    ) -> HybridSearchResponse:
        """
        ハイブリッド検索の実行
        1. ベクトル検索を実行
        2. キーワード検索APIを実行（抽出キーワードORクエリまたは通常クエリ）
        3. 融合アルゴリズム（RRF / Weighted）を適用
        4. RAGコンテキスト生成 & レスポンス構築
        """
        t_total_start = time.perf_counter()

        # 1. ベクトル検索実行
        search_mode = SearchMode.DOCUMENT if mode.lower() == "document" else SearchMode.CHUNK
        v_res: SearchResponse = self.vector_searcher.search(
            query=query,
            mode=search_mode,
            top_k=top_k * 2,
            keyword_boost=True,
        )

        vector_items = v_res.results
        extracted_kws = v_res.extracted_keywords
        kw_query = keyword_query_override or v_res.keyword_query or query

        # 2. キーワード検索API呼び出し
        kw_items, kw_time_ms, kw_status = self._call_keyword_search_api(
            query=kw_query,
            vault_path=vault_path,
            limit=top_k * 2,
        )

        # 3. 融合処理
        t_fusion_start = time.perf_counter()
        if fusion_method.lower() == "weighted":
            fused_items = weighted_score_fusion(
                vector_items=vector_items,
                keyword_items=kw_items,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
        else:
            fused_items = reciprocal_rank_fusion(
                vector_items=vector_items,
                keyword_items=kw_items,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
                k=rrf_k,
            )

        fused_items = fused_items[:top_k]
        t_fusion_end = time.perf_counter()
        fusion_time_ms = round((t_fusion_end - t_fusion_start) * 1000, 2)
        total_time_ms = round((t_fusion_end - t_total_start) * 1000, 2)

        # 4. RAGコンテキスト生成
        temp_search_items = [
            SearchResultItem(
                document_id=item.document_id or 0,
                path=item.path,
                title=item.title,
                score=item.hybrid_score,
                full_path=item.full_path,
                hit_text=item.hit_text or item.snippet or item.preview or "",
            )
            for item in fused_items
        ]
        rag_xml, rag_md = generate_rag_contexts(temp_search_items, query)

        metrics = {
            "vector_time_ms": v_res.total_time_ms,
            "keyword_time_ms": kw_time_ms,
            "fusion_time_ms": fusion_time_ms,
            "total_time_ms": total_time_ms,
        }

        # ベクトル生結果 & キーワード生結果のシリアライズ
        vector_results_dict = [asdict(item) for item in vector_items[:top_k]]
        keyword_results_dict = kw_items[:top_k]

        return HybridSearchResponse(
            query=query,
            mode=mode,
            hybrid_results=fused_items,
            vector_results=vector_results_dict,
            keyword_results=keyword_results_dict,
            extracted_keywords=extracted_kws,
            keyword_query=kw_query,
            fusion_method=fusion_method,
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            metrics=metrics,
            keyword_api_status=kw_status,
            rag_context_xml=rag_xml,
            rag_context_markdown=rag_md,
            detected_terms=v_res.detected_terms,
        )
