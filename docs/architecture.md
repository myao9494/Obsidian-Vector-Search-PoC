# システムアーキテクチャ & 設計ドキュメント

## 1. システム全体構成
本システムは FastAPI によるバックエンド、React (Vite) によるフロントエンド、SQLite DB、**FAISS 高速ベクトルインデックス**、および **ruri-v3-310m**（Sentence Transformers）による完全オフライン対応のベクトル検索PWAアプリケーションです。

### 構成要素
- **Vault Scanner (`scanner.py`)**: Vaultルートから再帰的に `.md` ファイルを走査。除外対象 (`.obsidian`, `.git`, `.vector_search`, `*.excalidraw.md`) をスキップし、ファイル名およびメタデータ (mtime, size, sha256) を抽出。
- **Markdown Chunker (`chunker.py`)**: 
  - 見出し階層（Header Breadcrumbs: `# タイトル > ## セクション > ### サブセクション`）をチャンクの先頭にコンテキストとして保持。
  - YAML Frontmatter の `tags:` および本文ハッシュタグ（`#tag`）を抽出・統合。
  - Obsidian wikilink (`[[ノート名|表示名]]`) の展開と不要記号・Excalidrawバイナリ等のノイズ除去。
  - 構造境界（見出し・段落・リスト）を尊重して500文字前後に分割し、短文ノートも欠落させずインデックス化。
- **SQLite Database (`db.py`)**: `<Vault>/.vector_search/index.db` に `documents` および `chunks` を永続化。
- **FAISS Vector Index (`faiss_index.py`)**: `faiss.IndexFlatIP` による C++/SIMD 最適化インメモリ高速内積検索（ミリ秒未満）。
- **Embedder (`embedder.py`)**: 
  - **ruri-v3-310m (768d)**: ModernBERT-Ja ベースの最高峰日本語SOTAモデル。8192トークン長文対応。
  - プレフィックス自動付与: 検索クエリには「`検索クエリ: `」、文書・チャンクには「`検索文書: `」を付与。
  - **ハードウェア自動検出**: Mac（Apple Silicon）では **MPS (Metal GPU)**、Windows/CPU環境では **CPU** を自動選択。
- **Index Manager (`indexer.py`)**: 差分検出（新規・変更・削除・未変更）を行い、進捗・残り時間推定を計算。
- **Vector Search Engine (`searcher.py`)**: FAISS による高速 Top-K 抽出 + 日本語形態素キーワードブースト + 反応文特定（Salient Sentence Extraction）を統合。

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

## 3. 検索パイプライン & 前後文脈抽出
1. **Query Embedding**: 入力クエリに `検索クエリ: ` を付与し、MPS/CPU で Embedding ベクトルを生成（正規化 float32）。
2. **FAISS Top-K Search**: `faiss.IndexFlatIP` で数万件のチャンクから類似度上位を 1ms 未満で抽出。
3. **Lexical / Hybrid Boost**: 日本語形態素（漢字・カタカナ・英数字）に基づくキーワード加点。
4. **Context Assembly**: 同一文書内の直前チャンク（`chunk_index - 1`）および直後チャンク（`chunk_index + 1`）を取得して文脈結合。
5. **Salient Sentence Extraction**: プレーンテキスト化・妥当性フィルタ・文単位コサイン類似度により最も関連の高い核心文を特定。
