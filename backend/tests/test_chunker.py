"""
Markdown Chunker のテスト仕様
- 見出し・段落境界を尊重しつつ、指定されたサイズ（500〜800文字）とオーバーラップ（50〜100文字）でチャンク分割を行うこと。
- 短い文書の場合は分割されずに1つのチャンクとして返されること。
- 長い文書の場合は適切なサイズとオーバーラップを維持して分割されること。
- チャンクインデックス（0-indexed）およびテキスト内容が正確に保持されること。
"""

import pytest
from app.chunker import chunk_markdown, ChunkData


def test_chunk_short_document():
    """短い文書（chunk_size以下）の場合、1つのチャンクになること"""
    text = "# Title\n\nThis is a short note content."
    chunks = chunk_markdown(text, chunk_size=500, overlap=50)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == text


def test_chunk_empty_document():
    """空の文書の場合、空リストが返ること"""
    assert chunk_markdown("", chunk_size=500, overlap=50) == []
    assert chunk_markdown("   \n\n  ", chunk_size=500, overlap=50) == []


def test_chunk_long_document_with_paragraphs():
    """
    段落区切りを含む長文が複数チャンクに分割され、
    オーバーラップが含まれ、インデックスが0から順に付与されること
    """
    # 200文字の段落を6個作成（計約1200文字）
    paragraphs = [f"Section {i}: " + ("A" * 180) for i in range(6)]
    text = "\n\n".join(paragraphs)

    chunk_size = 500
    overlap = 100
    chunks = chunk_markdown(text, chunk_size=chunk_size, overlap=overlap)

    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert len(c.text) > 0
        assert len(c.text) <= chunk_size + 200  # 段落境界の余裕を考慮

    # 連続するチャンク間でオーバーラップ（前のチャンクの一部が次のチャンクに含まれる）が存在すること
    has_overlap = False
    for i in range(len(chunks) - 1):
        c1_tail = chunks[i].text[-50:]
        if c1_tail in chunks[i + 1].text:
            has_overlap = True
            break
    assert has_overlap


def test_chunk_headings_preservation():
    """見出し（# Heading）で適切に区切られること"""
    text = (
        "# Heading 1\n\n" + ("Content under h1. " * 30) + "\n\n"
        "## Heading 2\n\n" + ("Content under h2. " * 30) + "\n\n"
        "### Heading 3\n\n" + ("Content under h3. " * 30)
    )

    chunks = chunk_markdown(text, chunk_size=400, overlap=50)
    assert len(chunks) >= 3
    # 見出しが含まれていること
    all_chunk_text = " ".join([c.text for c in chunks])
    assert "Heading 1" in all_chunk_text
    assert "Heading 2" in all_chunk_text
    assert "Heading 3" in all_chunk_text
