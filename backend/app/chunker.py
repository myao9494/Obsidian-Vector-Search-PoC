"""
Markdown チャンキング最適化モジュール
仕様:
- Markdownテキストから見出し階層（Header Breadcrumbs: # タイトル > ## セクション）を解析・保持。
- YAML Frontmatter メタデータ（tags, aliases, 検索用, category）を包括抽出・統合。
- YAML Frontmatter ヘッダー行自体の完全除去（本文のプレーン化）。
- Obsidian wikilink ([[ノート名]] や [[ノート名|表示名]]) を自然言語プレーンテキストに展開。
- 画像・描画埋め込み (![[...]] や ![...](...)) の除去。
- Excalidraw描画データ (# Excalidraw Data 以降、%%...%%、compressed-jsonブロック) の完全除去。
- 短文ノートの欠落を防止し、見出し・段落・リストの構造境界を尊重して適応的に分割。
"""

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple


@dataclass
class ChunkData:
    """チャンク情報を保持するデータクラス"""
    chunk_index: int
    text: str


@dataclass
class ExtractedMetadata:
    """Markdownから抽出されたメタデータ構造体"""
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    context_notes: List[str] = field(default_factory=list)


def extract_metadata_and_clean(
    text: str,
    glossary: Optional[Any] = None
) -> Tuple[str, ExtractedMetadata]:
    """
    MarkdownテキストからFrontmatterの各種メタデータ（tags, aliases, 検索用, category）や
    本文ハッシュタグを抽出し、ヘッダーやExcalidraw描画データを除去したクリーン本文とメタデータを返す。
    辞書（glossary）が渡された場合、本文中の専門用語から同義語・解説メタデータを自動補完する。
    """
    cleaned = text.strip()
    tags_set: Set[str] = set()
    aliases_set: Set[str] = set()
    keywords_set: Set[str] = set()
    context_notes_set: Set[str] = set()

    # 1. YAML Frontmatter の抽出と完全除去
    if cleaned.startswith("---"):
        parts = re.split(r"^---\s*$", cleaned, flags=re.MULTILINE)
        if len(parts) >= 3:
            frontmatter_content = parts[1]
            cleaned = "---".join(parts[2:]).strip()

            # ① tags の抽出
            m_tags_inline = re.search(r"^tags:\s*\[(.*?)\]", frontmatter_content, re.MULTILINE)
            if m_tags_inline:
                for t in m_tags_inline.group(1).split(","):
                    val = t.strip().strip("'\"")
                    if val:
                        tags_set.add(val)
            else:
                m_tags_block = re.search(r"^tags:\s*\n((?:\s*-\s*.+\n?)+)", frontmatter_content, re.MULTILINE)
                if m_tags_block:
                    for line in m_tags_block.group(1).splitlines():
                        val = re.sub(r"^\s*-\s*", "", line).strip().strip("'\"")
                        if val:
                            tags_set.add(val)

            # ② aliases の抽出
            m_aliases_inline = re.search(r"^aliases:\s*\[(.*?)\]", frontmatter_content, re.MULTILINE)
            if m_aliases_inline:
                for a in m_aliases_inline.group(1).split(","):
                    val = a.strip().strip("'\"")
                    if val:
                        aliases_set.add(val)
            else:
                m_aliases_block = re.search(r"^aliases:\s*\n((?:\s*-\s*.+\n?)+)", frontmatter_content, re.MULTILINE)
                if m_aliases_block:
                    for line in m_aliases_block.group(1).splitlines():
                        val = re.sub(r"^\s*-\s*", "", line).strip().strip("'\"")
                        if val:
                            aliases_set.add(val)

            # ③ 検索用 / category の抽出
            m_kw = re.search(r"^(?:検索用|keywords|category):\s*(.+)$", frontmatter_content, re.MULTILINE)
            if m_kw:
                for w in re.split(r"[\s,]+", m_kw.group(1)):
                    val = w.strip().strip("'\"")
                    if val:
                        keywords_set.add(val)

    # 2. # Excalidraw Data 以降のバイナリ・描画データを完全に切り捨て
    excal_split = re.split(r"(?i)^#+\s*Excalidraw\s+Data\b", cleaned, flags=re.MULTILINE)
    if len(excal_split) > 1:
        cleaned = excal_split[0].strip()

    # 3. Excalidraw 内部コメントブロック %% ... %% の除去
    cleaned = re.sub(r"%%.*?%%", "", cleaned, flags=re.DOTALL)

    # 4. 画像埋め込み・ファイル埋め込み ![[...]] および ![...](...) の除去
    cleaned = re.sub(r"!\[\[.*?\]\]", "", cleaned)
    cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", cleaned)

    # 5. Obsidian wikilink の展開
    cleaned = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", cleaned)

    # 6. 通常のMarkdownリンク [表示名](URL) -> 表示名 に変換
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # 7. 独立したURLの除去
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # 8. 本文中のハッシュタグ (#tag) の抽出
    for tag_match in re.findall(r"(?:^|\s)#([^\s#\.,;!?:/\\\[\]\(\)]+)", cleaned):
        if tag_match and not tag_match.startswith("#"):
            tags_set.add(tag_match)

    # 9. 行ごとのクレンジング
    lines = []
    metadata_keys = (
        "created:", "updated:", "date:", "id:", "pw:", "sha256:", "aliases:",
        "excalidraw-plugin:", "kanban-plugin:", "tags:", "検索用:", "category:"
    )
    for line in cleaned.splitlines():
        line_clean = re.sub(r"[ \t]{2,}", " ", line).strip()
        if not line_clean:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        
        lower_line = line_clean.lower()
        if any(lower_line.startswith(k) for k in metadata_keys):
            continue
        if re.match(r"^[A-Za-z0-9+/=]{30,}$", line_clean):
            continue
        if re.search(r"%[0-9A-Fa-f]{2}%[0-9A-Fa-f]{2}", line_clean) and len(line_clean) > 30:
            continue
        if re.match(r"^[:|\-\s*>`%]+$", line_clean):
            continue

        lines.append(line_clean)

    cleaned_text = "\n".join(lines).strip()

    # 10. 辞書（glossary）によるメタデータ補完（本文中の用語からaliases/context抽出）
    if glossary is not None and hasattr(glossary, "extract_enrichment_for_text"):
        dict_aliases, dict_contexts = glossary.extract_enrichment_for_text(cleaned)
        for a in dict_aliases:
            aliases_set.add(a)
        for c in dict_contexts:
            context_notes_set.add(c)

    metadata = ExtractedMetadata(
        tags=sorted(list(tags_set)),
        aliases=sorted(list(aliases_set)),
        keywords=sorted(list(keywords_set)),
        context_notes=sorted(list(context_notes_set))
    )
    return cleaned_text, metadata


def clean_markdown_text(text: str, glossary: Optional[Any] = None) -> str:
    """後方互換用クレンジング関数"""
    cleaned, _ = extract_metadata_and_clean(text, glossary=glossary)
    return cleaned


def chunk_markdown(
    text: str,
    doc_title: str = "",
    chunk_size: int = 500,
    overlap: int = 80,
    min_chunk_len: int = 15,
    glossary: Optional[Any] = None
) -> List[ChunkData]:
    """
    Markdownテキストを見出し階層・タグ・別名・キーワードメタデータを保持しながら高精度にチャンク分割する。
    辞書（glossary）が指定された場合、本文中の専門用語から同義語・解説メタデータを自動補完して各チャンクに注入する。
    """
    cleaned, metadata = extract_metadata_and_clean(text, glossary=glossary)
    
    # ノートタイトル（拡張子除去）
    base_title = re.sub(r"\.[a-zA-Z0-9]+$", "", doc_title).strip() if doc_title else ""
    
    # メタデータ統合プレフィックス文字列の構築
    meta_parts = []
    if metadata.tags:
        meta_parts.append(f"[Tags: {' '.join(['#' + t for t in metadata.tags])}]")
    if metadata.aliases:
        meta_parts.append(f"[Aliases: {' '.join(metadata.aliases)}]")
    if metadata.keywords:
        meta_parts.append(f"[Keywords: {' '.join(metadata.keywords)}]")
    if metadata.context_notes:
        meta_parts.append(f"[Context: {' '.join(metadata.context_notes[:3])}]")
    
    meta_prefix = " ".join(meta_parts).strip()

    # 空または短文テキストの救済
    if not cleaned:
        if base_title or meta_prefix:
            ctx_text = f"[{base_title}] {meta_prefix}".strip()
            return [ChunkData(chunk_index=0, text=ctx_text)]
        return []

    # 見出し記号（# 見出し）が含まれておらず、全体が chunk_size 以下の場合は1チャンクで返却
    has_headings = bool(re.search(r"^#{1,6}\s+", cleaned, re.MULTILINE))
    if not has_headings and len(cleaned) <= chunk_size:
        header_ctx = f"[{base_title}] {meta_prefix}".strip()
        full_text = f"{header_ctx}\n{cleaned}" if header_ctx else cleaned
        return [ChunkData(chunk_index=0, text=full_text)]

    # 見出し階層スタック
    header_stack: List[Tuple[int, str]] = []
    if base_title:
        header_stack.append((0, base_title))

    sections: List[Tuple[str, str]] = []
    current_lines: List[str] = []

    def get_current_context() -> str:
        h_names = [h[1] for h in header_stack]
        breadcrumbs = " > ".join(h_names)
        ctx = f"[{breadcrumbs}]"
        if meta_prefix:
            ctx += f" {meta_prefix}"
        return ctx

    for line in cleaned.splitlines():
        h_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if h_match:
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append((get_current_context(), sec_text))
                current_lines = []

            level = len(h_match.group(1))
            heading_title = h_match.group(2).strip()

            while header_stack and header_stack[-1][0] >= level:
                header_stack.pop()

            header_stack.append((level, heading_title))
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append((get_current_context(), sec_text))

    if not sections:
        header_ctx = f"[{base_title}] {meta_prefix}".strip()
        full_text = f"{header_ctx}\n{cleaned}" if header_ctx else cleaned
        return [ChunkData(chunk_index=0, text=full_text)]

    chunks: List[ChunkData] = []
    chunk_index = 0

    for ctx_prefix, sec_content in sections:
        if len(sec_content) <= chunk_size:
            chunk_text = f"{ctx_prefix}\n{sec_content}".strip()
            chunks.append(ChunkData(chunk_index=chunk_index, text=chunk_text))
            chunk_index += 1
            continue

        paragraphs = re.split(r"\n\s*\n", sec_content)
        buf = ""

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            if not buf:
                buf = p_strip
            elif len(buf) + len(p_strip) + 2 <= chunk_size:
                buf += "\n\n" + p_strip
            else:
                chunk_text = f"{ctx_prefix}\n{buf}".strip()
                chunks.append(ChunkData(chunk_index=chunk_index, text=chunk_text))
                chunk_index += 1
                
                if overlap > 0 and len(buf) > overlap:
                    buf = buf[-overlap:] + "\n\n" + p_strip
                else:
                    buf = p_strip

        if buf:
            chunk_text = f"{ctx_prefix}\n{buf}".strip()
            chunks.append(ChunkData(chunk_index=chunk_index, text=chunk_text))
            chunk_index += 1

    return chunks
