"""
ruri-v3-310m ダウンロードスクリプト
仕様:
- cl-nagoya/ruri-v3-310m をダウンロードし、models/ruri-v3-310m に保存する。
"""

import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer

def main():
    root_dir = Path(__file__).resolve().parent.parent.parent
    save_path = root_dir / "models" / "ruri-v3-310m"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if save_path.exists() and any(save_path.iterdir()):
        print(f"[スキップ] ruri-v3-310m は既に存在します: {save_path}")
        return

    print(f"[ダウンロード開始] cl-nagoya/ruri-v3-310m -> {save_path}")
    model = SentenceTransformer("cl-nagoya/ruri-v3-310m")
    model.save(str(save_path))
    print(f"ダウンロード完了: 次元数 {model.get_embedding_dimension()}")

if __name__ == "__main__":
    main()
