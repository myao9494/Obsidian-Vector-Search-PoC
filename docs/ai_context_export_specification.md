# 仕様書: ChatAI インプット用 自己完結型 HTML ドキュメント生成 (Chat AI Export)

## 1. 概要と開発の目的

### 1.1 背景
- 企業のチャット型AI（社内LLMチャット等）は、セキュリティや環境の都合上、外部ファイルアクセスや自律エージェント機能を持たず、単純なチャットUIのみであることが多い。
- このようなチャットAIで高精度な回答を得るには、必要な前提情報（複数のMarkdownノート、図面・画像、元ソース、プロンプト指示）をすべて人間が事前にインプットしてあげる必要がある。

### 1.2 目的
- 自然文質問やキーワードから **ハイブリッド検索（Dense × Sparse API）** で関連候補ドキュメントを一括抽出。
- 候補一覧から人間がチェックボックスでドキュメントを取捨選択。
- 参考実装（`obsidian-dagnetz` の `exportHtml`）に準拠し、**図面や画像をBase64 Data URLとして完全内包した単一の自己完結型HTMLファイル** をワンクリックで生成・ダウンロードできるようにする。

---

## 2. システム構成とデータフロー

```
[ ユーザーの質問 / キーワード入力 ]
             │
             ▼
[ POST /api/hybrid/search ] (Dense Vector 60000 × Keyword API 8079)
             │
             ▼
[ 候補ノート一覧テーブル (Checklist Table) ]
  - ユーザーがチェックボックスで対象ドキュメントを選択
  - 共通プロンプト（AIへの指示テンプレート）を設定
             │
             ▼
[ POST /api/export/ai-html ] (HtmlExporter)
  ├─ 1. Vault内画像の探索 & Base64 Data URL変換 (data:image/png;base64,...)
  ├─ 2. Markdownパース & HTMLレンダリング (markdown-it-py)
  ├─ 3. Obsidian wikilink ([[Note|Title]]) の展開
  ├─ 4. AI共通プロンプト・目次・レンダリング本文・元ソースの構造化
  └─ 5. クリーンなライトテーマCSSの適用
             │
             ▼
[ 生成結果プレビュー & アクション ]
  ├─ 📥 HTMLファイルダウンロード (.html)
  ├─ 📋 HTMLコードコピー
  ├─ 📋 Markdownテキストコピー
  └─ リアルタイム iframe プレビュー
```

---

## 3. HTML構造の仕様 (Self-contained)

生成されるHTMLファイルは外部CSSや外部画像に一切依存せず、ブラウザやチャットAI（ChatGPT, Claude, Gemini, 社内LLM）に直接アップロード可能な完全自己完結ファイルです。

5. **Excalidraw および図面の自動解決 (`obsidian-dagnetz` 準拠)**:
   - **Excalidraw プレビューキャッシュ (`.excalidraw-cache`)**: FNV-1a ハッシュおよび `index.json` を逆引きし、`{hash}_*_preview.png` を自動検出して Base64 埋め込み。
   - **Excalidraw-backed Markdown**: フロントマターの `excalidraw-plugin: parsed` や同名埋め込み (`![[りんご|75]]`) を判定し、キャッシュ図面をインライン化。
   - **Draw.io SVG**: `![[xxx.drawio.svg]]` を `image/svg+xml` として Base64 Data URL 埋め込み。
   - **Obsidian リンク解決**: URLデコード（`%20` 空白対応）、Vault 相対パス、リポジトリルート基準（`01_data/...`）の表記揺れを `resolve_document_file` で完全自動吸収。

---

## 4. API エンドポイント仕様

### 4.1 `POST /api/export/ai-html`
- **Request Body**:
  ```json
  {
    "vault_path": "/Users/mine/Obsidian/Vault",
    "relative_paths": ["01_note.md", "02_architecture.md"],
    "prompt": "以下のドキュメントを元に質問に回答してください",
    "title": "AI_Context_Architecture",
    "include_raw_markdown": true,
    "include_images": true
  }
  ```
- **Response Body**:
  ```json
  {
    "html_content": "<!DOCTYPE html><html lang=\"ja\">...</html>",
    "file_name": "AI_Context_Architecture.html",
    "total_documents": 2,
    "total_images_embedded": 3,
    "size_bytes": 145820
  }
  ```

### 4.2 `POST /api/export/ai-html/download`
- **Request Body**: 同上
- **Response**: `Content-Type: text/html; charset=utf-8`, `Content-Disposition: attachment; filename="AI_Context_Architecture.html"`
