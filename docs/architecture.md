# システムアーキテクチャ & 設計ドキュメント

## 1. システム全体構成
本システムは FastAPI によるバックエンド、React (Vite) によるフロントエンド、SQLite DB、**FAISS 高速ベクトルインデックス**、および **ruri-v3 シリーズ（310M / 30M）**（Sentence Transformers）による完全オフライン対応のベクトル検索PWAアプリケーションです。
将来的なキーワード検索リポジトリ (`Local-fulltext-search`) との統合を見据え、プロトコルやAPIインターフェースの互換性を確保しています。

### 構成要素
- **Vault Scanner (`scanner.py`)**:
  - Vaultルートから再帰的にファイルを走査。
  - **対象拡張子の動的指定**: `.md`, `.markdown`, `.txt` などをUI/APIから指定可能。
  - **除外ルール**: `.obsidian`, `.git`, `.vector_search`, `*.excalidraw.md`, `*.canvas`, `*.drawio.svg` を自動スキップ。
  - ファイル名（stem）を主タイトルとして確実に保持し、メタデータ (mtime, size, sha256) を抽出。
- **Markdown Chunker (`chunker.py`)**: 
  - **見出し階層 (Header Breadcrumbs)**: `# タイトル > ## セクション > ### サブセクション` をチャンクの先頭にコンテキストとして保持。
  - **YAML Frontmatter / ヘッダーの除去**: `created:`, `updated:`, `excalidraw-plugin:` 等のメタデータブロックを本文から完全に除外。タグのみ抽出して `[Tags: #A #B]` として保持。
  - **Excalidraw 描画データ (# Excalidraw Data 以降) の完全切り捨て**: 図面のバイナリ・JSONデータ（compressed-json等）や画像埋め込み（`![[...]]`）を徹底除去。
  - **Obsidian wikilink (`[[ノート名|表示名]]`) の展開** と不要記号・長大URLの除去。
  - 構造境界（見出し・段落・リスト）を尊重して500文字前後に分割し、短文ノートも欠落させずインデックス化。
- **SQLite Database (`db.py`)**: `<Vault>/.vector_search/index.db` に `documents` および `chunks` を永続化。
- **FAISS Vector Index (`faiss_index.py`)**: `faiss.IndexFlatIP` による C++/SIMD 最適化インメモリ高速内積検索（ミリ秒未満）。
- **Embedder (`embedder.py`)**: 
  - **ruri-v3-310m (768d)**: ModernBERT-Ja ベースの日本語SOTA標準・高精度モデル。
  - **ruri-v3-30m (256d)**: Windows 一般CPUでも ~60ms で動作する超軽量・超高速モデル。
  - プレフィックス自動付与: 検索クエリには「`検索クエリ: `」、文書・チャンクには「`検索文書: `」を付与。
  - **ハードウェア自動検出**: Mac（Apple Silicon）では **MPS (Metal GPU)**、Windows/CPU環境では **CPU (SIMD並列)** を自動選択。
- **Index Manager & Incremental Updater (`indexer.py`)**:
  - 全体差分インデックス（新規・変更・削除・未変更の検出）。
  - **単一ファイル高速差分更新 (`SingleFileUpdate`)**: 変更された1ファイルのみをミリ秒単位で再Embedding & DB/FAISS反映。
- **Glossary Dictionary (`dictionary.py`)**:
  - 新2列フォーマット（第1列: 専門用語（カンマ区切り）, 第2列: 意味・解説）および従来の3列フォーマットの自動認識。
  - **SHA-256ハッシュ & mtime差分検知キャッシュ**: 通常検索時のExcel I/O負荷を完全ゼロ化。ファイル保存時のみ自動再ロード。
  - 自然文クエリ補強（Query Enrichment）およびチャンクメタデータ自動注入（Chunk Enrichment）。
  - Web UIモーダルエディタからのExcel直接生成・保存。
- **Vector Search Engine (`searcher.py`)**:
  - **スコアキャリブレーション & ノイズフロア除去**: 無関係テキストの生内積（0.70未満）を急峻にカットし、真の合致文書（0.70〜0.98）と無関係なゴミ（0.00〜0.25）の間に明確なスコア差（マージン）を創出。
  - FAISS による高速 Top-K 抽出 + 日本語形態素キーワードブースト + 反応文特定（Salient Sentence Extraction）を統合。
  - `SearchResultItem` に絶対パス `full_path` を自動付与。
- **Open Hub & Native File Integration (`main.py`)**:
  - 外部Open Hub（8001番）への307リダイレクト (`GET /api/open/file`)。
  - OSネイティブ保存場所表示 (`POST /api/files/open-location`: macOS Finder / Windows Explorer)。

---

## 2. データモデル (SQLite)

### `documents` テーブル
| カラム名 | 型 | 説明 |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | 文書ID |
| `path` | TEXT UNIQUE NOT NULL | Vault内相対パス |
| `title` | TEXT | 文書タイトル（ファイル名および見出し） |
| `mtime` | REAL NOT NULL | 最終更新日時 (epoch) |
| `size` | INTEGER NOT NULL | ファイルサイズ (バイト) |
| `sha256` | TEXT NOT NULL | ファイルハッシュ |
| `text` | TEXT | ノート全文（Document検索用/プレビュー用） |
| `embedding` | BLOB | ノート全体のEmbedding (float32) |
| `indexed_at` | REAL | インデックス完了日時 |

### `chunks` テーブル
| カラム名 | 型 | 説明 |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | チャンクID |
| `document_id` | INTEGER NOT NULL | 親文書ID (FK) |
| `chunk_index` | INTEGER NOT NULL | 文書内チャンク連番 (0-indexed) |
| `text` | TEXT NOT NULL | チャンク本文（階層見出し・タグ・辞書メタデータ付き） |
| `embedding` | BLOB NOT NULL | チャンクのEmbedding (float32) |
| `embedding_dim` | INTEGER NOT NULL | ベクトルの次元数 (768 or 256) |
