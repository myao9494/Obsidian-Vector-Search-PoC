# システムアーキテクチャ & 設計ドキュメント

## 1. システム全体構成
本システムは FastAPI によるバックエンド、React (Vite) によるフロントエンド、SQLite DB、および Sentence Transformers (ローカルロード) によるオフラインベクトル検索エンジンで構成されます。

### 構成要素
- **Vault Scanner**: Vaultルートから再帰的に `.md` ファイルを走査。除外対象 (`.obsidian`, `.git`, `.vector_search`) をスキップし、メタデータ (mtime, size, sha256) を抽出。
- **Markdown Chunker**: 見出し・段落区切りを意識しつつ、500〜800文字（オーバーラップ50〜100文字）でテキストを分割。前後文脈のインデックスを保持。
- **SQLite Database**: `<Vault>/.vector_search/index.db` に `documents` および `chunks` を永続化。
- **Embedder**: SentenceTransformers をローカルパスから読み込み、正規化された float32 ベクトル (BLOB) を生成。
- **Index Manager**: 差分検出（新規・変更・削除・未変更）を行い、進捗・残り時間推定を計算。
- **Vector Search Engine**: メモリ上にロードされたベクトル行列とクエリベクトルとの NumPy コサイン類似度全件比較 (`scores = embeddings @ query_vec`) を実施。

## 2. データモデル (SQLite)

### `documents` テーブル
| カラム名 | 型 | 説明 |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | 文書ID |
| `path` | TEXT UNIQUE NOT NULL | Vault内相対/絶対パス |
| `title` | TEXT | 文書タイトル（ファイル名または先頭見出し） |
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
| `text` | TEXT NOT NULL | チャンク本文 |
| `embedding` | BLOB NOT NULL | チャンクのEmbedding (float32) |
| `embedding_dim` | INTEGER NOT NULL | ベクトルの次元数 |

## 3. 検索ロジック & 前後文脈抽出
- **Document検索**: クエリEmbeddingと全ノートEmbeddingのコサイン類似度を計算し Top K を返却。
- **Chunk検索**: クエリEmbeddingと全チャンクEmbeddingのコサイン類似度を計算。
  - 上位チャンク取得時、同一文書内の直前チャンク（`chunk_index - 1`）および直後チャンク（`chunk_index + 1`）を取得して文脈結合表示。
- **速度分離計測**:
  - `embedding_time_ms`: クエリのEmbedding生成時間
  - `search_time_ms`: 行列演算（コサイン類似度計算）時間
