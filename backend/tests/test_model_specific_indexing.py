"""
モデル別インデックス個別管理および差分インデックス機能のテスト
仕様:
- 各Embeddingモデル（モデルパス/名称/次元数）ごとに独立したSQLite DB（index_<model_key>.db）が生成・管理されること。
- モデルAでインデックスを作成後、モデルBに切り替えてインデックスを作成しても、モデルAのDBが消去・上書きされず保持されること。
- モデルAに切り替えた際、再インデックスなしで即座にモデルAのインデックスを用いて検索できること。
- 差分更新（force_reindex=False）では変更のないノートがスキップされ、更新・追加されたノートのみが反映されること。
- 全件再構築（force_reindex=True）では対象モデルのインデックスのみがクリーンに再作成され、他モデルのインデックスには影響しないこと。
- API経由でのモデル切り替え・モデル別DB統計取得が正しく動作すること。
"""

import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.embedder import MockEmbedder, BaseEmbedder
from app.indexer import IndexManager, get_model_db_path, get_model_identifier
from app.searcher import VectorSearcher, SearchMode
from app.main import app, state


class NamedMockEmbedder(MockEmbedder):
    """テスト用モデル名・次元数指定可能なMockEmbedder"""
    def __init__(self, model_name: str, dim: int = 384):
        super().__init__(dim=dim, model_path=model_name)



@pytest.fixture
def temp_vault():
    """テスト用一時Vaultディレクトリを作成"""
    tmp_dir = tempfile.mkdtemp(prefix="test_vault_multi_model_")
    vault_path = Path(tmp_dir)

    # テスト用Markdownノートを作成
    (vault_path / "note1.md").write_text("# ノート1\n機械学習とベクトル検索の基礎について解説します。", encoding="utf-8")
    (vault_path / "note2.md").write_text("# ノート2\nObsidianのプラグイン開発とアーキテクチャ設計。", encoding="utf-8")

    yield vault_path

    # クリーンアップ
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_get_model_identifier():
    """モデルパスまたはEmbedderからモデル識別子が正しく導出されること"""
    embedder_standard = NamedMockEmbedder("models/ruri-v3-310m", dim=768)
    embedder_light = NamedMockEmbedder("/Users/test/models/ruri-v3-30m", dim=256)
    embedder_mock = MockEmbedder(dim=384)

    assert get_model_identifier(embedder=embedder_standard) == "ruri-v3-310m"
    assert get_model_identifier(embedder=embedder_light) == "ruri-v3-30m"
    assert "mock" in get_model_identifier(embedder=embedder_mock)


def test_get_model_db_path(temp_vault):
    """Vaultパスとモデルから固有のDBパスが解決されること"""
    embedder_a = NamedMockEmbedder("ruri-v3-310m", dim=768)
    embedder_b = NamedMockEmbedder("ruri-v3-30m", dim=256)

    db_path_a = get_model_db_path(str(temp_vault), embedder=embedder_a)
    db_path_b = get_model_db_path(str(temp_vault), embedder=embedder_b)

    assert db_path_a.endswith("index_ruri-v3-310m.db")
    assert db_path_b.endswith("index_ruri-v3-30m.db")
    assert db_path_a != db_path_b


def test_multi_model_indexes_isolated_and_switchable(temp_vault):
    """モデルAとモデルBでそれぞれ独立してインデックスが作成・保持され、切り替え検索できること"""
    embedder_a = NamedMockEmbedder("model_standard", dim=768)
    embedder_b = NamedMockEmbedder("model_light", dim=256)

    # 1. モデルAでインデックス作成
    mgr_a = IndexManager(vault_path=str(temp_vault), embedder=embedder_a)
    res_a = mgr_a.run_index()
    assert res_a.new_count == 2
    assert os.path.exists(mgr_a.db_path)
    assert mgr_a.db_path.endswith("index_model_standard.db")

    # モデルAでの検索確認
    searcher_a = VectorSearcher(db_path=mgr_a.db_path, embedder=embedder_a)
    hits_a = searcher_a.search("機械学習", mode=SearchMode.CHUNK)
    assert len(hits_a.results) > 0

    # 2. モデルBに切り替えてインデックス作成
    mgr_b = IndexManager(vault_path=str(temp_vault), embedder=embedder_b)
    res_b = mgr_b.run_index()
    assert res_b.new_count == 2
    assert os.path.exists(mgr_b.db_path)
    assert mgr_b.db_path.endswith("index_model_light.db")

    # モデルBでの検索確認
    searcher_b = VectorSearcher(db_path=mgr_b.db_path, embedder=embedder_b)
    hits_b = searcher_b.search("Obsidian", mode=SearchMode.CHUNK)
    assert len(hits_b.results) > 0

    # 3. 再びモデルAで検索（インデックスの再作成なしでそのまま検索できること）
    assert os.path.exists(mgr_a.db_path)
    searcher_a_again = VectorSearcher(db_path=mgr_a.db_path, embedder=embedder_a)
    hits_a_again = searcher_a_again.search("機械学習", mode=SearchMode.CHUNK)
    assert len(hits_a_again.results) > 0
    assert hits_a_again.results[0].path == "note1.md"



def test_incremental_indexing_per_model(temp_vault):
    """差分インデックス（force_reindex=False）で変更・新規ファイルのみが処理されること"""
    embedder = NamedMockEmbedder("test_model", dim=384)
    mgr = IndexManager(vault_path=str(temp_vault), embedder=embedder)

    # 初回インデックス
    res1 = mgr.run_index(force_reindex=False)
    assert res1.new_count == 2
    assert res1.skipped_count == 0

    # 変更なしで差分インデックス実行
    res2 = mgr.run_index(force_reindex=False)
    assert res2.new_count == 0
    assert res2.updated_count == 0
    assert res2.skipped_count == 2

    # ノート1を変更、ノート3を新規作成
    (temp_vault / "note1.md").write_text("# ノート1 改訂版\nディープラーニングとベクトル検索の応用。", encoding="utf-8")
    (temp_vault / "note3.md").write_text("# ノート3\n新しく追加されたドキュメントです。", encoding="utf-8")

    res3 = mgr.run_index(force_reindex=False)
    assert res3.new_count == 1      # note3
    assert res3.updated_count == 1  # note1
    assert res3.skipped_count == 1  # note2


def test_clean_reindex_does_not_affect_other_models(temp_vault):
    """全件再構築（force_reindex=True）が他モデルのDBを破壊しないこと"""
    embedder_a = NamedMockEmbedder("model_a", dim=384)
    embedder_b = NamedMockEmbedder("model_b", dim=256)

    mgr_a = IndexManager(vault_path=str(temp_vault), embedder=embedder_a)
    mgr_a.run_index()

    mgr_b = IndexManager(vault_path=str(temp_vault), embedder=embedder_b)
    mgr_b.run_index()

    # モデルAのみ全件再構築
    res_a_clean = mgr_a.run_index(force_reindex=True)
    assert res_a_clean.new_count == 2

    # モデルBのDBが無傷で存在し検索可能なこと
    searcher_b = VectorSearcher(db_path=mgr_b.db_path, embedder=embedder_b)
    hits_b = searcher_b.search("Obsidian", mode=SearchMode.CHUNK)
    assert len(hits_b.results) > 0


def test_api_multi_model_stats_and_search(temp_vault):
    """FastAPI 経由でモデルごとのインデックス作成、統計取得、検索が切り替わること"""
    client = TestClient(app)

    # 1. MockモデルAをロード
    client.post("/api/model/load", json={"model_path": "mock_a", "use_mock": True})

    # インデックス作成
    res_idx = client.post("/api/index/start", json={
        "vault_path": str(temp_vault),
        "force_reindex": False,
    })
    assert res_idx.status_code == 200

    # 統計取得
    res_stats = client.get(f"/api/index/stats?vault_path={temp_vault}")
    assert res_stats.status_code == 200
    stats_data = res_stats.json()
    assert stats_data["document_count"] == 2
    assert "models" in stats_data  # モデル別統計が含まれていること

    # 検索
    res_search = client.post("/api/search", json={
        "vault_path": str(temp_vault),
        "query": "機械学習",
        "mode": "chunk"
    })
    assert res_search.status_code == 200
    assert len(res_search.json()["results"]) > 0
