# Obsidian Vector Search PoC

ローカルPC上の **Obsidian Vault** 全体をインデックス化し、自然言語による質問から意味的に関連するノート・チャンクを高速・高精度に検索する完全オフライン対応のベクトル検索PWAアプリケーションです。

---

## 🌟 主な特徴

- **完全オフライン動作**: 外部APIやクラウド通信は一切不使用。社内機密情報を含むVaultも安全・セキュアに検索可能。
- **🇯🇵 最高峰日本語特化 SOTA モデル `ruri-v3` シリーズ対応**:
  - 👑 **標準・高精度モデル**: `ruri-v3-310m` (768次元 / 310M params) — 豊かな文脈理解力。
  - ⚡ **超軽量・超高速モデル**: `ruri-v3-30m` (256次元 / わずか30M params) — **Windows 一般CPUでも ~60ms で爆速動作！**
- **⚡ C++/SIMD 最適化 FAISS 高速内積検索**: 2,000〜数万チャンクのベクトル検索をミリ秒未満（0.2ms以下）で処理。
- **🧩 最適化チャンキング & メタデータ統合**:
  - **見出し階層 (Header Breadcrumbs)**: `# タイトル > ## セクション` を各チャンクに自動付与し、文脈の欠落を防止。
  - **タグ・別名・キーワード統合**: Frontmatter の `tags:`, `aliases:`, `検索用:` および本文ハッシュタグ（`#tag`）を統合してベクトル化。
  - **Excalidraw & 画像埋め込みの完全除去**: 図面のBase64バイナリや描画データ（`# Excalidraw Data` 以降）を徹底クレンジング。
- **🎯 ノイズフロア除去 & スコアキャリブレーション**: 
  - 無関係な文章（生内積0.70未満）を 0.00〜0.15 に急峻にカットし、正解文書（0.85〜0.98）と無関係なノイズを明確に分離。
- **🏷️ ハイブリッド検索用 抽出キーワード (Hybrid Query)**:
  - 検索クエリからストップワードを除去した重要単語リストと、既存検索エンジンに渡せる `OR` クエリ文字列を出力・ワンクリックコピー。
- **🤖 AI（LLM）投入用 RAG コンテキスト出力 (XML / Markdown)**:
  - 上位ヒット結果を、ChatGPT / Claude / Gemini / ローカルLLMにそのまま貼り付けて回答を生成できる標準RAGフォーマット（`<context><document>...</document></context>` および Markdown引用形式）で生成・ワンクリックコピー。
- **💾 ブラウザ（LocalStorage）によるパス自動記憶**:
  - Vaultパスや各モデルパス、選択状態をブラウザに自動記憶。再起動時に入力する手間がありません。
- **🚀 ワンクリック起動（PWA Single Server）**:
  - ポート `60000` の FastAPI 単一サーバーで API と React UI を統合配信。Node.js 不要で即座に起動可能。

---

## 📊 検索精度・速度ベンチマーク（実Vault 319ファイル・全60問）

実Vault（319ノート・1,733チャンク）に対する包括的評価データセット（全60問）での実測値：

| 評価指標 | 👑 標準モデル (`ruri-v3-310m` / 768d) | ⚡ 超軽量モデル (`ruri-v3-30m` / 256d) | 評価・所見 |
| :--- | :---: | :---: | :--- |
| **Hit Rate @ 1** (第1位的中率) | **90.0%** (54 / 60問) | **88.3%** (53 / 60問) | 10問中9問がドンピシャで1位的中 |
| **Hit Rate @ 3** (Top3的中率) | **98.3%** (59 / 60問) | **100.0%** (60 / 60問) 🏆 | **超軽量モデルが全60問Top3的中を達成** |
| **MRR** (平均逆順位精度) | **0.9361** | **0.9389** 🏆 | 満点1.0に近い極めて高い順位精度 |
| **平均検索時間** | **232.93 ms** | **60.68 ms** ⚡ (約1/4) | **一般的なオフィスPCのCPUでも爆速** |
| **モデルサイズ / メモリ** | 約 650 MB / 768d | **約 60 MB / 256d** ⚡ | **メモリ消費量が極小** |

---

## 💻 動作要件

- **OS**: Windows 10/11, macOS 12+, Linux
- **Python**: 3.10 以上 (3.11 / 3.12 推奨)
- **Node.js / npm**: **不要**（ビルド済みの `frontend/dist` を同梱しているため、Pythonのみで動作します）

---

## 🚀 クイックスタート

### 1. 起動スクリプトの実行

#### Windows の場合:
```cmd
start.bat
```
（ダブルクリックまたはコマンドプロンプトから実行）

#### macOS / Linux の場合:
```bash
./start.sh
```

ブラウザが自動的に開き、**`http://127.0.0.1:60000`** にアクセスします。

---

## 🤖 モデルの準備

本システムは `models/` ディレクトリに配置されたローカルモデルを使用します。

### 方法A: 自動ダウンロード（ネット接続がある場合）
```bash
python backend/scripts/download_models.py
```
上記スクリプトを実行すると、`models/ruri-v3-310m` および `models/ruri-v3-30m` が自動配置されます。

### 方法B: 手動配置（社内プロキシ・オフライン環境の場合）
Hugging Face から以下のフォルダを作成して各ファイルを配置してください：

1. **👑 標準モデル**: `models/ruri-v3-310m/`
   - [https://huggingface.co/cl-nagoya/ruri-v3-310m/tree/main](https://huggingface.co/cl-nagoya/ruri-v3-310m/tree/main)
2. **⚡ 超軽量モデル**: `models/ruri-v3-30m/`
   - [https://huggingface.co/cl-nagoya/ruri-v3-30m/tree/main](https://huggingface.co/cl-nagoya/ruri-v3-30m/tree/main)

---

## 📖 使い方

1. **Vault フォルダの選択**:
   - 画面上部の「Obsidian Vault パス」に Vault の絶対パスを入力（または「📁 参照」ボタンをクリック）。
2. **モデルの選択**:
   - **👑 標準モデル**（Mac GPU / 高性能CPU向け）または **⚡ 超軽量モデル**（Windows 一般CPU向け）をラジオボタンで選択。
3. **インデックス作成**:
   - 「インデックス作成」パネルで対象拡張子（`.md, .markdown, .txt` 等）を確認し、「インデックス作成開始」をクリック。
   - 変更されたファイルのみが差分更新されます。
4. **検索と活用**:
   - 「ベクトル検索」パネルに自然言語で質問を入力（例: `Macのローカルで動画から文字起こしする方法`）。
   - **抽出キーワード**: ハイブリッド検索用のキーワードや OR クエリ文字列をコピー可能。
   - **🤖 AI投入用コンテキスト**: 「AI投入用コンテキスト (RAG Output)」を展開し、「📋 AIプロンプト用にコピー」をクリックして ChatGPT や Claude に貼り付け。

---

## 🛠️ プロジェクト構成

```text
PoC_lag/
├── backend/
│   ├── app/
│   │   ├── chunker.py         # 見出し階層・タグ・別名メタデータ統合チャンキング
│   │   ├── db.py              # SQLite3 永続化（documents / chunks テーブル）
│   │   ├── embedder.py        # ruri-v3 / SentenceTransformer ラッパー (MPS/CPU 自動判定)
│   │   ├── faiss_index.py     # FAISS Vector Index (IndexFlatIP) ラッパー
│   │   ├── indexer.py         # 差分インデックス & モデル自動マイグレーション
│   │   ├── main.py            # FastAPI 統合サーバー (REST API + PWA配信)
│   │   ├── scanner.py         # Vault走査 & 対象拡張子フィルタリング
│   │   └── searcher.py        # ハイブリッド検索・スコアキャリブレーション・RAG生成
│   ├── scripts/
│   │   ├── download_models.py # モデル自動ダウンロード
│   │   └── run_evaluation.py  # 全60問包括的ベンチマーク実行
│   └── tests/                 # pytest 単体・結合テストスイート
├── frontend/
│   ├── dist/                  # ビルド済み PWA 静的ファイル（FastAPIから直接配信）
│   └── src/                   # React + Vite ソースコード
├── models/
│   ├── ruri-v3-310m/          # 標準・高精度モデル (768d)
│   └── ruri-v3-30m/           # 超軽量・超高速モデル (256d)
├── docs/                      # アーキテクチャ・ベンチマーク詳細レポート
├── claude.md                  # システム仕様書
├── start.bat                  # Windows用 ワンクリック起動スクリプト
├── start.sh                   # macOS/Linux用 ワンクリック起動スクリプト
└── README.md                  # 本ドキュメント
```

---

## 🧪 テストの実行

```bash
# 全単体・結合テストの実行
pytest backend/tests/test_chunker.py backend/tests/test_scanner.py backend/tests/test_embedder.py backend/tests/test_searcher.py backend/tests/test_faiss_index.py

# 包括的60問ベンチマークテストの実行
pytest -s backend/tests/test_chunking_eval.py
```