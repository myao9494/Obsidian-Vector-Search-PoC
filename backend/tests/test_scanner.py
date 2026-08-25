"""
Vault Scanner のテスト仕様
- 指定されたVaultディレクトリ内のMarkdownファイル（*.md）を再帰的に走査すること
- .obsidian, .git, .vector_search などの指定された除外ディレクトリを無視すること
- 各ファイルについて相対パス、絶対パス、タイトル（先頭見出しまたはファイル名）、mtime、size、sha256、テキスト内容を抽出できること
"""

import os
import tempfile
import pytest
from app.scanner import scan_vault, DocumentMetadata


def test_scan_vault_basic(tmp_path):
    """
    基本的なVault走査のテスト:
    - 通常のMarkdownファイルが取得できること
    - タイトルが抽出できること (H1見出しまたはファイル名)
    - sha256, mtime, size, text が正しく計算されること
    """
    # テスト用ファイル作成
    note1 = tmp_path / "Note1.md"
    note1.write_text("# Note One Title\n\nThis is note 1 body text.", encoding="utf-8")

    sub_dir = tmp_path / "SubFolder"
    sub_dir.mkdir()
    note2 = sub_dir / "Note2.md"
    note2.write_text("No heading here, just plain content.", encoding="utf-8")

    results = scan_vault(str(tmp_path))

    assert len(results) == 2
    paths = {doc.relative_path: doc for doc in results}

    assert "Note1.md" in paths
    assert "Note1" in paths["Note1.md"].title and "Note One Title" in paths["Note1.md"].title
    assert "This is note 1 body text." in paths["Note1.md"].text
    assert paths["Note1.md"].size > 0
    assert len(paths["Note1.md"].sha256) == 64

    assert "SubFolder/Note2.md" in paths or "SubFolder\\Note2.md" in paths
    doc2_key = "SubFolder/Note2.md" if "SubFolder/Note2.md" in paths else "SubFolder\\Note2.md"
    assert paths[doc2_key].title == "Note2"
    assert "No heading here" in paths[doc2_key].text


def test_scan_vault_exclusions(tmp_path):
    """
    除外ディレクトリ (.obsidian, .git, .vector_search) が正しく無視されることのテスト
    """
    # 正常なファイル
    (tmp_path / "Valid.md").write_text("# Valid\nContent", encoding="utf-8")

    # .obsidian 配下のファイル
    obsidian_dir = tmp_path / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "workspace.json").write_text("{}", encoding="utf-8")
    (obsidian_dir / "ignore.md").write_text("# Ignore", encoding="utf-8")

    # .git 配下のファイル
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "git_ignore.md").write_text("# Git Ignore", encoding="utf-8")

    # .vector_search 配下のファイル
    vs_dir = tmp_path / ".vector_search"
    vs_dir.mkdir()
    (vs_dir / "vs_ignore.md").write_text("# VS Ignore", encoding="utf-8")

    # 非mdファイル
    (tmp_path / "image.png").write_bytes(b"PNG fake data")

    results = scan_vault(str(tmp_path))

    assert len(results) == 1
    assert results[0].relative_path == "Valid.md"


def test_scan_vault_invalid_path():
    """
    存在しないパスやファイルパスを指定した場合のエラーハンドリングテスト
    """
    with pytest.raises(ValueError):
        scan_vault("/non/existent/path/for/sure/12345")
