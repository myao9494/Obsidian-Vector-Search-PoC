"""
Vector Searcher のテスト仕様
- FAISSによるCosine Similarity高速検索の正確性
- Document検索モード（1文書1ベクトルでの類似度計算、上位Top K、Preview生成）
- Chunk検索モード（チャンク単位の類似度計算、上位Top K、ヒット文章および前後文脈の取得）
- 抽出キーワード（extracted_keywords, keyword_query）の生成
- LLM投入用 RAG コンテキストフォーマット（rag_context_xml, rag_context_markdown）の生成
"""

import numpy as np
import pytest
from app.embedder import MockEmbedder
from app.indexer import IndexManager
from app.searcher import VectorSearcher, SearchMode, SearchResponse, extract_query_keywords, generate_rag_contexts


@pytest.fixture
def indexed_vault(tmp_path):
    """インデックス済みのVaultを用意する"""
    vault = tmp_path / "SearchVault"
    vault.mkdir()

    pica_text = (
        "# PICA-X\n\n"
        "The thermal response of PICA-X is strongly affected by resin decomposition.\n\n"
        "The pyrolysis model describes decomposition of the phenolic resin.\n\n"
        "The resulting gases contribute to internal pressure of the material."
    )
    (vault / "PICA-X.md").write_text(pica_text, encoding="utf-8")

    other_text = (
        "# General Thermal Protection\n\n"
        "Thermal protection systems are critical for atmospheric entry vehicles."
    )
    (vault / "TPS.md").write_text(other_text, encoding="utf-8")

    embedder = MockEmbedder(dim=64)
    manager = IndexManager(vault_path=str(vault), embedder=embedder)
    manager.run_index(chunk_size=120, chunk_overlap=20)

    db_path = str(vault / ".vector_search" / "index.db")
    return str(vault), db_path, embedder


def test_document_search(indexed_vault):
    """Document検索モードのテスト"""
    vault_path, db_path, embedder = indexed_vault
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)

    res = searcher.search(
        query="PICA-X pyrolysis model",
        mode=SearchMode.DOCUMENT,
        top_k=5
    )

    assert isinstance(res, SearchResponse)
    assert res.mode == SearchMode.DOCUMENT
    assert len(res.results) >= 2
    assert res.query_embedding_time_ms >= 0.0
    assert res.search_time_ms >= 0.0
    assert res.total_time_ms >= 0.0

    # 1件目の構造確認
    top_item = res.results[0]
    assert top_item.path in ["PICA-X.md", "TPS.md"]
    assert top_item.full_path.endswith(top_item.path)
    assert top_item.full_path.startswith(vault_path)
    assert -1.0 <= top_item.score <= 1.0001
    assert top_item.preview != ""


def test_chunk_search_with_context(indexed_vault):
    """Chunk検索モードと前後文脈（prev / hit / next）のテスト"""
    vault_path, db_path, embedder = indexed_vault
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)

    res = searcher.search(
        query="pyrolysis model resin decomposition",
        mode=SearchMode.CHUNK,
        top_k=3
    )

    assert isinstance(res, SearchResponse)
    assert res.mode == SearchMode.CHUNK
    assert len(res.results) > 0

    hit = res.results[0]
    assert hit.chunk_id is not None
    assert hit.chunk_index is not None
    assert hit.hit_text is not None
    assert hit.context is not None
    assert "current" in hit.context


def test_extracted_keywords_and_query_generation(indexed_vault):
    """クエリからの抽出キーワードおよびハイブリッド検索用クエリの生成テスト"""
    vault_path, db_path, embedder = indexed_vault
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)

    res = searcher.search(
        query="Macのローカル環境でmlx-whisperを使って動画から文字起こしする",
        mode=SearchMode.CHUNK,
        top_k=3
    )

    assert isinstance(res.extracted_keywords, list)
    assert len(res.extracted_keywords) > 0
    assert "Mac" in res.extracted_keywords or "mlx-whisper" in res.extracted_keywords
    assert isinstance(res.keyword_query, str)
    assert "OR" in res.keyword_query or len(res.extracted_keywords) == 1


def test_rag_context_formatting(indexed_vault):
    """LLM投入用の標準RAGフォーマット（XMLおよびMarkdown）が正しく構築されること"""
    vault_path, db_path, embedder = indexed_vault
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)

    res = searcher.search(
        query="thermal protection pyrolysis",
        mode=SearchMode.CHUNK,
        top_k=2
    )

    # XMLフォーマット検証
    assert res.rag_context_xml is not None
    assert "<context" in res.rag_context_xml
    assert "</context>" in res.rag_context_xml
    assert "<document" in res.rag_context_xml
    assert 'score="' in res.rag_context_xml

    # Markdownフォーマット検証
    assert res.rag_context_markdown is not None
    assert "## 参考コンテキスト" in res.rag_context_markdown
    assert "Score:" in res.rag_context_markdown
