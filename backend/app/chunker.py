"""
Markdown チャンキングモジュール
仕様:
- Markdownテキストを見出しや段落（空行）の境界を考慮しながら、500〜800文字程度（初期値500、オーバーラップ50〜100文字）に分割する。
- チャンクの通番（chunk_index: 0から始まる連番）とテキスト内容を格納したChunkDataリストを返す。
- 空文字列や空白のみのテキストの場合は空リストを返す。
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class ChunkData:
    """チャンク情報を保持するデータクラス"""
    chunk_index: int
    text: str


def clean_markdown_text(text: str) -> str:
    """
    MarkdownテキストからYAML Frontmatter（--- ... ---）や過剰な空行を除去する
    """
    cleaned = text.strip()
    # YAML Frontmatterの除去
    if cleaned.startswith("---"):
        parts = re.split(r"^---\s*$", cleaned, flags=re.MULTILINE)
        if len(parts) >= 3:
            cleaned = "---".join(parts[2:]).strip()
    return cleaned


def chunk_markdown(
    text: str,
    chunk_size: int = 600,
    overlap: int = 80,
    min_chunk_len: int = 30
) -> List[ChunkData]:
    """
    Markdownテキストをチャンク分割する。
    
    Args:
        text: 分割対象のMarkdown文字列
        chunk_size: 1チャンクあたりの目標最大文字数（デフォルト600）
        overlap: チャンク間の重複文字数（デフォルト80）
        min_chunk_len: チャンクの最小文字数（極小ノイズ除外）
        
    Returns:
        ChunkDataのリスト
    """
    cleaned = clean_markdown_text(text)
    if not cleaned or len(cleaned) < min_chunk_len:
        if cleaned:
            return [ChunkData(chunk_index=0, text=cleaned)]
        return []

    # 全体がchunk_size以下の場合はそのまま1チャンクとして返却
    if len(cleaned) <= chunk_size:
        return [ChunkData(chunk_index=0, text=cleaned)]

    # 段落（空行）または見出しで行をグループ化
    # 見出し行 (# ...) または 空行の直後で分割候補とする
    blocks = re.split(r"(\n\s*\n|(?<=\n)(?=#+\s))", cleaned)
    
    # 分割されたブロックを結合して平坦化
    atomic_units: List[str] = []
    current_unit = ""
    for block in blocks:
        if not block:
            continue
        if block.strip() == "":
            current_unit += block
        else:
            if current_unit:
                atomic_units.append(current_unit)
                current_unit = ""
            # 単一ブロックがchunk_sizeを超える場合は文単位等で分割
            if len(block) > chunk_size:
                # 句点や改行でさらに分割
                sub_parts = re.split(r"([。\n\.\?!]+)", block)
                sub_accum = ""
                for part in sub_parts:
                    if len(sub_accum) + len(part) > chunk_size and sub_accum:
                        atomic_units.append(sub_accum)
                        sub_accum = part
                    else:
                        sub_accum += part
                if sub_accum:
                    atomic_units.append(sub_accum)
            else:
                atomic_units.append(block)

    if current_unit:
        atomic_units.append(current_unit)

    # atomic_units を chunk_size & overlap に応じて結合
    chunks: List[ChunkData] = []
    chunk_index = 0
    i = 0
    n = len(atomic_units)

    while i < n:
        chunk_text = ""
        start_i = i
        
        while i < n:
            next_unit = atomic_units[i]
            if len(chunk_text) + len(next_unit) > chunk_size and chunk_text:
                break
            chunk_text += next_unit
            i += 1

        chunk_text_stripped = chunk_text.strip()
        if chunk_text_stripped:
            chunks.append(ChunkData(chunk_index=chunk_index, text=chunk_text_stripped))
            chunk_index += 1

        if i >= n:
            break

        # オーバーラップのために i を少し巻き戻す
        overlap_accum = 0
        back_i = i - 1
        while back_i > start_i and overlap_accum < overlap:
            overlap_accum += len(atomic_units[back_i])
            back_i -= 1

        i = max(back_i + 1, start_i + 1)

    return chunks
