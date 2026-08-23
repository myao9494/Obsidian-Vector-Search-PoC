"""
Obsidian Vault スキャナーモジュール
仕様:
- 指定されたObsidian VaultディレクトリからすべてのMarkdownファイル（*.md）を再帰的に収集する。
- .obsidian, .git, .vector_search などの隠し/管理ディレクトリは除外する。
- 各ファイルについて相対パス、絶対パス、タイトル（先頭見出しまたはファイル名）、更新日時（mtime）、ファイルサイズ、SHA-256ハッシュ、本文テキストを取得する。
"""

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

EXCLUDED_DIRS = {".obsidian", ".git", ".vector_search"}


@dataclass
class DocumentMetadata:
    """文書のメタデータおよび本文を保持するデータクラス"""
    path: str
    relative_path: str
    title: str
    mtime: float
    size: int
    sha256: str
    text: str


def extract_title(text: str, file_stem: str) -> str:
    """
    本文からH1タイトル（# タイトル）を抽出する。
    見つからない場合はファイル名（拡張子なし）を返す。
    """
    for line in text.splitlines():
        line_strip = line.strip()
        if line_strip.startswith("# "):
            title = line_strip[2:].strip()
            if title:
                return title
    return file_stem


def calculate_sha256(content: bytes) -> str:
    """バイト列からSHA-256ハッシュ文字列を計算する"""
    return hashlib.sha256(content).hexdigest()


def scan_vault(vault_path: str) -> List[DocumentMetadata]:
    """
    Vaultディレクトリを再帰的に走査し、対象のMarkdownファイル情報を収集する。
    
    Args:
        vault_path: Vaultディレクトリの絶対パスまたは相対パス
        
    Returns:
        収集されたDocumentMetadataのリスト
        
    Raises:
        ValueError: パスが存在しないかディレクトリでない場合
    """
    vault_p = Path(vault_path).resolve()
    if not vault_p.exists() or not vault_p.is_dir():
        raise ValueError(f"Vaultパスが無効です: {vault_path}")

    documents: List[DocumentMetadata] = []

    for root, dirs, files in os.walk(vault_p):
        # 除外ディレクトリを探索対象から削除
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for file in files:
            if not file.lower().endswith(".md"):
                continue
            if file.lower().endswith(".excalidraw.md"):
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
            except Exception as e:
                # 読み込み失敗時はスキップまたはログ記録
                continue

    return documents
