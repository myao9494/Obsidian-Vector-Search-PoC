# Obsidian Vector Search PoC 仕様書

## 1. 概要
本システムは、ローカルPC上のObsidian Vault全体をインデックス化し、自然言語による質問から意味的に関連するMarkdown文書・チャンクをNumPyコサイン類似度により検索する完全オフライン対応のベクトル検索PWAアプリケーションである。

## 2. 主要機能
1. **PWA & 単一サーバー配信 (FastAPI Single Server)**:
   - ポート `60000` の FastAPI サーバー単体で REST API と PWA フロントエンド（HTML / JS / CSS / Service Worker / Manifest / Icons）を統合配信。
   - ブラウザから「アプリとしてインストール（PWA Standalone）」可能。
2. **Vault走査 (Scanner)**: Vault内の `*.md` を再帰的に探索（`.obsidian`, `.git`, `.vector_search`, `*.excalidraw.md` は除外）。
3. **チャンク分割 & クレンジング (Chunker)**:
   - YAML Frontmatter（`--- ... ---`）の自動除外。
   - Excalidraw描画データ（`%%...%%`）、Base64バイナリ行、長大URLパラメータの除外。
   - メタデータ行（`created:`, `updated:`, `tags:` 等）の除外。
   - 見出し・段落境界を尊重しつつ500〜800文字で分割（極小ノイズチャンクは除外）。
4. **SQLite永続化 (DB)**: `<Vault>/.vector_search/index.db` に文書およびチャンク・Embeddingを保存。
5. **ローカルEmbedding (Embedder)**: Sentence Transformersを使用し、ローカルパスからのみロード（完全オフライン・すべて商用利用OK）。
   - **Sup-SimCSE-JA Large (1024d)**: 🇯🇵 日本語特化SOTAモデル（文単位の意味類似度・高精度） [CC BY-SA 4.0]
   - **Sup-SimCSE-JA Base (768d)**: 🇯🇵 日本語特化高速モデル [CC BY-SA 4.0]
   - **Multilingual E5 Base (768d)**: 🌟 多言語推奨・速度精度ベストバランス（~0.1s） [MIT]
   - **BGE-M3 (1024d)**: 🏆 最高峰多言語SOTAモデル（8192トークン長文対応） [MIT]
   - **Multilingual E5 Large (1024d)**: E5大型版（~0.4s） [MIT]
   - **Multilingual E5 Small (384d)**: 超高速版（~0.03s） [MIT]
6. **差分インデックス & モデル自動マイグレーション (Indexer)**:
   - `path`, `mtime`, `size`, `sha256` を用いた差分更新。
   - モデル次元数変更時の自動クリア・再インデックス検知。
   - 全件強制再構築（Clean Re-index）オプション。
7. **高精度ベクトル検索 & 反応文特定 (Searcher)**:
   - **Document検索**: 1ノート = 1 Embeddingによる文書単位検索。プレビュー表示。
   - **Chunk検索**: チャンク単位の類似度検索。ヒット文章および前後文脈（前/ヒット/後）を表示。
   - **🎯 日本語形態素キーワードブースト (Lexical/Hybrid Boost)**: 漢字・カタカナ・英数の文字種境界分割による重要単語加点。
   - **🎚️ 最小類似度しきい値フィルタ (Min Score Filter)**: 任意の類似度以上のみに絞り込み。
   - **⚡ 反応文特定 (Salient Sentence Extraction)**: プレーンテキスト化・妥当性チェック・スコア閾値（≥0.78）による正確な核心文抽出。
8. **ネイティブGUIダイアログ (Dialog)**: OSのネイティブフォルダ選択ダイアログを呼び出し絶対パスを取得。
9. **UI (React + Vite + PWA)**: 
   - 関連度レベル別のカラーコーディング（極めて高い: 🟢, 高い: 🔵, 中程度: 🟡, 低: ⚪）。
   - キーワードハイライト（`<mark>` 表示）。
   - ポート60000(FastAPI単一)で動作。
10. **クロスプラットフォーム起動スクリプト**:
   - `start.bat`: Windowsコマンドプロンプトの文字コード（UTF-8 `chcp 65001` / `PYTHONUTF8=1`）エラー防止、ポート60000自動解放対応。
   - `start.sh`: macOS / Linux 用シェルスクリプト（ポート自動解放対応）。
