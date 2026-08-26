"""
単一ファイル差分更新・プロファイリング機能のテスト
仕様:
- ファイルの変更検知後、単一ファイルのみを即座に差分更新（Chunking, Embedding, DB反映）できること。
- 各工程の処理時間（ミリ秒単位: I/Oハッシュ、チャンキング、Embedding推論、DB保存、総所要時間）を正確に計測して返却すること。
- 新規追加 (created)、内容更新 (updated)、変更なしスキップ (skipped)、削除 (deleted) を正しく判定すること。
- 意地悪なデータ（1万文字以上の超長文、空ファイル、特殊記号、大量見出し等）でもクラッシュせず安全に処理できること。
"""

import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from app.db import init_db, get_db_stats, get_document_by_id
from app.dictionary import GlossaryDictionary, GlossaryEntry
from app.embedder import MockEmbedder
from app.indexer import IndexManager, SingleFileUpdateResult


@pytest.fixture
def temp_vault():
    temp_dir = tempfile.mkdtemp()
    vault_path = Path(temp_dir)
    
    # テスト用初期ファイル
    file1 = vault_path / "note1.md"
    file1.write_text("# タイトル1\nこれはノート1の初期本文です。", encoding="utf-8")
    
    file2 = vault_path / "sub" / "note2.md"
    file2.parent.mkdir(parents=True, exist_ok=True)
    file2.write_text("# サブノート\nサブフォルダ内のノート本文です。", encoding="utf-8")

    yield vault_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_update_single_file_created(temp_vault):
    """新規作成ファイルの差分更新テスト"""
    embedder = MockEmbedder(dim=256)
    manager = IndexManager(vault_path=str(temp_vault), embedder=embedder)

    # 初期状態はインデックス未作成
    new_file = temp_vault / "new_note.md"
    new_file.write_text("# 新規ノート\n新しく作成されたファイルの本文です。\n\n## 詳細\n詳細内容。", encoding="utf-8")

    res: SingleFileUpdateResult = manager.update_single_file("new_note.md")

    assert res.status == "created"
    assert res.relative_path == "new_note.md"
    assert res.chunk_count >= 1
    assert res.total_time_ms > 0
    assert res.chunking_time_ms >= 0
    assert res.embedding_time_ms >= 0
    assert res.db_time_ms >= 0

    stats = get_db_stats(manager.db_path)
    assert stats["document_count"] == 1


def test_update_single_file_updated(temp_vault):
    """既存ファイルの編集差分更新テスト"""
    embedder = MockEmbedder(dim=256)
    manager = IndexManager(vault_path=str(temp_vault), embedder=embedder)
    manager.run_index()  # 初回インデックス構築

    # note1.md を編集
    note1 = temp_vault / "note1.md"
    time.sleep(0.01)  # mtimeを確実に進める
    note1.write_text("# タイトル1 (更新)\n編集後の本文です。\n## セクション追加\n新しい知見です。", encoding="utf-8")

    res: SingleFileUpdateResult = manager.update_single_file("note1.md")

    assert res.status == "updated"
    assert res.relative_path == "note1.md"
    assert res.chunk_count >= 2
    assert res.total_time_ms > 0

    # DB内のドキュメント情報が更新されているか確認
    meta = get_db_stats(manager.db_path)
    assert meta["document_count"] == 2


def test_update_single_file_skipped(temp_vault):
    """変更がない場合のスキップ判定テスト"""
    embedder = MockEmbedder(dim=256)
    manager = IndexManager(vault_path=str(temp_vault), embedder=embedder)
    manager.run_index()

    # 変更なしで update_single_file を呼び出す
    res: SingleFileUpdateResult = manager.update_single_file("note1.md")

    assert res.status == "skipped"
    assert res.chunk_count == 0
    assert res.embedding_time_ms == 0.0  # スキップ時はEmbeddingしない
    assert res.total_time_ms >= 0


def test_update_single_file_deleted(temp_vault):
    """ファイル削除時のインデックス追従テスト"""
    embedder = MockEmbedder(dim=256)
    manager = IndexManager(vault_path=str(temp_vault), embedder=embedder)
    manager.run_index()

    # ファイルを削除
    note1 = temp_vault / "note1.md"
    note1.unlink()

    res: SingleFileUpdateResult = manager.update_single_file("note1.md")

    assert res.status == "deleted"
    stats = get_db_stats(manager.db_path)
    assert stats["document_count"] == 1


def test_update_single_file_with_custom_content(temp_vault):
    """GUI等から直接渡されたテキストで差分更新を行うテスト（ファイル上書きと即時インデックス）"""
    embedder = MockEmbedder(dim=256)
    manager = IndexManager(vault_path=str(temp_vault), embedder=embedder)
    manager.run_index()

    custom_text = "# 直接入力ノート\nGUIから直接渡された内容です。\n## メモ\n即時反映テスト。"
    res: SingleFileUpdateResult = manager.update_single_file("direct_edit.md", content=custom_text)

    assert res.status == "created"
    assert (temp_vault / "direct_edit.md").exists()
    assert (temp_vault / "direct_edit.md").read_text(encoding="utf-8") == custom_text


def test_update_single_file_malicious_cases(temp_vault):
    """意地悪なデータ（超長文・特殊記号・空ファイル）に対する堅牢性テスト"""
    embedder = MockEmbedder(dim=256)
    manager = IndexManager(vault_path=str(temp_vault), embedder=embedder)

    # 1. 空ファイル
    empty_file = temp_vault / "empty.md"
    empty_file.write_text("", encoding="utf-8")
    res_empty = manager.update_single_file("empty.md")
    assert res_empty.status == "created"
    assert res_empty.chunk_count == 0 or res_empty.chunk_count == 1

    # 2. 超長文（10,000文字以上）
    long_file = temp_vault / "huge.md"
    long_content = "# 超巨大ノート\n" + ("これは非常に長い文章の段落です。社内検証用テキスト。\n\n" * 300)
    long_file.write_text(long_content, encoding="utf-8")
    res_huge = manager.update_single_file("huge.md")
    assert res_huge.status == "created"
    assert res_huge.chunk_count > 10
    assert res_huge.embedding_time_ms > 0

    # 3. 特殊文字・壊れた記号だらけのノート
    special_file = temp_vault / "special.md"
    special_file.write_text("# 💣🔥 特殊記号 & <script>alert('xss')</script> \n[[リンク|#$!@%]]\n```python\ndef test(): pass\n```", encoding="utf-8")
    res_special = manager.update_single_file("special.md")
    assert res_special.status == "created"
    assert res_special.chunk_count >= 1
