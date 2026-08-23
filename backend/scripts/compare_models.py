"""
日本語向け高精度 Embedding モデルダウンロード & 比較検証スクリプト
仕様:
- intfloat/multilingual-e5-small (および base) をローカルにダウンロード。
- 「マネゲ株の基礎」というクエリに対して、実際のVaultファイル（マネゲ株関連ノート vs マラソン等の無関係ノート）との類似度を比較する。
"""

import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np


def test_comparison():
    root_dir = Path(__file__).resolve().parent.parent.parent
    
    models_to_test = [
        ("MiniLM (現在)", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", str(root_dir / "models/multilingual-minilm")),
        ("Multilingual E5 Small", "intfloat/multilingual-e5-small", str(root_dir / "models/multilingual-e5-small")),
        ("Multilingual E5 Base", "intfloat/multilingual-e5-base", str(root_dir / "models/multilingual-e5-base")),
    ]

    # テスト対象テキスト
    query = "マネゲ株の基礎"
    
    texts = [
        ("マネゲ株サマリー", "マネーゲーム株（マネゲ株）の基礎知識と仕手株の初動、急騰銘柄の売買ルールについて。"),
        ("ポプラ (マネゲ株)", "ポプラ 銘柄分析。マネゲ株としての値動きと出来高急増時のトレード戦略。"),
        ("マラソン (無関係)", "みえ松阪マラソン2026のエントリー日程、コースマップ、給水所と高低差について。"),
        ("コード/設定 (無関係)", "const commands = app.commands.commands; Object.keys(commands).forEach(k => { register(k); });"),
    ]

    for label, hf_name, local_path in models_to_test:
        print(f"\n==========================================")
        print(f"Testing Model: {label} ({hf_name})")
        print(f"==========================================")
        save_p = Path(local_path)
        if not save_p.exists():
            print(f"Downloading {hf_name} to {save_p} ...")
            m = SentenceTransformer(hf_name)
            m.save(str(save_p))
        else:
            m = SentenceTransformer(str(save_p))

        # E5系モデルはクエリに "query: ", パッセージに "passage: " を付与すると真価を発揮
        is_e5 = "e5" in hf_name.lower()
        q_text = f"query: {query}" if is_e5 else query
        q_vec = m.encode(q_text, normalize_embeddings=True)

        for name, t in texts:
            doc_text = f"passage: {t}" if is_e5 else t
            d_vec = m.encode(doc_text, normalize_embeddings=True)
            score = float(np.dot(q_vec, d_vec))
            print(f"  [{score:.4f}] {name}: {t[:40]}...")


if __name__ == "__main__":
    test_comparison()
