# Obsidian Vector Search PoC 仕様書

## 1. 概要
本システムは、ローカルPC上のObsidian Vault全体をインデックス化し、自然言語による質問から意味的に関連するMarkdown文書・チャンクをNumPyコサイン類似度により検索する技術検証用PoC（Proof of Concept）である。

## 2. 主要機能
1. **Vault走査 (Scanner)**: Vault内の `*.md` を再帰的に探索（`.obsidian`, `.git`, `.vector_search`, `*.excalidraw.md` は除外）。
2. **チャンク分割 & クレンジング (Chunker)**:
   - YAML Frontmatter（`--- ... ---`）の自動除外。
   - 見出し・段落境界を尊重しつつ500〜800文字で分割（極小ノイズチャンクは除外）。
3. **SQLite永続化 (DB)**: `<Vault>/.vector_search/index.db` に文書およびチャンク・Embeddingを保存。
4. **ローカルEmbedding (Embedder)**: Sentence Transformersを使用し、ローカルパスからのみロード（完全オフライン）。
   - **Multilingual E5 Base (768d)**: 速度・精度ベストバランス（~0.1s）
   - **BGE-M3 (1024d)**: 最高峰の多言語・日本語SOTAモデル（8192トークン長文対応）
   - **Multilingual E5 Large (1024d)**: E5大型版（~0.4s）
   - **Multilingual E5 Small (384d)**: 超高速版（~0.03s）
5. **差分インデックス & モデル自動マイグレーション (Indexer)**:
   - `path`, `mtime`, `size`, `sha256` を用いた差分更新。
   - モデル次元数変更時の自動クリア・再インデックス検知。
   - 全件強制再構築（Clean Re-index）オプション。
6. **高精度ベクトル検索 & 反応文特定 (Searcher)**:
   - **Document検索**: 1ノート = 1 Embeddingによる文書単位検索。プレビュー表示。
   - **Chunk検索**: チャンク単位の類似度検索。ヒット文章および前後文脈（前/ヒット/後）を表示。
   - **🎯 キーワード一致ブースト (Lexical/Hybrid Boost)**: クエリ単語の一致によるスコア補正で無関係な誤ヒットを抑制。
   - **🎚️ 最小類似度しきい値フィルタ (Min Score Filter)**: 任意の類似度以上のみに絞り込み。
   - **⚡ 最も反応した一文の特定 (Salient Sentence Extraction)**: チャンク内でクエリに最も強く反応した一文をベクトル比較でピンポイント特定。
7. **ネイティブGUIダイアログ (Dialog)**: OSのネイティブフォルダ選択ダイアログを呼び出し絶対パスを取得（macOS AppleScript / Windows PowerShell）。
8. **UI & 配信 (React + Vite + FastAPI)**: 
   - 関連度レベル別のカラーコーディング（極めて高い: 🟢, 高い: 🔵, 中程度: 🟡, 低: ⚪）。
   - キーワードハイライト（`<mark>` 表示）。
   - 事前ビルド済み `frontend/dist` を同梱し、FastAPI（ポート60000）から直接静的配信（Node.js不要）。
9. **クロスプラットフォーム起動スクリプト**:
   - `start.bat`: Windowsコマンドプロンプトの文字コード（UTF-8 `chcp 65001` / `PYTHONUTF8=1`）エラー防止対応。
   - `start.sh`: macOS / Linux 用シェルスクリプト。

## 3. データベース定義
- **documents テーブル**: `id`, `path` (UNIQUE), `title`, `mtime`, `size`, `sha256`, `text`, `embedding` (BLOB), `indexed_at`
- **chunks テーブル**: `id`, `document_id` (FK), `chunk_index`, `text`, `embedding` (BLOB), `embedding_dim`

## 4. API エンドポイント (Port: 60000)
- `POST /api/dialog/select-folder`: OSネイティブのフォルダ選択ダイアログを表示
- `POST /api/model/load`: ローカルEmbeddingモデルのロード
- `GET /api/model/status`: モデルロード状態取得
- `POST /api/index/start`: インデックス処理の開始（差分検知 / 強制再構築付き）
- `GET /api/index/progress`: インデックス進捗取得
- `GET /api/index/stats`: インデックス統計・DBサイズ等の取得
- `POST /api/search`: ベクトル検索実行（Document/Chunkモード、スコアフィルタ、キーワードブースト、反応文特定付き）
- `GET /`: フロントエンド UI（SPA静的配信）
