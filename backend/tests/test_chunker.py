"""
Markdown Chunker 最適化テスト仕様
- 見出し階層（Breadcrumbs: # タイトル > ## セクション）のコンテキスト保持
- Obsidian Frontmatter メタデータ（tags, aliases, 検索用, category）の抽出・統合
- Obsidian wikilink ([[ノート名]] や [[ノート名|別名]]) の適切なプレーンテキスト展開
- 短文ノート（タイトルとタグ・1行メモ）の確実なチャンク化（欠落防止）
- 長文ノートの構造（見出し・段落・リスト）を維持した分割
- Excalidraw描画データ (# Excalidraw Data 以降、%%...%%、埋め込み ![[...]]) の完全除去
- YAML Frontmatter ヘッダーの除去
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

管楽器専門店|バルドン・フィルステージ|ヨモギヤ楽器（株）
"""
    chunks = chunk_markdown(text, doc_title="クラリネット.md", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert "ヨモギヤ楽器" in chunks[0].text
    assert "クラリネット" in chunks[0].text
    assert "吹奏楽" in chunks[0].text
    assert "created:" not in chunks[0].text


def test_chunk_full_metadata_integration():
    """tags, aliases, 検索用, category などの各種メタデータが包括的に抽出・埋め込まれること"""
    text = """---
created: 2025-11-28 10:00:00
tags:
  - 投資
  - 株式
aliases:
  - CB
  - 転換社債
検索用: 新株予約権付社債 エクイティファイナンス
category: ファイナンス
---

# 転換社債とは
株式と債券の両方の性質を持つ金融商品です。
"""
    chunks = chunk_markdown(text, doc_title="転換社債（CB）.md", chunk_size=500, overlap=50)
    assert len(chunks) == 1
    c_text = chunks[0].text
    assert "Tags: #投資 #株式" in c_text
    assert "Aliases: CB 転換社債" in c_text or "CB" in c_text
    assert "新株予約権付社債" in c_text or "ファイナンス" in c_text
    assert "created:" not in c_text


def test_chunk_wikilink_expansion():
    """Obsidianのwikilinkが自然なプレーンテキストに展開されること"""
    text = """
# 確定申告の手順

- 詳細は [[確定申告_2025]] を参照。
- [[ふるさと納税|ふるさと納税の限度額計算]] も確認すること。
"""
    chunks = chunk_markdown(text, doc_title="確定申告", chunk_size=500, overlap=50)
    assert len(chunks) == 1
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


def test_chunk_excalidraw_data_section_removal():
    """# Excalidraw Data 以降のバイナリ・図面データおよび画像埋め込みが完全に除去されること（りんご.mdサンプル）"""
    text = """---
created: 2026-08-15 09:10:23
tags:
  - excalidraw
excalidraw-plugin: parsed
---

![[りんご|75]]
# 本文タイトル

ここに本物のテキストメモがあります。
りんごの美味しい食べ方について。

![[Pasted image 20260816102040.png|409]]
![[あは.excalidraw.md|275]]
![[いいい.drawio.svg|221]]

# Excalidraw Data

## Text Elements
%%
## Drawing
```compressed-json
N4KAkARALgngDgUwgLgAQQQDwMYEMA2AlgCYBOuA7hADTgQBuCpAzoQPYB2KqATLZMzYBXUtiRoIACyhQ4zZAHoFAc0JRJQgEYA6bGwC2CgF7N6hbEcK4OCtptbErHALRY8RMpWdx8Q1TdIEfARcZgRmBShcZQUebR4ANm0AFho6IIR9BA4oZm4AbXAwUDBSiBJuCAB5CmIALQBxAAkAdjY00shYREqgojkkfjLMbmcARgSADm0WgGYWgE5kgFZV
```
%%
"""
    cleaned, metadata = extract_metadata_and_clean(text)
    
    assert "ここに本物のテキストメモがあります" in cleaned
    assert "りんごの美味しい食べ方" in cleaned
    assert "Excalidraw Data" not in cleaned
    assert "compressed-json" not in cleaned
    assert "N4KAkARALg" not in cleaned
    assert "Drawing" not in cleaned
    assert "Pasted image" not in cleaned
    assert "drawio" not in cleaned
    assert "excalidraw-plugin" not in cleaned
    assert "created:" not in cleaned
