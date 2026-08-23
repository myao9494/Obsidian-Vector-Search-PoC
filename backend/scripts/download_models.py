"""
ローカルEmbeddingモデル一括ダウンロードスクリプト
仕様:
- 推奨モデル（intfloat/multilingual-e5-base, BAAI/bge-m3 等）を Hugging Face からダウンロードし、
  プロジェクト内の models/ ディレクトリにローカル保存する。
- 実行方法:
    python backend/scripts/download_models.py
"""

import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer

# ダウンロード対象モデルリスト (識別子, HuggingFaceリポジトリ名, 保存先フォルダ名)
TARGET_MODELS = [
    ("Multilingual E5 Base (🌟推奨・速度精度ベストバランス)", "intfloat/multilingual-e5-base", "multilingual-e5-base"),
    ("BGE-M3 (🏆最高峰SOTA・長文対応)", "BAAI/bge-m3", "bge-m3"),
    ("Multilingual E5 Small (⚡超高速・軽量)", "intfloat/multilingual-e5-small", "multilingual-e5-small"),
]

def main():
    root_dir = Path(__file__).resolve().parent.parent.parent
    models_dir = root_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Obsidian Vector Search PoC - モデルダウンロード")
    print("=" * 60)
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
            model = SentenceTransformer(hf_id)
            model.save(str(save_path))
            print(f"  --> ダウンロード完了! (次元数: {model.get_embedding_dimension()}d)")
        except Exception as e:
            print(f"  --> [エラー] ダウンロードに失敗しました: {e}", file=sys.stderr)

    print("\n" + "=" * 60)
    print("  すべての処理が完了しました。")
    print("=" * 60)

if __name__ == "__main__":
    main()
