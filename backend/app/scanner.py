"""
Vault Scanner モジュール
仕様:
- 指定されたVaultディレクトリ内の対象ファイル（デフォルト: *.md, *.markdown, *.txt など指定拡張子）を再帰的に走査。
- .obsidian, .git, .vector_search, .trash などの除外ディレクトリを無視。
- *.excalidraw.md などの図面ファイルを無視。
- target_extensions パラメータによる柔軟な対象拡張子の指定・拡張。
- 各ファイルについて相対パス、絶対パス、タイトル、mtime、size、sha256、テキスト内容を抽出。
"""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

# 除外対象ディレクトリ
EXCLUDED_DIRS = {
    ".obsidian",
    ".git",
    ".vector_search",
    ".trash",
    ".agents",
    "node_modules",
    ".venv",
    "__pycache__",
}

# 除外ファイル接尾辞（小文字）
EXCLUDED_SUFFIXES = (
    ".excalidraw.md",
    ".excalidraw",
    ".canvas",
    ".drawio.svg",
    ".drawio",
)

DEFAULT_EXTENSIONS = [".md", ".markdown", ".txt"]


@dataclass
class DocumentMetadata:
    """走査されたMarkdownファイルのメタデータ"""
    path: str
    relative_path: str
    title: str
    mtime: float
    size: int
    sha256: str
    text: str


def extract_title(text: str, file_stem: str) -> str:
    """
    Obsidianの仕様に基づき、ファイル名（file_stem）を主タイトルとして保持し、
    本文にH1見出しがある場合は「ファイル名 - 見出し」として抽出する。
    """
    for line in text.splitlines():
        line_strip = line.strip()
        if line_strip.startswith("# "):
            h1 = line_strip[2:].strip()
            if h1 and h1.lower() != file_stem.lower():
                return f"{file_stem} - {h1}"
            elif h1:
                return h1
    return file_stem


def calculate_sha256(content: bytes) -> str:
    """バイト列からSHA-256ハッシュ文字列を計算する"""
    return hashlib.sha256(content).hexdigest()


def scan_vault(
    vault_path: str,
    target_extensions: Optional[List[str]] = None
) -> List[DocumentMetadata]:
    """
    Vaultディレクトリを再帰的に走査し、対象拡張子のファイル情報を収集する。
    
    Args:
        vault_path: Vaultディレクトリの絶対パスまたは相対パス
        target_extensions: 対象とする拡張子リスト（例: [".md", ".txt"]）。Noneの場合はデフォルト [".md", ".markdown", ".txt"]
        
    Returns:
        収集されたDocumentMetadataのリスト
        
    Raises:
        ValueError: パスが存在しないかディレクトリでない場合
    """
    vault_p = Path(vault_path).resolve()
    if not vault_p.exists() or not vault_p.is_dir():
        raise ValueError(f"Vaultパスが無効です: {vault_path}")

    # 拡張子の正規化（例: "md" -> ".md", "TXT" -> ".txt"）
    if target_extensions:
        valid_exts = set()
        for ext in target_extensions:
            clean_ext = ext.strip().lower()
            if clean_ext:
                if not clean_ext.startswith("."):
                    clean_ext = "." + clean_ext
                valid_exts.add(clean_ext)
    else:
        valid_exts = set(DEFAULT_EXTENSIONS)

    documents: List[DocumentMetadata] = []

    for root, dirs, files in os.walk(vault_p):
        # 除外ディレクトリを探索対象から削除
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for file in files:
            file_lower = file.lower()

            # 除外ファイル接尾辞のチェック（*.excalidraw.md 等）
            if any(file_lower.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
                continue

            # 対象拡張子のチェック
            file_ext = Path(file).suffix.lower()
            if file_ext not in valid_exts:
                continue

            file_path = Path(root) / file
            rel_path = file_path.relative_to(vault_p).as_posix()

            try:
                raw_bytes = file_path.read_bytes()
                text = raw_bytes.decode("utf-8", errors="replace")
                stat = file_path.stat()

                sha256 = calculate_sha256(raw_bytes)
                title = extract_title(text, file_path.stem)

                doc = DocumentMetadata(
                    path=str(file_path),
                    relative_path=rel_path,
                    title=title,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                    sha256=sha256,
                    text=text,
                )
                documents.append(doc)
            except Exception:
                # 読み込み失敗時はスキップ
                continue

    return documents
