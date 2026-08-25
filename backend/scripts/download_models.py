"""
ローカルEmbeddingモデル一括ダウンロードスクリプト
仕様:
- 推奨の日本語特化モデル（cl-nagoya/ruri-v3-310m, cl-nagoya/ruri-v3-30m）を Hugging Face からダウンロードし、
  プロジェクト内の models/ ディレクトリにローカル保存する。
- 実行方法:
    python backend/scripts/download_models.py
"""

import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

# ダウンロード対象モデルリスト (識別子, HuggingFaceリポジトリ名, 保存先フォルダ名)
TARGET_MODELS = [
    ("👑 標準・高精度モデル: ruri-v3-310m (768d / 310M params)", "cl-nagoya/ruri-v3-310m", "ruri-v3-310m"),
    ("⚡ 超軽量・超高速モデル: ruri-v3-30m (256d / 30M params)", "cl-nagoya/ruri-v3-30m", "ruri-v3-30m"),
    ("🌟 バランスモデル: ruri-v3-70m (512d / 70M params)", "cl-nagoya/ruri-v3-70m", "ruri-v3-70m"),
]

def main():
    root_dir = Path(__file__).resolve().parent.parent.parent
    models_dir = root_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  Obsidian Vector Search PoC - モデル一括ダウンロード")
    print("=" * 65)
    print(f"保存先: {models_dir}\n")

    for label, hf_id, folder_name in TARGET_MODELS:
        save_path = models_dir / folder_name
        if save_path.exists() and any(save_path.iterdir()):
            print(f"[スキップ] {label} は既に存在します: {save_path.name}")
            continue

        print(f"\n[ダウンロード開始] {label}")
        print(f"  HuggingFace ID : {hf_id}")
        print(f"  ローカル保存先 : {save_path}")
        try:
            snapshot_download(repo_id=hf_id, local_dir=str(save_path))
            print(f"  --> ダウンロード完了!")
        except Exception as e:
            print(f"  --> [エラー] ダウンロードに失敗しました: {e}", file=sys.stderr)

    print("\n" + "=" * 65)
    print("  すべてのモデル準備が完了しました。")
    print("=" * 65)

if __name__ == "__main__":
    main()
