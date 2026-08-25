"""
Vault Scanner のテスト仕様
- 指定されたVaultディレクトリ内の対象ファイル（デフォルト: *.md, *.markdown, *.txt など指定拡張子）を再帰的に走査すること
- .obsidian, .git, .vector_search などの指定された除外ディレクトリを無視すること
- *.excalidraw.md などの図面ファイルを無視すること
- target_extensions 引数で対象拡張子を動的に指定・拡張できること
- 各ファイルについて相対パス、絶対パス、タイトル、mtime、size、sha256、テキスト内容を抽出できること
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

    doc2_key = "SubFolder/Note2.md" if "SubFolder/Note2.md" in paths else "SubFolder\\Note2.md"
    assert paths[doc2_key].title == "Note2"
    assert "No heading here" in paths[doc2_key].text


def test_scan_vault_exclusions_and_excalidraw(tmp_path):
    """
    除外ディレクトリ (.obsidian, .git, .vector_search) および *.excalidraw.md が無視されること
    """
    (tmp_path / "Valid.md").write_text("# Valid\nContent", encoding="utf-8")
    (tmp_path / "Drawing.excalidraw.md").write_text("# Excalidraw Data\nBinary", encoding="utf-8")

    obsidian_dir = tmp_path / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "ignore.md").write_text("# Ignore", encoding="utf-8")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "git_ignore.md").write_text("# Git Ignore", encoding="utf-8")

    vs_dir = tmp_path / ".vector_search"
    vs_dir.mkdir()
    (vs_dir / "vs_ignore.md").write_text("# VS Ignore", encoding="utf-8")

    results = scan_vault(str(tmp_path))

    assert len(results) == 1
    assert results[0].relative_path == "Valid.md"


def test_scan_vault_custom_extensions(tmp_path):
    """
    target_extensions で指定した拡張子のファイル（.txt, .markdown など）が走査対象となること
    """
    (tmp_path / "Note.md").write_text("# MD Note", encoding="utf-8")
    (tmp_path / "Memo.txt").write_text("Text Memo content", encoding="utf-8")
    (tmp_path / "Doc.markdown").write_text("# Markdown Doc", encoding="utf-8")
    (tmp_path / "Data.csv").write_text("a,b,c", encoding="utf-8")
    (tmp_path / "Ignored.pdf").write_bytes(b"PDF fake")

    # .md, .txt, .markdown を対象
    results = scan_vault(str(tmp_path), target_extensions=[".md", ".txt", ".markdown"])
    paths = [d.relative_path for d in results]

    assert "Note.md" in paths
    assert "Memo.txt" in paths
    assert "Doc.markdown" in paths
    assert "Data.csv" not in paths
    assert "Ignored.pdf" not in paths


def test_scan_vault_invalid_path():
    """存在しないパスやファイルパスを指定した場合のエラーハンドリングテスト"""
    with pytest.raises(ValueError):
        scan_vault("/non/existent/path/for/sure/12345")
