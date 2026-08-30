"""
ハイブリッド検索 API エンドポイントのテスト
仕様:
- POST /api/hybrid/search のリクエストとレスポンス検証
- GET /api/hybrid/keyword-api-status の動作検証
- キーワードAPI未接続時のフォールバック動作
"""

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


from app.main import app, state
from app.embedder import MockEmbedder


@pytest.fixture
def client():
    return TestClient(app)


def test_keyword_api_status_endpoint(client):
    """GET /api/hybrid/keyword-api-status のテスト"""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        response = client.get("/api/hybrid/keyword-api-status?keyword_api_url=http://127.0.0.1:8079")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["url"] == "http://127.0.0.1:8079"


def test_hybrid_search_endpoint_without_index(client, tmp_path):
    """インデックス未作成時の400エラー検証"""
    response = client.post(
        "/api/hybrid/search",
        json={
            "vault_path": str(tmp_path),
            "query": "テスト",
        },
    )
    assert response.status_code == 400
    assert "インデックスが存在しません" in response.json()["detail"]


def test_hybrid_search_endpoint_success(client, tmp_path):
    """ハイブリッド検索の正常レスポンス検証"""
    from app.db import init_db, upsert_document, insert_chunks
    import numpy as np

    db_dir = tmp_path / ".vector_search"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / "index.db")
    init_db(db_path)

    doc_id = upsert_document(
        db_path=db_path,
        path="test.md",
        title="Test Document",
        mtime=123456.0,
        size=100,
        sha256="dummyhash",
        text="これはテスト文書です。",
        embedding=np.zeros(384, dtype=np.float32).tobytes(),
    )
    insert_chunks(
        db_path=db_path,
        document_id=doc_id,
        chunks=[
            (
                0,
                "これはテスト文書のチャンクです。",
                np.zeros(384, dtype=np.float32).tobytes(),
                384,
            )
        ],
    )


    state.embedder = MockEmbedder(dim=384)


    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "total": 1,
            "items": [
                {
                    "file_id": 99,
                    "full_path": str(tmp_path / "test.md"),
                    "file_name": "test.md",
                    "snippet": "<mark>テスト</mark>文書",
                    "utility_score": 10.0,
                }
            ]
        }).encode("utf-8")
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        response = client.post(
            "/api/hybrid/search",
            json={
                "vault_path": str(tmp_path),
                "query": "テスト",
                "keyword_api_url": "http://127.0.0.1:8079",
                "mode": "chunk",
                "top_k": 10,
                "vector_weight": 0.5,
                "keyword_weight": 0.5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["hybrid_results"]) >= 1
        assert data["hybrid_results"][0]["match_type"] == "both"
        assert data["hybrid_results"][0]["title"] == "Test Document" or data["hybrid_results"][0]["title"] == "test.md"
        assert data["metrics"]["total_time_ms"] >= 0

