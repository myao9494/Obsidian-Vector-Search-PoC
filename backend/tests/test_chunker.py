"""
Markdown Chunker 最適化テスト仕様
- 見出し階層（Breadcrumbs: # タイトル > ## セクション）のコンテキスト保持
- Obsidian Frontmatter タグ（tags: [A, B] や #tag）の抽出・統合
- Obsidian wikilink ([[ノート名]] や [[ノート名|別名]]) の適切なプレーンテキスト展開
- 短文ノート（タイトルとタグ・1行メモ）の確実なチャンク化（欠落防止）
- 長文ノートの構造（見出し・段落・リスト）を維持した分割
- Excalidraw描画データ (%%...%%) やBase64バイナリ行等のノイズ除去
"""

import pytest
from app.chunker import (
    chunk_markdown,
    extract_metadata_and_clean,
    ChunkData
)


def test_chunk_breadcrumbs_hierarchy():
    """見出し階層（Breadcrumbs）が各チャンクに付与されること"""
    text = """
# 投資戦略 2026

## 株式投資

### 転換社債の立ち回り
転換社債（CB）は株式に転換できる社債です。
発行発表時は希薄化懸念により一時的に株価が暴落することがあります。

### 配当金と確定申告
年間配当金が一定額を超える場合は確定申告の総合課税と申告分離課税を比較検討します。
"""
    chunks = chunk_markdown(text, doc_title="投資戦略 2026", chunk_size=300, overlap=50)
    assert len(chunks) >= 2
    
    # 最初のチャンクには「投資戦略 2026 > 株式投資 > 転換社債の立ち回り」が含まれること
    c0 = chunks[0].text
    assert "投資戦略 2026" in c0
    assert "転換社債の立ち回り" in c0
    assert "希薄化懸念" in c0

    # 2つ目のチャンクには「配当金と確定申告」の階層が含まれること
    c1 = chunks[1].text
    assert "配当金と確定申告" in c1
    assert "総合課税" in c1


def test_chunk_frontmatter_tags_integration():
    """Frontmatterのタグや本文のハッシュタグが抽出・活用されること"""
    text = """---
created: 2026-01-10 10:07:18
tags:
  - 学校
  - 吹奏楽
  - 楽器
  - クラリネット
---

# 購入したところ

[管楽器専門店|バルドン・フィルステージ|ヨモギヤ楽器（株）](https://www.bardon.co.jp/)
"""
    cleaned, tags = extract_metadata_and_clean(text)
    assert "学校" in tags
    assert "吹奏楽" in tags
    assert "クラリネット" in tags
    assert "created:" not in cleaned
    assert "bardon.co.jp" not in cleaned  # URLは除去
    assert "管楽器専門店" in cleaned or "バルドン" in cleaned

    chunks = chunk_markdown(text, doc_title="クラリネット.md", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    # チャンクにタグと店舗名が含まれていること
    assert "クラリネット" in chunks[0].text
    assert "吹奏楽" in chunks[0].text or "バルドン" in chunks[0].text


def test_chunk_wikilinks_expansion():
    """Obsidianのwikilink ([[ノート名]] や [[ノート名|エイリアス]]) が適切に処理されること"""
    text = """
# 確定申告の手順

- 詳細は [[確定申告_2025]] を参照。
- [[ふるさと納税|ふるさと納税の限度額計算]] も確認すること。
"""
    chunks = chunk_markdown(text, doc_title="確定申告", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    # wikilink のブラケットが除去され自然な文章になっていること
    assert "確定申告_2025" in chunks[0].text
    assert "ふるさと納税の限度額計算" in chunks[0].text
    assert "[[" not in chunks[0].text


def test_chunk_short_note_preservation():
    """短文ノートでも欠落せず、タイトルやタグと一体となってチャンク化されること"""
    text = """---
tags:
  - クーポン
  - 優待
---
# QUOカード銘柄
3353 メディカル一光
"""
    chunks = chunk_markdown(text, doc_title="QUOカード銘柄.md", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert "QUOカード銘柄" in chunks[0].text
    assert "メディカル一光" in chunks[0].text
    assert "優待" in chunks[0].text or "クーポン" in chunks[0].text


def test_chunk_excalidraw_noise_removal():
    """Excalidrawの内部コメント (%%...%%) やBase64等のノイズが除去されること"""
    text = """
# アーキテクチャ図

以下はシステムの構成図です。

%%
# Excalidraw Data
{"type": "excalidraw", "version": 2, "elements": [{"id": "abc12345", "type": "rectangle"}]}
%%

実際のコンポーネントはFastAPIとReactで構成されます。
"""
    chunks = chunk_markdown(text, doc_title="構成図", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert "FastAPIとReact" in chunks[0].text
    assert "excalidraw" not in chunks[0].text.lower()
    assert "abc12345" not in chunks[0].text
