# Obsidian Vector Search PoC

ローカルPC上の **Obsidian Vault** 全体をインデックス化し、自然言語による質問から意味的に関連するノート・チャンクを高速に検索する完全オフライン対応のベクトル検索PoC（Proof of Concept）です。

---

## 🌟 主な特徴

- **完全オフライン動作**: 外部APIやクラウド、外部Vector DBは不使用。社内機密情報を含むVaultも安全に検索可能。
- **高速 NumPy 行列演算**: 数千〜数万チャンクのコサイン類似度計算をわずか数十ミリ秒で実行。
- **高精度日本語モデル対応**: `Multilingual E5 Base` (768d)、`BGE-M3` (1024d) などの最新オープンモデルに対応。
- **スマート差分インデックス**: ファイルの更新日時（mtime）とSHA256ハッシュにより、変更があったファイルのみを高速に差分更新。
- **⚡ 最も反応した一文（Salient Sentence）の特定**: チャンク全体の中から、質問に最も強く反応した核心の一文をピンポイントで抽出・強調表示。
- **🎯 語彙ブースト & 類似度色分け**: キーワード一致ブーストと類似度に応じた直感的なカラーコーディング（🟢極めて高い / 🔵高い / 🟡中程度 / ⚪低）。
- **社内PC対応（Node.js不要）**: フロントエンドのビルド成果物（`frontend/dist`）を同梱しているため、PythonのみでブラウザUIまで即座に起動可能。

---

## 💻 動作要件

- **OS**: Windows 10/11, macOS 12+, Linux
- **Python**: 3.10 以上 (3.11 / 3.12 推奨)
- **Node.js / npm**: **不要**（同梱の `frontend/dist` をPythonが自動配信します）

---

## 📦 会社環境・オフラインPCでのセットアップ手順

### STEP 1: リポジトリの取得
リポジトリを社内PCに `git clone` または ZIPでダウンロードして展開します。

### STEP 2: Python仮想環境の作成とライブラリ導入
コマンドプロンプト（Windows）またはターミナル（macOS/Linux）を開き、プロジェクト直下で以下を実行します：

```bash
# 仮想環境の作成
python -m venv .venv

# 仮想環境のアクティベート
# Windows の場合:
.venv\Scripts\activate
# macOS / Linux の場合:
source .venv/bin/activate

# 依存パッケージのインストール
pip install -r backend/requirements.txt
```

---

## 🤖 Embedding モデルの準備・ダウンロード方法

本システムはローカルの `models/` フォルダからモデルをロードして動作します。
Gitリポジトリには容量制限のためモデルバイナリを含めていませんので、以下のいずれかの方法でモデルを配置してください。

### 方法A: 自動ダウンロードスクリプト（ネット接続がある場合）
インターネットに接続できる環境で以下のスクリプトを実行すると、推奨モデルが一括ダウンロードされます：

```bash
python backend/scripts/download_models.py
```

---

### 方法B: Webブラウザから直接手動ダウンロード（プロキシや社内制限環境の場合）

社内のセキュリティやプロキシ制限等でスクリプトが使えない場合は、ブラウザで Hugging Face の **`Files and versions`** ページを開き、下表の**すべてのファイル**をダウンロードして指定のフォルダ構造通りに配置してください。

> ⚠️ **重要（配置上の注意点）**
> - `1_Pooling` や `2_Dense`, `0_StaticEmbedding` は、モデルフォルダ直下に**サブフォルダを作成**し、その中に各ファイルを配置してください。
> - モデルの重みファイルについて：Hugging Face上で `pytorch_model.bin` として提供されているモデル（PKSHA, Sup-SimCSE, SBERT, BGE-M3など）と `model.safetensors` で提供されているモデル（E5など）があります。**どちらの形式でも SentenceTransformers は自動判別して問題なく動作します**。
> - ファイルが1つでも欠けていると初期化エラーとなるため、指定のファイルを揃えてください。

---

#### 1. 【🌟多言語推奨・速度精度バランス】 `intfloat/multilingual-e5-base` (768次元 / MITライセンス: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/intfloat/multilingual-e5-base/tree/main](https://huggingface.co/intfloat/multilingual-e5-base/tree/main)
- **配置先フォルダ**: `models/multilingual-e5-base/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/multilingual-e5-base/
├── model.safetensors                 # [必須] モデル重み本体 (約1.1GB)
├── config.json                       # [必須] モデル設定ファイル
├── tokenizer.json                    # [必須] トークナイザー定義
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentencepiece.bpe.model           # [必須] SentencePiece辞書
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
└── 1_Pooling/
    └── config.json                   # [必須] プーリング設定 (1_Pooling フォルダを作成して中に入れる)
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/multilingual-e5-base/model.safetensors` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/model.safetensors) |
| `models/multilingual-e5-base/config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/config.json) |
| `models/multilingual-e5-base/tokenizer.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/tokenizer.json) |
| `models/multilingual-e5-base/tokenizer_config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/tokenizer_config.json) |
| `models/multilingual-e5-base/sentencepiece.bpe.model` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/sentencepiece.bpe.model) |
| `models/multilingual-e5-base/sentence_bert_config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/sentence_bert_config.json) |
| `models/multilingual-e5-base/config_sentence_transformers.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/config_sentence_transformers.json) |
| `models/multilingual-e5-base/modules.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/modules.json) |
| `models/multilingual-e5-base/special_tokens_map.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/special_tokens_map.json) |
| `models/multilingual-e5-base/1_Pooling/config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-base/resolve/main/1_Pooling/config.json) |

#### 2. 【🇯🇵PKSHA製日本語特化】 `pkshatech/simcse-ja-bert-base-clcmlp` (768次元 / Apache 2.0: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/tree/main](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/tree/main)
- **配置先フォルダ**: `models/pksha-simcse-ja/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/pksha-simcse-ja/
├── pytorch_model.bin                 # [必須] モデル重み本体 (約445MB)
├── config.json                       # [必須] モデル設定
├── vocab.txt                         # [必須] 日本語語彙辞書
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
├── 1_Pooling/
│   └── config.json                   # [必須] プーリング設定
└── 2_Dense/
    ├── config.json                   # [必須] Dense層設定
    └── pytorch_model.bin             # [必須] Dense層重み (約2.36MB)
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/pksha-simcse-ja/pytorch_model.bin` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/pytorch_model.bin) |
| `models/pksha-simcse-ja/config.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/config.json) |
| `models/pksha-simcse-ja/vocab.txt` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/vocab.txt) |
| `models/pksha-simcse-ja/tokenizer_config.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/tokenizer_config.json) |
| `models/pksha-simcse-ja/sentence_bert_config.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/sentence_bert_config.json) |
| `models/pksha-simcse-ja/config_sentence_transformers.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/config_sentence_transformers.json) |
| `models/pksha-simcse-ja/modules.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/modules.json) |
| `models/pksha-simcse-ja/special_tokens_map.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/special_tokens_map.json) |
| `models/pksha-simcse-ja/1_Pooling/config.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/1_Pooling/config.json) |
| `models/pksha-simcse-ja/2_Dense/config.json` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/2_Dense/config.json) |
| `models/pksha-simcse-ja/2_Dense/pytorch_model.bin` | [Download](https://huggingface.co/pkshatech/simcse-ja-bert-base-clcmlp/resolve/main/2_Dense/pytorch_model.bin) |

---

#### 3. 【🇯🇵日本語特化SOTA・高精度】 `cl-nagoya/sup-simcse-ja-large` (1024次元 / CC BY-SA 4.0: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/cl-nagoya/sup-simcse-ja-large/tree/main](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/tree/main)
- **配置先フォルダ**: `models/sup-simcse-ja-large/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/sup-simcse-ja-large/
├── pytorch_model.bin                 # [必須] モデル重み本体 (約1.3GB)
├── config.json                       # [必須] モデル設定
├── vocab.txt                         # [必須] 日本語語彙辞書
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
└── 1_Pooling/
    └── config.json                   # [必須] プーリング設定
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/sup-simcse-ja-large/pytorch_model.bin` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/pytorch_model.bin) |
| `models/sup-simcse-ja-large/config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/config.json) |
| `models/sup-simcse-ja-large/vocab.txt` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/vocab.txt) |
| `models/sup-simcse-ja-large/tokenizer_config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/tokenizer_config.json) |
| `models/sup-simcse-ja-large/sentence_bert_config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/sentence_bert_config.json) |
| `models/sup-simcse-ja-large/config_sentence_transformers.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/config_sentence_transformers.json) |
| `models/sup-simcse-ja-large/modules.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/modules.json) |
| `models/sup-simcse-ja-large/special_tokens_map.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/special_tokens_map.json) |
| `models/sup-simcse-ja-large/1_Pooling/config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-large/resolve/main/1_Pooling/config.json) |

---

#### 4. 【🇯🇵日本語特化・高速版】 `cl-nagoya/sup-simcse-ja-base` (768次元 / CC BY-SA 4.0: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/cl-nagoya/sup-simcse-ja-base/tree/main](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/tree/main)
- **配置先フォルダ**: `models/sup-simcse-ja-base/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/sup-simcse-ja-base/
├── pytorch_model.bin                 # [必須] モデル重み本体 (約440MB)
├── config.json                       # [必須] モデル設定
├── vocab.txt                         # [必須] 日本語語彙辞書
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
└── 1_Pooling/
    └── config.json                   # [必須] プーリング設定
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/sup-simcse-ja-base/pytorch_model.bin` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/pytorch_model.bin) |
| `models/sup-simcse-ja-base/config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/config.json) |
| `models/sup-simcse-ja-base/vocab.txt` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/vocab.txt) |
| `models/sup-simcse-ja-base/tokenizer_config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/tokenizer_config.json) |
| `models/sup-simcse-ja-base/sentence_bert_config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/sentence_bert_config.json) |
| `models/sup-simcse-ja-base/config_sentence_transformers.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/config_sentence_transformers.json) |
| `models/sup-simcse-ja-base/modules.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/modules.json) |
| `models/sup-simcse-ja-base/special_tokens_map.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/special_tokens_map.json) |
| `models/sup-simcse-ja-base/1_Pooling/config.json` | [Download](https://huggingface.co/cl-nagoya/sup-simcse-ja-base/resolve/main/1_Pooling/config.json) |

---

#### 5. 【🇯🇵日本語BERT定番】 `colorfulscoop/sbert-base-ja` (768次元 / MITライセンス: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/colorfulscoop/sbert-base-ja/tree/main](https://huggingface.co/colorfulscoop/sbert-base-ja/tree/main)
- **配置先フォルダ**: `models/sbert-base-ja/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/sbert-base-ja/
├── pytorch_model.bin                 # [必須] モデル重み本体 (約440MB)
├── config.json                       # [必須] モデル設定
├── spm.model                         # [必須] SentencePiece辞書モデル
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
└── 1_Pooling/
    └── config.json                   # [必須] プーリング設定
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/sbert-base-ja/pytorch_model.bin` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/pytorch_model.bin) |
| `models/sbert-base-ja/config.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/config.json) |
| `models/sbert-base-ja/spm.model` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/spm.model) |
| `models/sbert-base-ja/tokenizer_config.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/tokenizer_config.json) |
| `models/sbert-base-ja/sentence_bert_config.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/sentence_bert_config.json) |
| `models/sbert-base-ja/config_sentence_transformers.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/config_sentence_transformers.json) |
| `models/sbert-base-ja/modules.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/modules.json) |
| `models/sbert-base-ja/special_tokens_map.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/special_tokens_map.json) |
| `models/sbert-base-ja/1_Pooling/config.json` | [Download](https://huggingface.co/colorfulscoop/sbert-base-ja/resolve/main/1_Pooling/config.json) |

---

#### 6. 【⚡超高速CPU埋め込み】 `hotchpotch/static-embedding-japanese` (1024次元 / MITライセンス: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/hotchpotch/static-embedding-japanese/tree/main](https://huggingface.co/hotchpotch/static-embedding-japanese/tree/main)
- **配置先フォルダ**: `models/static-embedding-japanese/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/static-embedding-japanese/
├── config_sentence_transformers.json # [必須] ST設定
├── modules.json                      # [必須] パイプライン構成定義
└── 0_StaticEmbedding/
    ├── model.safetensors             # [必須] 埋め込み重み本体
    └── tokenizer.json                # [必須] トークナイザー定義
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/static-embedding-japanese/config_sentence_transformers.json` | [Download](https://huggingface.co/hotchpotch/static-embedding-japanese/resolve/main/config_sentence_transformers.json) |
| `models/static-embedding-japanese/modules.json` | [Download](https://huggingface.co/hotchpotch/static-embedding-japanese/resolve/main/modules.json) |
| `models/static-embedding-japanese/0_StaticEmbedding/model.safetensors` | [Download](https://huggingface.co/hotchpotch/static-embedding-japanese/resolve/main/0_StaticEmbedding/model.safetensors) |
| `models/static-embedding-japanese/0_StaticEmbedding/tokenizer.json` | [Download](https://huggingface.co/hotchpotch/static-embedding-japanese/resolve/main/0_StaticEmbedding/tokenizer.json) |

---

#### 7. 【🏆最高峰多言語SOTA・長文対応】 `BAAI/bge-m3` (1024次元 / MITライセンス: 商用利用OK)

- **Hugging Face ページ**: [https://huggingface.co/BAAI/bge-m3/tree/main](https://huggingface.co/BAAI/bge-m3/tree/main)
- **配置先フォルダ**: `models/bge-m3/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/bge-m3/
├── pytorch_model.bin                 # [必須] モデル重み本体 (約2.2GB)
├── config.json                       # [必須] モデル設定
├── tokenizer.json                    # [必須] トークナイザー定義
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentencepiece.bpe.model           # [必須] SentencePiece辞書
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
└── 1_Pooling/
    └── config.json                   # [必須] プーリング設定
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/bge-m3/pytorch_model.bin` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/pytorch_model.bin) |
| `models/bge-m3/config.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/config.json) |
| `models/bge-m3/tokenizer.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/tokenizer.json) |
| `models/bge-m3/tokenizer_config.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/tokenizer_config.json) |
| `models/bge-m3/sentencepiece.bpe.model` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/sentencepiece.bpe.model) |
| `models/bge-m3/sentence_bert_config.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/sentence_bert_config.json) |
| `models/bge-m3/config_sentence_transformers.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/config_sentence_transformers.json) |
| `models/bge-m3/modules.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/modules.json) |
| `models/bge-m3/special_tokens_map.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/special_tokens_map.json) |
| `models/bge-m3/1_Pooling/config.json` | [Download](https://huggingface.co/BAAI/bge-m3/resolve/main/1_Pooling/config.json) |

---

#### 8. 【⚡超高速・軽量版】 `intfloat/multilingual-e5-small` (384次元)

- **Hugging Face ページ**: [https://huggingface.co/intfloat/multilingual-e5-small/tree/main](https://huggingface.co/intfloat/multilingual-e5-small/tree/main)
- **配置先フォルダ**: `models/multilingual-e5-small/`

**📂 必要な全ファイル構成（ディレクトリツリー）**:
```text
models/multilingual-e5-small/
├── model.safetensors                 # [必須] モデル重み本体 (約470MB)
├── config.json                       # [必須] モデル設定
├── tokenizer.json                    # [必須] トークナイザー定義
├── tokenizer_config.json             # [必須] トークナイザー設定
├── sentencepiece.bpe.model           # [必須] SentencePiece辞書
├── sentence_bert_config.json         # [必須] SentenceTransformers設定
├── config_sentence_transformers.json # [必須] ST詳細設定
├── modules.json                      # [必須] パイプライン構成定義
├── special_tokens_map.json           # [必須] 特殊トークンマップ
└── 1_Pooling/
    └── config.json                   # [必須] プーリング設定
```

**📥 各ファイルの個別ダウンロード直リンク**:
| ファイルパス (配置先) | ダウンロードリンク |
|---|---|
| `models/multilingual-e5-small/model.safetensors` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/model.safetensors) |
| `models/multilingual-e5-small/config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/config.json) |
| `models/multilingual-e5-small/tokenizer.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/tokenizer.json) |
| `models/multilingual-e5-small/tokenizer_config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/tokenizer_config.json) |
| `models/multilingual-e5-small/sentencepiece.bpe.model` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/sentencepiece.bpe.model) |
| `models/multilingual-e5-small/sentence_bert_config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/sentence_bert_config.json) |
| `models/multilingual-e5-small/config_sentence_transformers.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/config_sentence_transformers.json) |
| `models/multilingual-e5-small/modules.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/modules.json) |
| `models/multilingual-e5-small/special_tokens_map.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/special_tokens_map.json) |
| `models/multilingual-e5-small/1_Pooling/config.json` | [Download](https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/1_Pooling/config.json) |

---

## 🚀 アプリケーションの起動方法

### Windows の場合
プロジェクト直下の **`start.bat`** をダブルクリックするか、コマンドプロンプトから実行してください。
```cmd
start.bat
```
> ※ コマンドプロンプトのコードページを自動的に UTF-8 (`chcp 65001`) に設定して起動するため、日本語Windows環境（CP932/Shift_JIS）での文字化けやクラッシュを防ぎます。

### macOS / Linux の場合
ターミナルで **`start.sh`** を実行してください。
```bash
./start.sh
```

起動後、自動的にブラウザが立ち上がり、**`http://127.0.0.1:60000`** にアクセスして利用できます。

---

## 🛠️ トラブルシューティング

### Q1. Windows コマンドプロンプトで文字化け・起動エラーが発生する
- **原因**: Windowsの既定文字コード（CP932/Shift_JIS）とPythonの入出力が衝突している可能性があります。
- **対処**: 必ず同梱の `start.bat` から起動してください。手動で実行する場合は、事前に以下のコマンドを実行してください：
  ```cmd
  chcp 65001
  set PYTHONUTF8=1
  set PYTHONIOENCODING=utf-8
  python -m uvicorn app.main:app --host 127.0.0.1 --port 60000
  ```

### Q2. 「ポート 60000 が既に使用されています」と表示される
- **原因**: 以前起動したサーバープロセスが残っている可能性があります。
- **対処**:
  - **Windows**: タスクマネージャーから `python.exe` を終了するか、コマンドプロンプトで以下を実行：
    ```cmd
    for /f "tokens=5" %a in ('netstat -aon ^| findstr :60000') do taskkill /f /pid %a
    ```
  - **macOS/Linux**:
    ```bash
    lsof -i :60000 -t | xargs kill -9
    ```

### Q3. モデルを変更した後に検索するとエラーが出る
- **原因**: 以前インデックスしたベクトルの次元数（例: 384d）と、新しくロードしたモデルの次元数（例: 768d）が異なっているためです。
- **対処**: 「**全件強制再構築 (Clean Re-index)**」チェックボックスをONにして、再度「**Index Vault**」を実行してください。

---

## 👨‍💻 開発者向け情報 (フロントエンドの再ビルド)

Node.js が利用可能な開発環境でフロントエンドのUIコード（`frontend/src/`）を変更した場合は、以下の手順で再ビルドして `frontend/dist/` を更新してください：

```bash
cd frontend
npm install
npm run build
```
ビルドされた `frontend/dist/` は Git にコミットすることで、社内PCなどのNode.jsが無い環境でもそのまま最新UIが反映されます。

---

## 📄 ライセンス

本プロジェクトは技術検証用PoCです。