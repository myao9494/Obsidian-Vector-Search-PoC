"""
FastAPI REST API のテスト仕様
- CORSおよびヘルスチェック
- モデルのロードAPI（モックモード / ローカルパス）
- フォルダ選択ダイアログAPIのモック検証
- インデックス開始、進捗取得、統計取得API
- ベクトル検索API（Document / Chunk）
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app, state


@pytest.fixture
def client(tmp_path):
    """TestClientフィクスチャとテスト用Vaultのセットアップ"""
    vault = tmp_path / "ApiVault"
    vault.mkdir()
    (vault / "Doc1.md").write_text("# API Doc 1\nContent for API testing.", encoding="utf-8")
    (vault / "Doc2.md").write_text("# API Doc 2\nSecond document content.", encoding="utf-8")

    # 初期状態のリセット
    state.vault_path = str(vault)
    state.model_path = "mock"
    state.is_mock_model = True

    return TestClient(app), str(vault)


def test_health_check(client):
    test_client, _ = client
    response = test_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_load_mock_model(client):
    test_client, _ = client
    response = test_client.post("/api/model/load", json={"model_path": "mock", "use_mock": True})
    assert response.status_code == 200
    data = response.json()
    assert data["loaded"] is True
    assert data["dim"] == 384


def test_index_and_stats(client):
    test_client, vault_path = client
    # モデルロード
    test_client.post("/api/model/load", json={"model_path": "mock", "use_mock": True})

    # インデックス実行
    response = test_client.post("/api/index/start", json={"vault_path": vault_path})
    assert response.status_code == 200
    result = response.json()
    assert result["total_files"] == 2
    assert result["new_count"] == 2

    # 統計取得
    stats_res = test_client.get(f"/api/index/stats?vault_path={vault_path}")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["document_count"] == 2
    assert stats["chunk_count"] >= 2


def test_search_api(client):
    test_client, vault_path = client
    # セットアップ
    test_client.post("/api/model/load", json={"model_path": "mock", "use_mock": True})
    test_client.post("/api/index/start", json={"vault_path": vault_path})

    # 検索 (Chunk)
    search_res = test_client.post(
        "/api/search",
        json={
            "vault_path": vault_path,
            "query": "API testing content",
            "mode": "chunk",
            "top_k": 5
        }
    )
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["mode"] == "chunk"
    assert len(data["results"]) > 0
    assert data["results"][0]["score"] is not None

    # 検索 (Document)
    search_doc_res = test_client.post(
        "/api/search",
        json={
            "vault_path": vault_path,
            "query": "API testing content",
            "mode": "document",
            "top_k": 5
        }
    )
    assert search_doc_res.status_code == 200
    doc_data = search_doc_res.json()
    assert doc_data["mode"] == "document"
    assert len(doc_data["results"]) > 0


def test_update_file_api(client):
    test_client, vault_path = client
    test_client.post("/api/model/load", json={"model_path": "mock", "use_mock": True})
    test_client.post("/api/index/start", json={"vault_path": vault_path})

    # ファイル差分更新
    update_res = test_client.post(
        "/api/index/update-file",
        json={
            "vault_path": vault_path,
            "relative_path": "Doc1.md",
            "content": "# API Doc 1 (Updated)\nUpdated content directly via API."
        }
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["status"] == "updated"
    assert data["total_time_ms"] > 0
    assert data["chunk_count"] >= 1


def test_dictionary_save_and_status_api(client):
    test_client, vault_path = client

    # 初期状態（辞書ファイルなし）
    st_res = test_client.get(f"/api/dictionary/status?vault_path={vault_path}")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["loaded"] is False
    assert st_data["total_entries"] == 0

    # 辞書エントリを保存 (POST /api/dictionary/save)
    save_payload = {
        "vault_path": vault_path,
        "file_name": "glossary.xlsx",
        "entries": [
            {
                "terms": "PJ-X, プロジェクトX, PJX",
                "description": "社内基幹システム刷新プロジェクト"
            },
            {
                "terms": "ポチッと君, ポチット",
                "description": "交通費・経費精算システム"
            }
        ]
    }
    save_res = test_client.post("/api/dictionary/save", json=save_payload)
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["success"] is True
    assert save_data["total_entries"] == 2

    # 保存後のステータス確認
    st_res2 = test_client.get(f"/api/dictionary/status?vault_path={vault_path}")
    assert st_res2.status_code == 200
    st_data2 = st_res2.json()
    assert st_data2["loaded"] is True
    assert st_data2["total_entries"] == 2
    assert st_data2["file_name"] == "glossary.xlsx"
    assert len(st_data2["entries"]) == 2
    assert st_data2["entries"][0]["term"] == "PJ-X"
    assert "プロジェクトX" in st_data2["entries"][0]["synonyms"]


