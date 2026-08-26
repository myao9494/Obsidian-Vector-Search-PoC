"""
専門用語・類似語辞書を組み込んだベクトル検索 (VectorSearcher with Glossary) 結合テスト
仕様:
- 自然文質問（例: 「PJXのプロジェクトでの議事録ってどんなものがあったっけ」）に対し、
  本文に「プロジェクトX」としか書かれていないノートが最上位でヒットすること。
- 自然文質問（例: 「ポチッと君の使い方は？」）に対し、
  本文に「交通費・出張旅費精算」としか書かれていないノートが最上位でヒットすること。
- レスポンスに detected_terms（検知された専門用語一覧）が含まれること。
"""

import os
import pytest
from app.db import init_db
from app.dictionary import GlossaryDictionary
from app.embedder import MockEmbedder
from app.indexer import IndexManager
from app.searcher import VectorSearcher, SearchMode


@pytest.fixture
def temp_vault_with_dict(tmp_path):
    """辞書付きテスト用Vault環境の構築"""
    vault = tmp_path / "test_vault"
    vault.mkdir()
    
    # 辞書CSVの作成
    glossary_file = vault / "glossary.csv"
    glossary_file.write_text(
        "Term,Synonyms,Description\n"
        "PJ-X,\"プロジェクトX, PJX, PX\",2024年発足の社内基幹システム刷新プロジェクト\n"
        "ポチッと君,ポチット,社内の交通費・経費精算および旅費申請システム\n",
        encoding="utf-8"
    )

    # ノート1: 「プロジェクトX」と記述（「PJX」「PJ-X」は含まない）
    note1 = vault / "2024-05-10_プロジェクトX_キックオフ.md"
    note1.write_text(
        "# 2024年5月10日 プロジェクトX キックオフ定例議事録\n\n"
        "社内基幹システム刷新の全体方針に関する会議の記録です。\n"
        "マイクロサービスアーキテクチャへの段階的移行計画を承認しました。\n",
        encoding="utf-8"
    )

    # ノート2: 「交通費・経費精算」と記述（「ポチッと君」は含まない）
    note2 = vault / "社内経費精算ガイド.md"
    note2.write_text(
        "# 社内交通費・経費精算および出張旅費申請ガイド\n\n"
        "立替交通費および出張旅費の申請フローと精算ルールのマニュアルです。\n"
        "毎月末営業日までに申請承認ワークフローを提出してください。\n",
        encoding="utf-8"
    )

    # 無関係なノート
    note3 = vault / "Pythonクックブック.md"
    note3.write_text(
        "# Python非同期処理の書き方\n\n"
        "asyncioとFastAPIを用いた非同期Webサーバーの実装例です。\n",
        encoding="utf-8"
    )

    return str(vault)


def test_search_with_glossary_enrichment(temp_vault_with_dict):
    """辞書連携による未知略称・社内造語のベクトル検索ヒット検証"""
    vault_path = temp_vault_with_dict
    db_path = os.path.join(vault_path, ".vector_search", "index.db")
    
    embedder = MockEmbedder(dim=256)
    glossary = GlossaryDictionary.from_file(os.path.join(vault_path, "glossary.csv"))
    
    # 辞書を渡してインデックス作成
    indexer = IndexManager(db_path=db_path, embedder=embedder, glossary=glossary)
    result = indexer.index_vault(vault_path)
    assert result.total_files >= 3

    # 辞書を渡して検索エンジンを初期化
    searcher = VectorSearcher(db_path=db_path, embedder=embedder, glossary=glossary)

    # 1. 「PJXのプロジェクトでの議事録ってどんなものがあったっけ」で検索
    resp1 = searcher.search(
        query="PJXのプロジェクトでの議事録ってどんなものがあったっけ",
        mode=SearchMode.CHUNK,
        top_k=5
    )
    
    assert len(resp1.results) > 0
    assert "プロジェクトX" in resp1.results[0].title or "プロジェクトX" in (resp1.results[0].hit_text or "")
    assert len(resp1.detected_terms) >= 1
    assert resp1.detected_terms[0]["term"] == "PJ-X"

    # 2. 「ポチッと君の使い方は？」で検索
    resp2 = searcher.search(
        query="ポチッと君の使い方は？",
        mode=SearchMode.CHUNK,
        top_k=5
    )
    
    assert len(resp2.results) > 0
    assert "経費精算" in resp2.results[0].title or "経費精算" in (resp2.results[0].hit_text or "")
    assert len(resp2.detected_terms) >= 1
    assert resp2.detected_terms[0]["term"] == "ポチッと君"
