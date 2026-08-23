"""
Index Manager のテスト仕様
- 初回インデックス処理（全件取得・チャンク分割・Embedding生成・SQLite登録）
- 差分インデックス処理（新規追加・更新・未変更スキップ・削除検知）
- 進捗コールバック（processed, total, progress%, elapsed_sec）の呼び出し
- インデックス処理統計（件数、所要時間、DBサイズ）の集計
"""

import os
import time
import pytest
from app.embedder import MockEmbedder
from app.indexer import IndexManager, IndexResult


@pytest.fixture
def mock_vault(tmp_path):
    """テスト用Vaultディレクトリの作成"""
    vault = tmp_path / "TestVault"
    vault.mkdir()

    # Note 1
    (vault / "Note1.md").write_text("# Note 1\nThis is initial content of Note 1.", encoding="utf-8")

    # Note 2 (Subfolder)
    sub = vault / "SubFolder"
    sub.mkdir()
    (sub / "Note2.md").write_text("# Note 2\nThis is initial content of Note 2.", encoding="utf-8")

    return vault


def test_initial_index(mock_vault):
    """初回インデックス処理のテスト"""
    embedder = MockEmbedder(dim=64)
    manager = IndexManager(vault_path=str(mock_vault), embedder=embedder)

    progress_events = []
    def on_progress(p):
        progress_events.append(p)

    result = manager.run_index(progress_callback=on_progress)

    assert isinstance(result, IndexResult)
    assert result.total_files == 2
    assert result.new_count == 2
    assert result.updated_count == 0
    assert result.skipped_count == 0
    assert result.deleted_count == 0
    assert result.chunk_count >= 2
    assert len(progress_events) >= 2
    assert os.path.exists(mock_vault / ".vector_search" / "index.db")


def test_incremental_index(mock_vault):
    """差分インデックス処理のテスト（新規、変更、スキップ、削除）"""
    embedder = MockEmbedder(dim=64)
    manager = IndexManager(vault_path=str(mock_vault), embedder=embedder)

    # 1回目
    res1 = manager.run_index()
    assert res1.new_count == 2

    # ファイル変更 (Note1.md を更新)
    time.sleep(0.01)
    (mock_vault / "Note1.md").write_text("# Note 1 Updated\nUpdated text content.", encoding="utf-8")

    # ファイル追加 (Note3.md を追加)
    (mock_vault / "Note3.md").write_text("# Note 3\nBrand new note 3.", encoding="utf-8")

    # ファイル削除 (SubFolder/Note2.md を削除)
    (mock_vault / "SubFolder" / "Note2.md").unlink()

    # 2回目（差分実行）
    res2 = manager.run_index()

    assert res2.total_files == 2  # Note1, Note3
    assert res2.new_count == 1     # Note3
    assert res2.updated_count == 1 # Note1
    assert res2.skipped_count == 0
    assert res2.deleted_count == 1 # Note2


def test_skip_when_no_changes(mock_vault):
    """変更がない場合は全件スキップされること"""
    embedder = MockEmbedder(dim=64)
    manager = IndexManager(vault_path=str(mock_vault), embedder=embedder)

    # 1回目
    manager.run_index()

    # 2回目（何も変更なし）
    res2 = manager.run_index()
    assert res2.new_count == 0
    assert res2.updated_count == 0
    assert res2.skipped_count == 2
    assert res2.deleted_count == 0
