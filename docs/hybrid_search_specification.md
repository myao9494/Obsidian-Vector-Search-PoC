# ハイブリッド検索 (Hybrid Search: Dense × Sparse Fusion) 仕様書

## 1. 概要
本仕様は、ローカルPC上で動作するベクトル検索エンジン（`PoC_lag`: ポート 60000）と、運用中の高速キーワード検索エンジン（`Local-fulltext-search`: ポート 8079）をREST API経由で統合し、意味類似性とキーワード完全一致の双方の強みを融合した「ハイブリッド検索PoC」のアーキテクチャおよび機能仕様を定める。

---

## 2. なぜハイブリッド検索か (背景と目的)

| 検索方式 | 強み | 弱点 |
|---|---|---|
| **ベクトル検索 (Dense / Semantic)**<br>ruri-v3 (310M/30M) + FAISS | ・自然文質問の文脈理解<br>・同義語・類似概念のマッチング<br>・曖昧な表現の救済 | ・型番・英数記号・固有名詞の完全一致でスコアが分散する恐れ |
| **キーワード検索 (Sparse / Lexical)**<br>SQLite FTS5 + BM25 (`Local-fulltext-search`) | ・固有名詞・型番・コード片の100%完全一致<br>・高速な除外検索 (`-word`) | ・表記揺れや類義語を拾えない<br>・自然言語の意味を理解できない |
| **ハイブリッド検索 (Hybrid Fusion)**<br>Dense × Sparse + RRF | **双方の長所を完全統合**。概念的一致も型番の完全一致も見落とさず最上位に浮上。 | なし (計算オーバーヘッドも並行処理で最小化) |

---

## 3. システムアーキテクチャ & 連携フロー

```
[ ユーザー (React PWA :60000) ]
        │
        ▼ POST /api/hybrid/search
[ FastAPI Backend (:60000) ]
   ├── ① VectorSearcher (ローカル FAISS + ruri-v3)
   │     ・クエリEmbedding生成 & コサイン類似度検索
   │     ・キーワード抽出 (extracted_keywords) & ORクエリ生成
   │
   ├── ② キーワード検索 API クライアント (並行呼び出し)
   │     ・POST http://127.0.0.1:8079/api/search (Local-fulltext-search)
   │     ・自動フォールバック (接続不可時もベクトル単体で安全応答)
   │
   ├── ③ 融合エンジン (Fusion Engine)
   │     ・RRF (Reciprocal Rank Fusion) / Weighted Score Fusion
   │     ・フルパスキーによるドキュメント統合
   │     ・マッチ種別判定 (🌟 両方一致 / 🔮 意味一致 / 🏷️ キーワード一致)
   │
   └── ④ レスポンス構築 & RAG コンテキスト (XML / Markdown) 生成
```

---

## 4. 融合アルゴリズム (Fusion Algorithms)

### 4.1 RRF (Reciprocal Rank Fusion) - 推奨
各ドキュメント $d$ に対し、順位の逆数に基づくスコアを算出：
$$Score_{RRF}(d) = w_{vector} \cdot \frac{1}{k + rank_{vector}(d)} + w_{keyword} \cdot \frac{1}{k + rank_{keyword}(d)}$$
- $k$: スムージング定数（デフォルト $k = 60$）
- $w_{vector}, w_{keyword}$: ベクトル重みおよびキーワード重み（スライダーで 0.0〜1.0 に動的調整可能、初期値 $0.5 : 0.5$）
- **メリット**: スケール感の異なるコサイン類似度とBM25スコアを正規化不要で公平かつ頑健に融合可能。

### 4.2 Weighted Score Fusion (正規化スコア合成)
$$Score_{Weighted}(d) = w_{vector} \cdot S_{vector}(d) + w_{keyword} \cdot S_{keyword\_norm}(d)$$
- $S_{vector}$: ベクトルのキャリブレーションスコア (0.0〜1.0)
- $S_{keyword\_norm}$: キーワード検索の `utility_score` を最大値で min-max 正規化した値 (0.0〜1.0)

---

## 5. API インターフェース仕様

### `POST /api/hybrid/search`
ハイブリッド検索を実行する。

- **リクエスト**:
  ```json
  {
    "vault_path": "/Users/mine/000_work/obsidian-dagnetz/01_data",
    "query": "議事録の決定事項",
    "keyword_api_url": "http://127.0.0.1:8079",
    "mode": "chunk",
    "top_k": 20,
    "vector_weight": 0.5,
    "keyword_weight": 0.5,
    "fusion_method": "rrf",
    "rrf_k": 60,
    "keyword_query_override": null
  }
  ```

- **レスポンス**:
  ```json
  {
    "query": "議事録の決定事項",
    "mode": "chunk",
    "hybrid_results": [
      {
        "document_id": 12,
        "path": "01_Meeting/2026-08-20.md",
        "title": "2026-08-20",
        "full_path": "/Users/mine/000_work/obsidian-dagnetz/01_data/01_Meeting/2026-08-20.md",
        "hybrid_score": 0.016393,
        "match_type": "both",
        "vector_rank": 1,
        "vector_score": 0.912,
        "keyword_rank": 2,
        "keyword_score": 14.5,
        "snippet": "<mark>決定事項</mark>: 次期アーキテクチャ選定について...",
        "salient_sentence": "本会議における最終決定事項は以下の3点とする。",
        "hit_text": "# 議事録 > ## 決定事項\n本会議における最終決定事項は...",
        "context": { "prev": { ... }, "next": { ... } }
      }
    ],
    "vector_results": [ ... ],
    "keyword_results": [ ... ],
    "extracted_keywords": ["議事録", "決定事項"],
    "keyword_query": "議事録 OR 決定事項",
    "fusion_method": "rrf",
    "vector_weight": 0.5,
    "keyword_weight": 0.5,
    "metrics": {
      "vector_time_ms": 12.4,
      "keyword_time_ms": 8.1,
      "fusion_time_ms": 0.3,
      "total_time_ms": 20.8
    },
    "keyword_api_status": {
      "connected": true,
      "url": "http://127.0.0.1:8079",
      "message": "12件ヒット"
    },
    "rag_context_xml": "<context query=\"...\">...</context>",
    "rag_context_markdown": "## 参考コンテキスト\n..."
  }
  ```

### `GET /api/hybrid/keyword-api-status`
キーワード検索APIサーバーの死活状態を確認する。

- **クエリ**: `keyword_api_url=http://127.0.0.1:8079`
- **レスポンス**:
  ```json
  {
    "connected": true,
    "url": "http://127.0.0.1:8079",
    "message": "正常に接続中"
  }
  ```

---

## 6. フロントエンド UI 機能 (HybridSearchPage.jsx)

1. **API接続ステータス & URL変更**:
   - デフォルト `http://127.0.0.1:8079`（LocalStorage保存）。接続テストボタン付き。
2. **チューニングパネル**:
   - 融合方式選択（RRF vs Weighted Score）
   - 重みスライダー（Vector比率 0%〜100%）
   - 自然文からの自動抽出ORクエリ送信オプション
3. **3つのビューモード**:
   - **🔀 統合ランキング**: 一致バッジ（🌟 両方一致 / 🔮 意味一致 / 🏷️ キーワード一致）、8001 Open Hubリンク、Finder/Explorer保存場所表示、パスクピー、文脈アコーディオン。
   - **⚖️ 3ペイン並列比較ビュー**: `[ 🔮 ベクトル Top 10 ]` | `[ 🔀 ハイブリッド Top 10 ]` | `[ 🏷️ キーワード Top 10 ]` を3列並列で視覚比較。
   - **🤖 AI (RAG) コンテキスト**: XML / Markdown プロンプトのワンクリックコピー。
