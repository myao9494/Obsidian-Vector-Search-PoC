# 外部Open/UIハブ（8001番）連携 & ファイルオープン仕様書

本ドキュメントは、キーワード検索リポジトリ (`/Users/mine/000_work/app/Local-fulltext-search`) の外部Openハブ連携契約に完全準拠し、検索結果から直接ファイルやフォルダを開くための仕様をまとめたものです。

---

## 1. 所有権と前提

8001番で動作するOpen/UIハブは、本リポジトリとは別の外部アプリ（Open Hub）が提供します。
本リポジトリは8001番サーバーを監視・プロキシせず、検索結果のクリック時に規定のURLへ遷移（またはリダイレクト）します。

| 接続先 / ポート | 用途 |
| :--- | :--- |
| `http://127.0.0.1:60000` (PoC) / `http://127.0.0.1:8079` (Local-fulltext-search) | ベクトル検索、インデックス作成、差分更新、辞書管理、`open-location` (Finder/Explorer) |
| `http://127.0.0.1:8001` | 外部Openハブアプリ（検索結果を開く既存エンドポイントの呼び出し先） |

---

## 2. エンドポイント & URL仕様

### 2.1 外部Open Hub（8001）への直接リンク（Web UI）

Webクライアント（検索結果一覧カード）は、次のURLを `target="_blank"` で開きます：

```text
ファイルを開く: ${OPEN_HUB_BASE}/api/fullpath?path=<URLエンコード済みfull_path>
フォルダを開く: ${OPEN_HUB_BASE}/?path=<URLエンコード済みfolder_path>
```

- `OPEN_HUB_BASE` の既定値: `http://127.0.0.1:8001`
- フルパスは絶対パスを使用（例: `/Users/mine/ObsidianVault/PJ-X/Kickoff.md`）

### 2.2 バックエンド リダイレクトAPI (`GET /api/open/file`)

バックエンド経由で直接8001番Open Hubへリダイレクトする場合のエンドポイントです：

```http
GET /api/open/file?path=<URLエンコード済みfull_path>&open_hub_base=http://127.0.0.1:8001
```

- **レスポンス**: `307 Temporary Redirect`
- **Location**: `http://127.0.0.1:8001/api/fullpath?path=...`

### 2.3 OSネイティブ保存場所表示API (`POST /api/files/open-location`)

ローカルの Finder（macOS）または Explorer（Windows）で対象ファイルを選択表示するAPIです：

```http
POST /api/files/open-location
Content-Type: application/json

{
  "path": "/Users/mine/ObsidianVault/TPS_Overview.md"
}
```

- **macOS動作**: `/usr/bin/open -R <path>` を実行して Finder を前面表示
- **Windows動作**: `explorer.exe /select, <normalized_path>` を実行して Explorer でファイルを選択表示
- **レスポンス**: `{"status": "success"}`

---

## 3. UI 操作とアクション一覧

検索結果カードの各要素から利用できるアクションは以下の通りです：

```
┌────────────────────────────────────────────────────────────────────────┐
│  [☑] #1  TPS_Overview.md ↗                               関連度: 94.2%  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Path: /Users/mine/ObsidianVault/TPS_Overview.md                  │  │
│  │ [📋 パスをコピー]  [🧭 保存場所を表示]  [📂 フォルダを開く]      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  反応文（核となる一文）: ...                                            │
│  ヒット段落: ...                                                       │
└────────────────────────────────────────────────────────────────────────┘
```

1. **タイトルクリック (`TPS_Overview.md ↗`)**:
   - `http://127.0.0.1:8001/api/fullpath?path=...` を新規タブで開き、ファイルを直接閲覧・編集。
2. **「📋 パスをコピー」ボタン**:
   - クリップボードにファイルの絶対パスをコピー（「コピー完了」を表示）。
3. **「🧭 保存場所を表示」ボタン**:
   - `POST /api/files/open-location` を呼び出し、ローカルの Finder / Explorer でファイル位置を即座に開く。
4. **「📂 フォルダを開く」ボタン**:
   - `http://127.0.0.1:8001/?path=...` を開き、親フォルダのリストを表示。

---

## 4. 将来のリポジトリ統合に向けた互換性

本PoCで実装された以下のインターフェースは、`/Users/mine/000_work/app/Local-fulltext-search` の仕様と完全に一致しています：
- `POST /api/files/open-location` のリクエスト/レスポンス仕様
- `http://127.0.0.1:8001/api/fullpath?path=...` のURL生成ルール
- `SearchResultItem` の `full_path` フィールド

そのため、キーワード検索とベクトル検索（セマンティックハイブリッド検索）を統合する際にも、フロントエンドおよびバックエンドのコード変更を最小限に抑えてスムーズに統合可能です。
