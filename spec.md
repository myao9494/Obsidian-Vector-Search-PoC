# Obsidian Vector Search PoC
## 1. 目的

ローカルPC上のObsidian Vault全体をインデックス化し、自然言語による質問から意味的に関連するMarkdown文書を検索できるか検証する。

本PoCで確認したいことは以下。

1. Vault全体を現実的な時間でIndexできるか
    
2. CPUのみでEmbedding生成が実用的な速度で動くか
    
3. 数千～数万ノート規模で検索できるか
    
4. 検索結果が人間の感覚として妥当か
    
5. 文書単位検索とチャンク単位検索のどちらが有効か
    
6. 検索結果に「なぜヒットしたのか」が分かる文章を表示できるか
    

**本PoCはRAGシステムを作るものではない。**

# 2. システム構成

```text
┌──────────────────────────────┐
│          React UI            │
└──────────────┬───────────────┘
               │ HTTP
               ↓
┌──────────────────────────────┐
│          FastAPI             │
├──────────────────────────────┤
│ Vault Scanner                │
│ Index Manager                │
│ Vector Search                │
└───────┬───────────┬──────────┘
        │           │
        ↓           ↓
   SQLite DB   Sentence Transformer
        │
        ↓
 Obsidian Vault
```

---

# 3. 技術スタック

## Backend

- Python
    
- FastAPI
    
- Uvicorn
    
- Sentence Transformers
    
- NumPy
    
- SQLite
    

## Frontend

- React
    
- Vite
    

## Vector Search

PoCでは**NumPyによるCosine Similarityの全件比較**を基本とする。

FAISS、HNSW、Chroma、Qdrant等は使用しない。

理由：

> まず「何件までなら単純な全件比較で実用になるか」を測定するため。

必要になった場合のみ将来ANNへ変更する。

---

# 4. 実行環境

mac /Windows11を想定。

GPUは必須としない。

CPUだけで動作すること。

---

# 5. ネットワーク要件

アプリケーション実行時にインターネット接続を必要としない。

Embeddingモデルは**ローカルファイルからロードする**。

Pythonからのモデル自動ダウンロードは禁止。

例えば、

```python
model = SentenceTransformer(
    r"D:\Models\embedding-model"
)
```

のようにローカルパスからロードする。

---

# 6. 起動

FastAPI：

```text
127.0.0.1:80001
```

React：

```text
127.0.0.1:80002
```

localhostのみで利用する。

外部ネットワークへの公開は不要。

---

# 7. セキュリティ

PoCのため必要最小限とする。

### 実装するもの

- localhost bind
    
- パスの基本的なバリデーション
    
- 不正なファイルアクセスを避ける基本チェック
    

### 実装しないもの

- ログイン
    
- JWT
    
- OAuth
    
- ユーザー管理
    
- HTTPS
    
- Cloud
    
- 外部API
    
- 権限管理
    
- マルチユーザー
    

---

# 8. Obsidian Vault選択

UIからWindowsのGUIフォルダ選択ダイアログを使用してVaultを選択する。

例：

```text
Obsidian Vault

[D:\Obsidian\MyVault] [フォルダ選択]
```

CLIからのパス入力を必須にしてはいけない。

---

# 9. 対象ファイル

Vault以下のMarkdownファイル。

```text
*.md
```

を再帰的に検索する。

除外：

```text
.obsidian
.git
.vector_search
```

その他は原則として検索対象。

---

# 10. SQLite DB

Vault全体をIndexするため、SQLiteを使用する。

推奨構成：

```text
MyVault/
├── Note1.md
├── Note2.md
├── ...
└── .vector_search/
    └── index.db
```

`.vector_search`はMarkdown検索対象から除外する。

---

# 11. DB構造

## documents

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    title TEXT,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    text TEXT,
    indexed_at REAL
);
```

## chunks

```sql
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    embedding_dim INTEGER NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
```

必要に応じて、

```sql
CREATE INDEX idx_chunks_document
ON chunks(document_id);
```

を作成する。

---

# 12. Embeddingモデル

Sentence Transformersを使用。

モデルはローカルパス指定。

UI：

```text
Embedding Model

[D:\Models\model-name] [Load Model]
```

モデルの自動ダウンロードは禁止。

---

# 13. Index方式

Vault全体をIndexする。

初回：

```text
Vault
 ↓
全Markdown取得
 ↓
Markdown解析
 ↓
Document作成
 ↓
Chunk作成
 ↓
Embedding
 ↓
SQLite保存
```

---

# 14. 差分Index

毎回全ファイルをEmbeddingし直さない。

以下を比較する。

```text
path
mtime
size
sha256
```

### 新規

Embedding生成。

### 変更

再Embedding。

### 変更なし

Skip。

### 削除

DBから削除。

---

# 15. Document検索

検索モードとして、

```text
● Document
○ Chunk
```

を提供する。

Document検索では、

**1 Markdown = 1 Embedding**

とする。

例えば、

```text
PICA-X.md
    ↓
全文
    ↓
Embedding
```

質問とのCosine Similarityを計算する。

目的：

> 「このノート全体が質問に関連しているか」

を評価する。

---

# 16. Chunk検索

Chunk検索ではMarkdownを複数のChunkに分割する。

概念：

```text
PICA-X.md
 ↓
Chunk 1
Chunk 2
Chunk 3
...
```

各ChunkをEmbeddingする。

質問とのCosine Similarityを計算し、関連性の高いChunkを返す。

目的：

> 「このノートのどの部分が質問に関連しているか」

を確認する。

---

# 17. Chunk分割

PoCでは高度な自然言語処理は不要。

初期値：

```text
Chunk size: 500～800文字程度
Overlap: 50～100文字程度
```

程度の単純な方式でよい。

Markdownの見出し・段落境界を可能な範囲で尊重する。

ただし、過度に複雑なchunkingアルゴリズムは実装しない。

---

# 18. 検索処理

ユーザーが質問を入力。

例：

```text
PICA-Xの熱分解モデルについて
```

### Document

```text
Query
 ↓
Embedding
 ↓
Documents
 ↓
Cosine Similarity
 ↓
Top K
```

### Chunk

```text
Query
 ↓
Embedding
 ↓
Chunks
 ↓
Cosine Similarity
 ↓
Top K
```

---

# 19. 検索結果

Top 20を表示。

## Documentモード

```text
#1  PICA-X.md

Similarity: 0.892

D:\Obsidian\TPS\PICA-X.md
```

---

## Chunkモード

```text
#1  PICA-X.md

Similarity: 0.934

「The pyrolysis model describes
decomposition of the phenolic resin...」

D:\Obsidian\TPS\PICA-X.md

Chunk: 12
```

---

# 20. 検索結果にセンテンス／文脈を表示

Chunk検索では、**検索にヒットした文章そのものを必ず表示する。**

さらに可能であれば、

```text
前の文章
↓
ヒットした文章
↓
次の文章
```

という形で周辺文脈も表示する。

例：

```text
PICA-X.md
Similarity: 0.934

...the thermal response of PICA-X is
strongly affected by the resin decomposition.

The pyrolysis model describes decomposition
of the phenolic resin.

The resulting gases contribute to the
internal pressure of the material...

D:\Obsidian\TPS\PICA-X.md
```

これにより、人間が検索結果を見て、

> 「この文書は本当に今回の質問に関係している」

と判断できるようにする。

---

# 21. Document検索でもPreviewを表示

Document検索の場合は、ファイル全体をEmbeddingしているため「ヒットしたセンテンス」は存在しない。

そのため、

- ファイル名
    
- Similarity
    
- ファイルパス
    
- 本文Preview
    

を表示する。

可能なら、PreviewはMarkdownの先頭ではなく、**検索Queryに関連しそうな箇所を簡易的に抽出して表示**してもよい。

ただし、これは必須ではない。

---

# 22. UI

1画面構成。

```text
┌─────────────────────────────────────────────┐
│ Obsidian Vector Search PoC                  │
├─────────────────────────────────────────────┤
│                                             │
│ Vault                                       │
│ [ D:\Obsidian\MyVault ] [フォルダ選択]       │
│                                             │
│ Model                                       │
│ [ D:\Models\embedding-model ] [Load]        │
│                                             │
│ [Index Vault]                               │
│                                             │
│ Documents : 12,438                          │
│ Chunks    : 86,321                          │
│                                             │
├─────────────────────────────────────────────┤
│ Search Mode                                 │
│                                             │
│ ● Document     ○ Chunk                      │
│                                             │
│ [ PICA-Xの熱分解モデルについて          ]    │
│                                  [Search]    │
├─────────────────────────────────────────────┤
│ Results                                     │
│                                             │
│ #1 PICA-X.md                  0.934          │
│ D:\Obsidian\TPS\PICA-X.md                   │
│                                             │
│ "The pyrolysis model describes..."          │
│                                             │
│ #2 Pyrolysis.md               0.901          │
│ ...                                         │
└─────────────────────────────────────────────┘
```

---

# 23. Index進捗

Vaultが大きいことを前提に、Index中は進捗を表示。

```text
Indexing...

4,231 / 12,438

34%

Elapsed: 02:31
Estimated: 04:52
```

最低限、

- 処理済みファイル数
    
- 全ファイル数
    
- 経過時間
    

を表示する。

---

# 24. Index結果

完了後、

```text
Index completed

Files       : 12,438
New         : 12,438
Updated     : 0
Skipped     : 0
Deleted     : 0

Chunks      : 86,321

Embedding   : 18m 42s
DB size     : 1.8 GB
```

などを表示。

---

# 25. 検索性能

検索時間を計測する。

例：

```text
Documents : 12,438
Chunks    : 86,321

Search time : 184 ms
```

Embedding生成時間と検索時間を分離する。

---

# 26. Index性能測定

以下を測定する。

- Markdownファイル数
    
- 総ファイルサイズ
    
- Document数
    
- Chunk数
    
- DBサイズ
    
- 初回Index時間
    
- 差分Index時間
    
- 検索時間
    

---

# 27. スケール評価

特定の件数を目標値としてハードコードしない。

実際のVaultで、

```text
1,000
5,000
10,000
50,000
100,000
```

など、可能な範囲で測定できる設計にする。

重要なのは、

> **どこから検索速度が実用限界を超えるか**

を実測すること。

---

# 28. Vector Search実装

最初はNumPyによる全件比較。

Embeddingを、

```python
numpy.ndarray
```

としてメモリにロードし、

```python
scores = embeddings @ query_embedding
```

相当の処理でCosine Similarityを計算する。

Embeddingは正規化して保存してもよい。

---

# 29. メモリ最適化

SQLiteにはEmbeddingを保存する。

アプリ起動時またはIndex後に必要なEmbeddingをメモリへロードして検索高速化してよい。

ただし、

> **「全Chunkをメモリに載せると何GB必要になるか」**

も測定対象とする。

巨大Vaultでメモリ不足になる場合は、後からANNやSQLiteベースの別方式を検討する。

---

# 30. 人間による評価

検索結果には将来的なContext Pack作成を想定して、**選択チェックボックス**を付ける。

```text
☑ PICA-X.md
☑ Pyrolysis.md
☐ FIAT.md
```

ただし、PoCでは選択したファイルをLLMへ送信しない。

選択機能は、

> **検索結果の中から人間が必要な文書を選べる**

ところまで。

---

# 31. 今回実装しないもの

明確にスコープ外。

```text
× LLM
× RAG
× Context Pack生成
× 会社チャット連携
× Keyword Search
× Hybrid Search
× Query Expansion
× Agent
× 自動質問生成
× 自動評価
× FAISS
× HNSW
× Cloud
× Authentication
× User Management
```

---

# 32. 将来の本システム

今回のPoCが成功した場合、将来的には以下へ発展する。

```text
                 Obsidian Vault
                       │
                       ↓
              ┌─────────────────┐
              │ Vector Search    │
              └────────┬────────┘
                       ↓
              関連Document/Chunk
                       ↓
                👤 人間が選択
                       ↓
                Context Pack
                       ↓
                会社チャット
                       ↓
                     LLM
                       ↓
                    回答
```

さらに将来的には、

```text
Document Search
       +
Chunk Search
       +
Keyword Search
```

を組み合わせる可能性がある。

---

# 33. PoCの最終判定

以下を人間が実際に確認する。

### ① 精度

質問すると、

> 「これは確かに関連している」

と思えるノートが上位に出るか。

### ② 文脈

Chunk検索で、

> 「なぜこの文章がヒットしたのか」

が分かるか。

### ③ 規模

Vault全体をIndexしてもPCが現実的な速度で動くか。

### ④ 更新

数個のMarkdownを変更した場合、差分Indexが十分高速か。

### ⑤ 検索速度

数万Chunk程度になっても、検索がストレスなく返ってくるか。

---

# 34. 実装方針

**最小実装を優先する。**

実装順序：

```text
STEP 1
FastAPI + React起動

↓

STEP 2
Vault GUI選択

↓

STEP 3
Markdown全件取得

↓

STEP 4
SQLite DB作成

↓

STEP 5
Document Embedding

↓

STEP 6
Document検索

↓

STEP 7
Chunk分割

↓

STEP 8
Chunk Embedding

↓

STEP 9
Chunk検索

↓

STEP 10
検索結果に本文・文脈・パス表示

↓

STEP 11
差分Index

↓

STEP 12
性能測定
```

各STEP終了時点で動作確認できる状態にする。


/Users/mine/000_work/obsidian-dagnetz/01_data/2026