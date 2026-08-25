# Obsidian Vector Search PoC 仕様書

## 1. 概要
本システムは、ローカルPC上のObsidian Vault全体をインデックス化し、自然言語による質問から意味的に関連するMarkdown文書・チャンクを高速・高精度に検索する完全オフライン対応のベクトル検索PWAアプリケーションである。

## 2. 主要機能
1. **PWA & 単一サーバー配信 (FastAPI Single Server)**:
   - ポート `60000` の FastAPI サーバー単体で REST API と PWA フロントエンドを統合配信。
   - ブラウザから「アプリとしてインストール（PWA Standalone）」可能。
2. **Vault走査 (Scanner)**: Vault内の `*.md` を再帰的に探索（`.obsidian`, `.git`, `.vector_search`, `*.excalidraw.md` は除外）。
3. **チャンキング最適化 & クレンジング (Chunker)**:
   - **見出し階層コンテキスト (Header Breadcrumbs)**: `# タイトル > ## セクション > ### サブセクション` を各チャンクのヘッダーに自動付与し、セマンティック意味情報を保持。
   - **タグ統合 (Frontmatter & In-body Tags)**: YAML Frontmatter の `tags:` および本文ハッシュタグ（`#tag`）を抽出してチャンク情報に統合。
   - **リンク・記法展開**: Obsidian wikilink（`[[ノート名|表示名]]`）を展開し、URLを除去して表示名のみを保持。
   - **ノイズ除去**: Excalidraw描画データ（`%%...%%`）、Base64バイナリ行、長大URLパラメータ、メタデータ行（`created:`, `updated:` 等）を徹底除外。
   - **構造保持分割 & 短文救済**: 見出し・段落・リスト境界を尊重し500文字前後に分割。短文ノートも欠落させずインデックス化。
4. **SQLite & FAISS 統合永続化 (DB & Vector Index)**:
   - メタデータ・テキスト・Embedding を `<Vault>/.vector_search/index.db` に保存。
   - **FAISS (faiss.IndexFlatIP)** による C++/SIMD 最適化インメモリ高速内積検索（ミリ秒未満）。
5. **ローカルEmbedding & 自動デバイス選択 (Embedder)**:
   - **ruri-v3-310m (768d)** 🌟: 🇯🇵 日本語特化 SOTA ModernBERT-Ja モデル（8192トークン長文対応 / クエリ: `検索クエリ: `、文書: `検索文書: ` 自動付与）。
   - **マルチプラットフォーム自動高速化**: Mac環境では **MPS (Metal GPU)**、Windows/CPU環境では **CPU (マルチスレッドSIMD)** を自動判定・選択。
   - ローカルパスからのみロード（完全オフライン・自動通信禁止）。
6. **差分インデックス & モデル自動マイグレーション (Indexer)**:
   - `path`, `mtime`, `size`, `sha256` を用いた差分更新。
   - モデル次元数変更時の自動クリア・再インデックス検知。
7. **高精度ハイブリッド検索 & 反応文特定 (Searcher)**:
   - **Chunk検索**: チャンク単位の類似度検索。ヒット文章および前後文脈（前/ヒット/後）を表示。
   - **Document検索**: 1ノート = 1 Embeddingによる文書単位検索。
   - **🎯 日本語形態素キーワードブースト (Lexical/Hybrid Boost)**: 漢字・カタカナ・英数単語の文字種境界分割による加点。
   - **⚡ 反応文特定 (Salient Sentence Extraction)**: プレーンテキスト化・妥当性チェック・しきい値判定による核心文抽出。
8. **ネイティブGUIダイアログ (Dialog)**: OSのネイティブフォルダ選択ダイアログを呼び出し絶対パスを取得。
9. **UI (React + Vite + PWA)**: 
   - 関連度レベル別のカラーコーディング（極めて高い: 🟢, 高い: 🔵, 中程度: 🟡, 低: ⚪）。
   - キーワードハイライト（`<mark>` 表示）。
10. **クロスプラットフォーム起動スクリプト**:
    - `start.bat`: Windowsコマンドプロンプトの文字コード（UTF-8 `chcp 65001` / `PYTHONUTF8=1` / `KMP_DUPLICATE_LIB_OK=TRUE`）、ポート60000自動解放対応。
    - `start.sh`: macOS / Linux 用シェルスクリプト（ポート自動解放、OpenMP多重初期化防止対応）。
