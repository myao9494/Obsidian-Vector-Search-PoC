"""
最高峰モデル（BGE-M3 / Multilingual-E5-Large）のダウンロードと精度・速度比較スクリプト
仕様:
- BAAI/bge-m3 (1024d) および intfloat/multilingual-e5-large (1024d) をダウンロード。
- 「マネゲ株の基礎」に対する類似度スコアとエンコード速度を測定・比較。
"""

import time
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np


def download_and_compare():
    root_dir = Path(__file__).resolve().parent.parent.parent
    
    models_to_test = [
        ("Multilingual E5 Base (現在)", "intfloat/multilingual-e5-base", str(root_dir / "models/multilingual-e5-base")),
        ("Multilingual E5 Large (大型版 1024d)", "intfloat/multilingual-e5-large", str(root_dir / "models/multilingual-e5-large")),
        ("BGE-M3 (最高峰多言語 1024d)", "BAAI/bge-m3", str(root_dir / "models/bge-m3")),
    ]

    query = "マネゲ株の基礎"
    
    texts = [
        ("マネゲ株サマリー", "マネーゲーム株（マネゲ株）の基礎知識と仕手株の初動、急騰銘柄の売買ルールについて。下値の固い低位株を狙う。"),
        ("ポプラ (マネゲ株)", "ポプラ 銘柄分析。マネゲ株としての値動きと出来高急増時のトレード戦略。カタリスト重視。"),
        ("マラソン (無関係)", "みえ松阪マラソン2026のエントリー日程、コースマップ、給水所と高低差について。"),
        ("コード/設定 (無関係)", "const commands = app.commands.commands; Object.keys(commands).forEach(k => { register(k); });"),
    ]

    for label, hf_name, local_path in models_to_test:
        print(f"\n==========================================")
        print(f"Testing Model: {label}")
        print(f"==========================================")
        save_p = Path(local_path)
        if not save_p.exists():
            print(f"Downloading {hf_name} to {save_p} ...")
            m = SentenceTransformer(hf_name)
            m.save(str(save_p))
        else:
            m = SentenceTransformer(str(save_p))

        is_e5 = "e5" in hf_name.lower()
        q_text = f"query: {query}" if is_e5 else query

        t0 = time.perf_counter()
        q_vec = m.encode(q_text, normalize_embeddings=True)
        t_q = (time.perf_counter() - t0) * 1000

        print(f"  Dimension: {m.get_embedding_dimension()}d | Query Encode Time: {t_q:.2f}ms")

        for name, t in texts:
            doc_text = f"passage: {t}" if is_e5 else t
            d_vec = m.encode(doc_text, normalize_embeddings=True)
            score = float(np.dot(q_vec, d_vec))
            print(f"  [{score:.4f}] {name}: {t[:35]}...")


if __name__ == "__main__":
    download_and_compare()
