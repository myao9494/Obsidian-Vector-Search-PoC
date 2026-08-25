# システムアーキテクチャ & 設計ドキュメント

## 1. システム全体構成
本システムは FastAPI によるバックエンド、React (Vite) によるフロントエンド、SQLite DB、**FAISS 高速ベクトルインデックス**、および **ruri-v3-310m**（Sentence Transformers）による完全オフライン対応のベクトル検索PWAアプリケーションです。

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
  - **ruri-v3-310m (768d)**: ModernBERT-Ja ベースの日本語SOTAモデル。
  - プレフィックス自動付与: 検索クエリには「`検索クエリ: `」、文書・チャンクには「`検索文書: `」を付与。
  - **ハードウェア自動検出**: Mac（Apple Silicon）では **MPS (Metal GPU)**、Windows/CPU環境では **CPU (SIMD並列)** を自動選択。
- **Index Manager (`indexer.py`)**: 差分検出（新規・変更・削除・未変更）を行い、進捗・残り時間推定を計算。
- **Vector Search Engine (`searcher.py`)**:
  - **スコアキャリブレーション & ノイズフロア除去**: 無関係テキストの生内積（0.70未満）を急峻にカットし、真の合致文書（0.70〜0.98）と無関係なゴミ（0.00〜0.25）の間に明確なスコア差（マージン）を創出。
  - FAISS による高速 Top-K 抽出 + 日本語形態素キーワードブースト + 反応文特定（Salient Sentence Extraction）を統合。

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
| `text` | TEXT NOT NULL | チャンク本文（階層見出し・タグ付き） |
| `embedding` | BLOB NOT NULL | チャンクのEmbedding (float32) |
| `embedding_dim` | INTEGER NOT NULL | ベクトルの次元数 |
