"""
ハイブリッド検索エンジン (HybridSearcher) の単体テスト
仕様:
- RRF (Reciprocal Rank Fusion) によるベクトル検索結果とキーワード検索結果の統合リランキング。
- スコア正規化合成 (Weighted Score Fusion) の動作検証。
- キーワードAPIへの通信およびレスポンスパース。
- キーワードAPIダウン時の安全なフォールバック（ベクトル検索単体で正常応答）。
- 抽出キーワードを用いたORクエリ生成とAPIへの送信。
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.hybrid_searcher import (
    HybridSearcher,
    HybridSearchResultItem,
    HybridSearchResponse,
    reciprocal_rank_fusion,
    weighted_score_fusion,
)
from app.searcher import SearchResultItem, SearchMode


def test_reciprocal_rank_fusion_both_matched():
    """ベクトル検索とキーワード検索の双方でヒットした場合にRRFスコアが最上位になることを検証"""
    vector_items = [
        SearchResultItem(
            document_id=1,
            path="docs/vector_match.md",
            title="Vector Match",
            score=0.92,
            full_path="/vault/docs/vector_match.md",
            hit_text="ベクトル検索で見つかったテキスト",
        ),
        SearchResultItem(
            document_id=2,
            path="docs/both_match.md",
            title="Both Match",
            score=0.85,
            full_path="/vault/docs/both_match.md",
            hit_text="両方でヒットしたテキスト",
        ),
    ]

    keyword_items = [
        {
            "file_id": 101,
            "full_path": "/vault/docs/both_match.md",
            "file_name": "both_match.md",
            "snippet": "<mark>キーワード</mark>検索スニペット",
            "utility_score": 10.0,
            "relevance_bucket": 3,
        },
        {
            "file_id": 102,
            "full_path": "/vault/docs/keyword_only.md",
            "file_name": "keyword_only.md",
            "snippet": "<mark>キーワード</mark>のみヒット",
            "utility_score": 8.0,
            "relevance_bucket": 2,
        },
    ]

    results = reciprocal_rank_fusion(
        vector_items=vector_items,
        keyword_items=keyword_items,
        vector_weight=0.5,
        keyword_weight=0.5,
        k=60,
    )

    assert len(results) == 3
    # both_match.md はベクトル第2位・キーワード第1位のため、RRFスコアでトップになる
    assert results[0].full_path == "/vault/docs/both_match.md"
    assert results[0].match_type == "both"
    assert results[0].vector_rank == 2
    assert results[0].keyword_rank == 1
    assert results[0].snippet == "<mark>キーワード</mark>検索スニペット"
    assert results[0].hit_text == "両方でヒットしたテキスト"

    # 残りのアイテムの検証
    paths = [r.full_path for r in results]
    assert "/vault/docs/vector_match.md" in paths
    assert "/vault/docs/keyword_only.md" in paths


def test_weighted_score_fusion():
    """正規化スコア合成 (Weighted Score Fusion) の動作検証"""
    vector_items = [
        SearchResultItem(
            document_id=1,
            path="docs/a.md",
            title="Doc A",
            score=0.80,
            full_path="/vault/docs/a.md",
        ),
    ]
    keyword_items = [
        {
            "file_id": 1,
            "full_path": "/vault/docs/a.md",
            "file_name": "a.md",
            "snippet": "スニペット",
            "utility_score": 5.0,
        },
    ]

    results = weighted_score_fusion(
        vector_items=vector_items,
        keyword_items=keyword_items,
        vector_weight=0.6,
        keyword_weight=0.4,
    )

    assert len(results) == 1
    assert results[0].full_path == "/vault/docs/a.md"
    assert results[0].match_type == "both"
    assert results[0].hybrid_score > 0.0


def test_hybrid_searcher_fallback_on_keyword_api_error(tmp_path):
    """キーワードAPIがダウン/エラー時でもベクトル検索のみで安全に結果を返すことを検証"""
    mock_vector_searcher = MagicMock()
    mock_vector_searcher.search.return_value = MagicMock(
        query="テストクエリ",
        mode=SearchMode.CHUNK,
        results=[
            SearchResultItem(
                document_id=1,
                path="note.md",
                title="Note",
                score=0.88,
                full_path=str(tmp_path / "note.md"),
                hit_text="テスト本文",
            )
        ],
        total_candidates=1,
        query_embedding_time_ms=5.0,
        search_time_ms=2.0,
        total_time_ms=7.0,
        extracted_keywords=["テスト"],
        keyword_query="テスト",
        detected_terms=[],
    )

    hybrid_searcher = HybridSearcher(
        vector_searcher=mock_vector_searcher,
        keyword_api_url="http://127.0.0.1:99999",  # 存在しないポート
    )

    # 意図的にキーワードAPIで例外を起こさせる
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        res = hybrid_searcher.search(
            query="テストクエリ",
            vault_path=str(tmp_path),
            mode="chunk",
            top_k=10,
        )

    assert len(res.hybrid_results) == 1
    assert res.hybrid_results[0].match_type == "vector_only"
    assert res.keyword_api_status["connected"] is False
    assert "エラー" in res.keyword_api_status["message"] or "failed" in res.keyword_api_status["message"].lower() or "Connection" in res.keyword_api_status["message"]
