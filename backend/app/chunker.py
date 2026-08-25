"""
Markdown チャンキング最適化モジュール
仕様:
- Markdownテキストから見出し階層（Header Breadcrumbs: # タイトル > ## セクション）を解析・保持。
- YAML Frontmatter および本文中の Obsidian タグ（tags: や #tag）を抽出・統合。
- Obsidian wikilink ([[ノート名]] や [[ノート名|表示名]]) を自然言語プレーンテキストに展開。
- Excalidraw描画データ (%%...%%)、Base64バイナリ行、長大URLパラメータ等のノイズを徹底除去。
- 短文ノートの欠落を防止し、見出し・段落・リストの構造境界を尊重して500文字前後に分割。
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple


@dataclass
class ChunkData:
    """チャンク情報を保持するデータクラス"""
    chunk_index: int
    text: str


def extract_metadata_and_clean(text: str) -> Tuple[str, List[str]]:
    """
    MarkdownテキストからFrontmatterのタグや本文のハッシュタグを抽出し、
    ノイズを除去したクリーンな本文とタグリストを返す。
    
    Returns:
        (cleaned_text, tags_list)
    """
    cleaned = text.strip()
    tags_set: Set[str] = set()

    # 1. YAML Frontmatter の抽出と除去
    if cleaned.startswith("---"):
        parts = re.split(r"^---\s*$", cleaned, flags=re.MULTILINE)
        if len(parts) >= 3:
            frontmatter_content = parts[1]
            cleaned = "---".join(parts[2:]).strip()

            # Frontmatter 内の tags 抽出
            # tags: [tag1, tag2] 形式
            m_inline = re.search(r"^tags:\s*\[(.*?)\]", frontmatter_content, re.MULTILINE)
            if m_inline:
                for t in m_inline.group(1).split(","):
                    val = t.strip().strip("'\"")
                    if val:
                        tags_set.add(val)
            else:
                # tags: \n  - tag1 \n  - tag2 形式
                m_block = re.search(r"^tags:\s*\n((?:\s*-\s*.+\n?)+)", frontmatter_content, re.MULTILINE)
                if m_block:
                    for line in m_block.group(1).splitlines():
                        val = re.sub(r"^\s*-\s*", "", line).strip().strip("'\"")
                        if val:
                            tags_set.add(val)

    # 2. Excalidraw 内部コメントブロック %% ... %% の除去
    cleaned = re.sub(r"%%.*?%%", "", cleaned, flags=re.DOTALL)

    # 3. Obsidian wikilink の展開
    # [[ノート名|表示名]] -> 表示名
    cleaned = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", cleaned)

    # 4. 通常のMarkdownリンク [表示名](URL) -> 表示名 に変換 (URLは除外)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # 5. 独立したURLの除去
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # 6. 画像・描画埋め込み ![[...]] の除去
    cleaned = re.sub(r"!\[\[[^\]]+\]\]", "", cleaned)

    # 7. 本文中のハッシュタグ (#tag) の抽出
    for tag_match in re.findall(r"(?:^|\s)#([^\s#\.,;!?:/\\\[\]\(\)]+)", cleaned):
        # 見出し記号と混同しないようにチェック
        if tag_match and not tag_match.startswith("#"):
            tags_set.add(tag_match)

    # 8. 行ごとのクレンジング
    lines = []
    metadata_keys = ("created:", "updated:", "date:", "id:", "pw:", "sha256:", "aliases:")
    for line in cleaned.splitlines():
        line_clean = re.sub(r"[ \t]{2,}", " ", line).strip()
        if not line_clean:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        
        lower_line = line_clean.lower()
        # メタデータ行のスキップ
        if any(lower_line.startswith(k) for k in metadata_keys):
            continue
        # Base64 や URLエンコード残骸のスキップ
        if re.match(r"^[A-Za-z0-9+/=]{30,}$", line_clean):
            continue
        if re.search(r"%[0-9A-Fa-f]{2}%[0-9A-Fa-f]{2}", line_clean) and len(line_clean) > 30:
            continue
        if re.match(r"^[:|\-\s*>`%]+$", line_clean):
            continue

        lines.append(line_clean)

    cleaned_text = "\n".join(lines).strip()
    return cleaned_text, sorted(list(tags_set))


def clean_markdown_text(text: str) -> str:
    """後方互換用クレンジング関数"""
    cleaned, _ = extract_metadata_and_clean(text)
    return cleaned


def chunk_markdown(
    text: str,
    doc_title: str = "",
    chunk_size: int = 500,
    overlap: int = 80,
    min_chunk_len: int = 15
) -> List[ChunkData]:
    """
    Markdownテキストを見出し階層・タグ情報を保持しながら高精度にチャンク分割する。
    
    Args:
        text: 分割対象のMarkdown文字列
        doc_title: ドキュメントタイトル（ファイル名等）
        chunk_size: 1チャンクあたりの目標文字数
        overlap: チャンク間の重複文字数
        min_chunk_len: チャンクの最小文字数
        
    Returns:
        ChunkDataのリスト
    """
    cleaned, tags = extract_metadata_and_clean(text)
    
    # ノートタイトル（拡張子除去）
    base_title = re.sub(r"\.md$", "", doc_title).strip() if doc_title else ""
    
    # タグプレフィックス文字列
    tags_prefix = f"[Tags: {' '.join(['#' + t for t in tags])}]" if tags else ""

    # 本文が極めて短い場合の救済処理
    if not cleaned or len(cleaned) < min_chunk_len:
        if cleaned or tags or base_title:
            parts = []
            if base_title:
                parts.append(f"# {base_title}")
            if tags_prefix:
                parts.append(tags_prefix)
            if cleaned:
                parts.append(cleaned)
            content = "\n\n".join(parts).strip()
            if content:
                return [ChunkData(chunk_index=0, text=content)]
        return []

    # 行ごとに見出し階層を追跡しながらセクションブロックを構築
    sections: List[Tuple[List[str], str]] = []  # (breadcrumb_hierarchy, section_text)
    current_hierarchy: List[str] = [base_title] if base_title else []
    current_lines: List[str] = []

    heading_regex = re.compile(r"^(#{1,6})\s+(.+)$")

    for line in cleaned.splitlines():
        h_match = heading_regex.match(line)
        if h_match:
            # 既存の蓄積行があればセクションとして保存
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append((list(current_hierarchy), sec_text))
                current_lines = []

            h_level = len(h_match.group(1))  # 1 for #, 2 for ##, etc.
            h_text = h_match.group(2).strip()

            # 階層の更新
            base_offset = 1 if base_title else 0
            target_depth = (h_level - 1) + base_offset
            
            if target_depth < len(current_hierarchy):
                current_hierarchy = current_hierarchy[:target_depth]
            
            # 見出しを追加
            current_hierarchy.append(h_text)
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append((list(current_hierarchy), sec_text))

    # 各セクションをチャンク化
    chunks: List[ChunkData] = []
    chunk_index = 0

    for hierarchy, sec_text in sections:
        # コンテキストヘッダーの生成
        breadcrumb_str = " > ".join(hierarchy) if hierarchy else ""
        header_parts = []
        if breadcrumb_str:
            header_parts.append(f"[{breadcrumb_str}]")
        if tags_prefix:
            header_parts.append(tags_prefix)
        
        context_header = " ".join(header_parts)
        effective_chunk_size = max(chunk_size - len(context_header) - 10, 200)

        # セクション内が effective_chunk_size 以下ならそのまま1チャンク
        if len(sec_text) <= effective_chunk_size:
            full_text = f"{context_header}\n{sec_text}" if context_header else sec_text
            chunks.append(ChunkData(chunk_index=chunk_index, text=full_text.strip()))
            chunk_index += 1
            continue

        # セクション内を段落・リスト・文単位で分割
        blocks = re.split(r"(\n\s*\n|(?<=\n)(?=[-*\d]\s))", sec_text)
        atomic_units: List[str] = []
        for blk in blocks:
            if not blk:
                continue
            if len(blk) > effective_chunk_size:
                sub_parts = re.split(r"([。\n\.\?!]+)", blk)
                accum = ""
                for sp in sub_parts:
                    if len(accum) + len(sp) > effective_chunk_size and accum:
                        atomic_units.append(accum)
                        accum = sp
                    else:
                        accum += sp
                if accum:
                    atomic_units.append(accum)
            else:
                atomic_units.append(blk)

        i = 0
        n = len(atomic_units)
        while i < n:
            chunk_body = ""
            start_i = i
            while i < n:
                next_u = atomic_units[i]
                if len(chunk_body) + len(next_u) > effective_chunk_size and chunk_body:
                    break
                chunk_body += next_u
                i += 1

            chunk_body_str = chunk_body.strip()
            if chunk_body_str:
                full_text = f"{context_header}\n{chunk_body_str}" if context_header else chunk_body_str
                chunks.append(ChunkData(chunk_index=chunk_index, text=full_text.strip()))
                chunk_index += 1

            if i >= n:
                break

            # オーバーラップ処理
            overlap_accum = 0
            back_i = i - 1
            while back_i > start_i and overlap_accum < overlap:
                overlap_accum += len(atomic_units[back_i])
                back_i -= 1
            i = max(back_i + 1, start_i + 1)

    # 1件も生成されなかった場合のフォールバック
    if not chunks:
        parts = []
        if base_title:
            parts.append(f"# {base_title}")
        if tags_prefix:
            parts.append(tags_prefix)
        if cleaned:
            parts.append(cleaned)
        content = "\n\n".join(parts).strip()
        if content:
            chunks.append(ChunkData(chunk_index=0, text=content))

    return chunks
