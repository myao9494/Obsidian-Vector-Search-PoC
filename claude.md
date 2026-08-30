# Obsidian Vector Search PoC 仕様書

## 1. 概要
本システムは、ローカルPC上のObsidian Vault全体をインデックス化し、自然言語による質問から意味的に関連するMarkdown文書・チャンクを高速・高精度に検索する完全オフライン対応のベクトル検索PWAアプリケーションである。

## 2. 主要機能
1. **PWA & 単一サーバー配信 (FastAPI Single Server)**:
   - ポート `60000` の FastAPI サーバー単体で REST API と PWA フロントエンドを統合配信。
   - ブラウザから「アプリとしてインストール（PWA Standalone）」可能。
2. **モデル2択化 & ブラウザLocalStorage自動記憶**:
   - **👑 標準モデル**: `ruri-v3-310m` (768d / 310M params) - 最高峰の文脈把握力。
   - **⚡ 超軽量モデル**: `ruri-v3-30m` (256d / 30M params) - 超極小・Windows CPU環境で ~60ms 爆速動作。
   - ラジオボタンでワンクリック切り替え可能。
   - `Vaultパス`、`標準モデルパス`、`超軽量モデルパス`、`選択モデル` をブラウザ（LocalStorage）に自動記憶。
3. **柔軟なVault走査 & 対象拡張子指定 (Scanner)**:
   - 対象拡張子（`.md`, `.markdown`, `.txt` 等）を画面およびAPIから動的に指定可能。
   - `.obsidian`, `.git`, `.vector_search`, `*.excalidraw.md`, `*.canvas` 等の除外ディレクトリ・ファイルを自動スキップ。
4. **チャンキング最適化 & クレンジング (Chunker)**:
   - **見出し階層コンテキスト (Header Breadcrumbs)**: `# タイトル > ## セクション > ### サブセクション` を各チャンクのヘッダーに自動付与し、セマンティック意味情報を保持。
   - **タグ・メタデータ統合 (Tags, Aliases, Keywords, Category)**: 
     - YAML Frontmatter の `tags:` および本文ハッシュタグ（`#tag`）
     - ノートの別名（`aliases:`）
     - 検索用キーワード（`検索用:`, `keywords:`, `category:`）
     - これらを包括抽出し、各チャンク先頭に `[コンテキスト] [Tags: #A #B] [Aliases: X] [Keywords: Y]` として構造化埋め込み。
   - **YAML Frontmatter / ヘッダーの完全除去**: `created:`, `updated:`, `excalidraw-plugin:` 等の不要なYAML行を本文から完全に除外。
   - **Excalidraw 描画データ (# Excalidraw Data 以降) の完全切り捨て**: 図面のバイナリ・JSONデータ（compressed-json等）や画像埋め込み（`![[...]]`）を徹底除去。
   - **リンク・記法展開**: Obsidian wikilink（`[[ノート名|表示名]]`）を展開し、URLを除去して表示名のみを保持。
   - **構造保持分割 & 短文救済**: 見出し・段落・リスト境界を尊重し500文字前後に分割。短文ノートも欠落させずインデックス化。
5. **SQLite & FAISS 統合永続化 (DB & Vector Index)**:
   - メタデータ・テキスト・Embedding をモデル別に `<Vault>/.vector_search/index_<model_name>.db` に保存。
   - モデル（標準 768d vs 超軽量 256d）ごとに独立したSQLite DBファイルを管理し、モデル切り替え時にインデックスを破棄・上書きすることなく共存・即時切り替えが可能。
   - **FAISS (faiss.IndexFlatIP)** による C++/SIMD 最適化インメモリ高速内積検索（0.2ms以下）。
6. **ローカルEmbedding & 自動デバイス選択 (Embedder)**:
   - **ruri-v3-310m / ruri-v3-30m**: 日本語特化 SOTA ModernBERT-Ja モデル（8192トークン長文対応 / クエリ: `検索クエリ: `、文書: `検索文書: ` 自動付与）。
   - **マルチプラットフォーム自動高速化**: Mac環境では **MPS (Metal GPU)**、Windows/CPU環境では **CPU (マルチスレッドSIMD)** を自動判定・選択。
   - ローカルパスからのみロード（完全オフライン・自動通信禁止）。
7. **モデル別差分インデックス & 直感的更新ボタン (Indexer)**:
   - `path`, `mtime`, `size`, `sha256` を用いた差分更新。対象拡張子の動的受付。
   - **⚡ 差分インデックス更新（差分学習）**: 変更・新規・削除のあったノートのみを高速処理（`force_reindex=false`）。
   - **🔄 全件再インデックス**: 対象モデルのインデックスのみをクリーンに全再作成（`force_reindex=true` / 他モデルのインデックスは安全に保持）。

8. **高精度ハイブリッド検索 & メタデータ・キーワードブースト (Searcher)**:
   - **スコアキャリブレーション & ノイズフロア除去**: 異方性ノイズ（無関係テキストの生内積 0.70 未満）を急峻にカットし、真の合致文書（0.70〜0.98）と無関係なゴミ（0.00〜0.25）の間に明確なスコア差（マージン）を創出。
   - **タグ・別名・タイトル一致ボーナス (Tag / Meta / Exact Title Bonus)**: クエリ単語がタグや別名、ファイル名と合致した場合に優先順位を押し上げるメタデータブースト。
   - **🏷️ ハイブリッド検索用 抽出キーワード (Extracted Keywords & OR Query)**: クエリから重要単語を抽出（`extracted_keywords`）し、既存検索エンジンに渡せる `keyword_query`（例: `A OR B OR C`）を生成。
   - **🤖 AI（LLM）投入用 RAG コンテキスト生成 (XML / Markdown)**: 上位ヒット結果を LLM（ChatGPT / Claude / Gemini / ローカルLLM）にそのまま食べさせられる標準RAGフォーマット（`<context><document>...</document></context>` および Markdown引用形式）で生成。
   - **⚡ 高速反応文特定 (Salient Sentence Extraction)**: 上位3件の核心文を高速抽出してハイライト。
9. **📖 専門用語・類似語辞書連携 & Web UIエディタ (Glossary / Synonyms)**:
   - **シンプル新2列フォーマット（第1列: 専門用語, 第2列: 意味・解説）**: 専門用語列内にカンマ区切り（`,` や `、`）で同義語・略称をまとめて定義可能（例: `PJ-X, プロジェクトX, PJX`）。従来の3列フォーマットとも完全互換。
   - **⚡ SHA-256ハッシュ & mtime差分検知キャッシュ**: 毎検索時のExcel I/O負荷を完全ゼロ化（0.00ms応答）。人間が外部で編集・保存した際のみハッシュ差分を検知して自動で再パース・更新。
   - **Mac対応 Web UI 辞書エディタ**: Excelアプリが不要で、画面上のモーダルから用語の追加・編集・削除・Excel (`.xlsx`) 保存・新規作成が直接完結。
   - **Excel (.xlsx) / CSV 自動読み込み**: Vault内の `glossary.xlsx` や `glossary.csv` を自動認識・ロード。
   - **表記揺れの自動吸収**: 大文字/小文字、全角/半角、ハイフン有無（`PJ-X` ⇔ `PJX` ⇔ `ｐｊｘ`）を正規化して最長一致で検知。
   - **自然文クエリのEmbedding補強 (Query Enrichment)**: 自然文の質問から用語を検知し、同義語・解説を付与してEmbedding化することで、過去ノートの別名表記とも高次元でマッチング。
   - **インデックス時メタデータ自動補完 (Chunk Enrichment)**: 本文中の専門用語から同義語・解説を `[Aliases: ...]` `[Context: ...]` として自動注入。既存ノートを修正することなく過去資産を救済。
   - **UI 用語解説カード表示**: 検索結果画面の上部に検知された社内専門用語・類似語・解説のカードを美しく表示し、「辞書を編集」ショートカットも提供。
10. **ネイティブGUIダイアログ (Dialog)**: OSのネイティブフォルダ選択ダイアログを呼び出し絶対パスを取得。
11. **UI (React + Vite + PWA)**: 
    - モデル2択ラジオ選択（標準 768d vs 超軽量 256d）。
    - 📖 専門用語辞書 Web UI エディタ（Excel直接生成・保存対応）。
    - 💡 検出された専門用語・類似語（Glossary）カード表示。
    - 抽出キーワードバッジ表示 & ORクエリコピー。
    - 🤖 AI投入用コンテキストビューア（XML/Markdown切り替え ＆ プロンプト用コピー）。
    - 対象拡張子入力フィールドの搭載。
    - 関連度レベル別のカラーコーディング（極めて高い: 🟢, 高い: 🔵, 中程度: 🟡, 低: ⚪）。
    - キーワードハイライト（`<mark>` 表示）。
12. **クロスプラットフォーム起動スクリプト**:
    - `start.bat`: Windowsコマンドプロンプトの文字コード（UTF-8 `chcp 65001` / `PYTHONUTF8=1` / `KMP_DUPLICATE_LIB_OK=TRUE`）、ポート60000自動解放対応。
    - `start.sh`: macOS / Linux 用シェルスクリプト（ポート自動解放、OpenMP多重初期化防止対応）。
13. **⚡ ファイル差分更新・ライブ検証 (Incremental Updater & Live Benchmark)**:
    - **単一ファイル高速差分更新 (`POST /api/index/update-file`)**: ファイル変更を検知・即座にEmbedding & DB/FAISS反映。
    - **工程別ミリ秒プロファイリング**: `I/O・ハッシュ計算`、`Markdown解析・Chunking`、`Embedding推論`、`SQLite/FAISS保存` の内訳を計測。
    - **GUI リアルタイム時間検証パネル**: ファイルパス入力、直接編集テスト、外部変更検知、意地悪テストプリセット（1万字超長文、記号乱舞、空ファイル等）を即座に実験・視覚化。
14. **🔗 外部Open Hub (8001) 連携 & ファイルオープン・保存場所表示**:
    - **Local-fulltext-search 仕様完全準拠**: 将来のリポジトリ統合を見据え、キーワード検索リポジトリと同一のプロトコルを採用。
    - **Primary Open (タイトルクリック)**: 検索結果タイトルをクリックすると `${OPEN_HUB_BASE}/api/fullpath?path=<URLエンコード済みfull_path>`（既定 `http://127.0.0.1:8001`）へ遷移し、外部Openハブ経由でファイルを開く。
    - **307リダイレクトAPI (`GET /api/open/file?path=...`)**: バックエンド経由で8001 Open Hubへ転送。
    - **保存場所表示 (`POST /api/files/open-location`)**: macOSではFinder (`open -R`)、WindowsではExplorer (`explorer.exe /select,`) を起動してファイル位置を表示。
    - **フォルダを開く & パスコピー**: 親フォルダのOpen Hubリンクおよびフルパスのワンクリックコピー機能。
15. **🔀 ハイブリッド検索 PoC (Dense Vector × Keyword Search API Fusion)**:
    - **運用中キーワード検索リポジトリ (`Local-fulltext-search`: Port 8079) 連携**:
      - `POST /api/hybrid/search` および `GET /api/hybrid/keyword-api-status` エンドポイント提供。
      - ベクトル検索エンジン（60000番）と運用中キーワード検索API（8079番）を同時並行実行。
    - **RRF (Reciprocal Rank Fusion) リランキング**:
      - $Score_{RRF}(d) = w_{vector} \cdot \frac{1}{k + rank_{vector}} + w_{keyword} \cdot \frac{1}{k + rank_{keyword}}$（デフォルト $k=60$）。
      - 重み比率スライダー（0%〜100%）および 正規化スコア合成（Weighted Score Fusion）に対応。
    - **自動フォールバック**: キーワード検索APIサーバー停止時もベクトル検索単体で安全に応答。
    - **抽出キーワード連携**: 自然文質問から重要単語を抽出して `A OR B` クエリを自動生成しキーワードAPIへ送信。
    - **専用新ページ & 3ペイン並列比較ビュー (HybridSearchPage.jsx)**:
      - 🔀 **ハイブリッド統合ランキング**: 一致理由バッジ（`🌟 両方一致` / `🔮 意味一致` / `🏷️ キーワード一致`）、スコア内訳、スニペット、反応文、文脈アコーディオン。
      - ⚖️ **3ペイン並列比較ビュー**: `[ 🔮 ベクトル Top 10 ]` vs `[ 🔀 ハイブリッド Top 10 ]` vs `[ 🏷️ キーワード Top 10 ]` を3列並列で視覚比較。
      - 🤖 **AI (RAG) コンテキスト**: 融合上位ノートから生成した XML / Markdown プロンプトのワンクリックコピー。

16. **🤖 ChatAI インプット用 自己完結型 HTML ドキュメント生成 (Chat AI Export)**:
    - **エージェント非搭載の社内チャットAI向けワンショット投入**:

      - 外部ファイルアクセス権限のないチャットAIに、関連する前提ドキュメント群・図面・指示プロンプトを単一ファイルで投入可能。
    - **ハイブリッド検索連動 & 人間選択チェックリスト**:
      - 質問・キーワードからハイブリッド検索で候補ノートを抽出。「ハイブリッド検索」タブで設定されたすべてのパラメータ（重み比率スライダー、RRF / Weighted Score 融合方式、検索単位：チャンク / ドキュメント、キーワードAPI URL、ORクエリ設定）を `hybridSettings.js` 経由でリアルタイムに自動同期・完全適用。
      - ステップ1のヘッダーに連動中のハイブリッド検索設定ステータス（重み比率・融合方式・検索単位）をリアルタイム表示。
      - デフォルト選択は「何も選択しない（0件）」とし、人間が必要なドキュメントを明示的に選択。
      - **チェックボックス・ドラッグ連続選択 / Shift+ドラッグ連続解除**: チェックボックス列をマウスドラッグでなぞることで高速連続選択、Shiftキーを押しながらドラッグで高速連続解除が可能。全選択 / 全解除ボタンも完備。
      - **スニペット / 根拠文の文字数制御**: 一覧テーブル内のスニペットおよび根拠文は最大200文字までに制限し、200文字を超える場合は末尾に「...」を付加してレイアウト崩れと視認性を最適化。
    - **`obsidian-dagnetz` 準拠の自己完結型 HTML エクスポート (`html_exporter.py`)**:




      - **Excalidraw キャッシュ・図面・ローカル画像の Base64 Data URL インライン埋め込み**:
        - `.excalidraw-cache` の探索および FNV-1a ハッシュ / `index.json` 逆引きによる Excalidraw PNG プレビュー画像の自動解決。
        - **Excalidraw ベクターSVG自動動的生成フォールバック**: プレビューキャッシュ未生成のノートでも、ノート内の `compressed-json` / JSON 描画データから高品質なベクター SVG を自動生成して 100% 確実に図面をインライン埋め込み。
        - **Drawio / SVG ダークモード白黒反転防止正規化**: `color-scheme: light dark` や `light-dark(...)` をライトモード（`#ffffff` 背景、黒線）に正規化し、OS/ブラウザがダークモードでも正常描画を保証。
        - `![[りんご|75]]` などの Excalidraw-backed markdown（自身または別ノート）の自動判定および埋め込み。
        - `.drawio.svg`, `.dio.svg`, `.svg` の `image/svg+xml` Base64 Data URL 化。
        - URLデコード（`unquote`）および Vault 全体・添付フォルダの階層探索。

      - **多角的スマートパス解決 (`resolve_document_file`)**:
        - キーワード検索 API / ベクトル検索からのパス表現（絶対パス、Vault 相対パス、リポジトリルート相対パス `01_data/...`）の表記揺れを自動正規化し、100% 確実に実在ノートを特定。
      - **AI共通指示プロンプト統合**: デフォルト「質問に対する根拠付きの回答」、その右側に「資料の修正・推敲」、「総合要約とアクション抽出」、「課題・リスクレビュー」、および自由編集プロンプトを埋め込み。

      - **Dataview / DataviewJS テーブル定義の自動HTMLテーブル変換**:
        - `株人マネゲ【254】.md` のような `const noteListRows = [...]` を内包する ````dataviewjs` ブロックや `dv.table()` を自動パースし、Obsidian と同様の美しい名称・タグ・冒頭・作成日・編集日の HTML テーブル（`<table>`）としてレンダリング。
      - **構造化HTML & マークダウン元データセクション**: 目次、クリーンなMarkdownレンダリング本文、`<details><summary>マークダウンファイルの元データ</summary><pre><code>...</code></pre></details>` を統合。

    - **専用新ページ & ダウンロード・コピー UI (`AiContextExportPage.jsx`)**:
      - 「🤖 AIコンテキスト生成 (Chat AI Export)」専用タブ。
      - **📥 HTMLファイルダウンロード (.html)**、**📋 HTMLコードコピー**、**📋 Markdownテキストコピー**、リアルタイムプレビュー（iframe表示）を提供。
      - 日本語 IME 変換決定（Enter 1回目）での誤検索防止ガード (`isComposing`) 搭載。
      - エンドポイント: `POST /api/export/ai-html`, `POST /api/export/ai-html/download`。

