"""
ローカル検証用 Embedding モデルダウンロードスクリプト
仕様:
- 事前準備として Sentence Transformer モデルをダウンロードし、ローカルディレクトリに保存する。
- アプリケーション実行時はこのローカルディレクトリからロードされ、オフラインで完全動作する。
"""

import os
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer


def download_local_model(model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", target_dir: str = "models/multilingual-minilm"):
    """モデルをダウンロードし、ローカルフォルダに保存する"""
    root_dir = Path(__file__).resolve().parent.parent.parent
    save_path = root_dir / target_dir
    save_path.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {model_name} to {save_path} ...")
    model = SentenceTransformer(model_name)
    model.save(str(save_path))
    print(f"Successfully saved model to: {save_path}")


if __name__ == "__main__":
    download_local_model()
