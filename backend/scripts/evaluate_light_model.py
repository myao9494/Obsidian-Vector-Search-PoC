"""
最軽量モデル ruri-v3-30m のパラメーター最適化 & 全60問包括的ベンチマークスクリプト
仕様:
- Vault: /Users/mine/000_work/obsidian-dagnetz/01_data
- 軽量モデル: models/ruri-v3-30m (256d)
- CPU環境およびGPU環境における推論速度・MRR・Hit Rateを測定。
"""

import os
import time
from pathlib import Path
import numpy as np

from app.embedder import Embedder, auto_detect_device
from app.indexer import IndexManager
from app.searcher import VectorSearcher, SearchMode, extract_query_keywords
from tests.evaluate_chunking import evaluate_search_engine, EVALUATION_DATASET_ALL


def evaluate_light_model():
    vault_path = "/Users/mine/000_work/obsidian-dagnetz/01_data"
    model_path = "models/ruri-v3-30m"
    device = auto_detect_device()

    print("=" * 65)
    print("  超軽量モデル ruri-v3-30m (256d) 全60問ベンチマーク & 最適化")
    print("=" * 65)
    print(f"  Vault: {vault_path}")
    print(f"  Model: {model_path} (30M params / 256d)")
    print(f"  Device: {device}")
    print("=" * 65)

    # 1. Embedder 初期化
    embedder = Embedder(model_path=model_path, device=device)
    print(f"Embedder ロード完了: dim={embedder.embedding_dim}d")

    # 2. 一時DBまたは再インデックス
    indexer = IndexManager(vault_path=vault_path, embedder=embedder)
    print("ruri-v3-30m 用のインデックスを構築中...")
    t0 = time.time()
    res = indexer.run_index(chunk_size=500, chunk_overlap=80, force_reindex=True)
    print(f"インデックス構築完了: Docs={res.new_count + res.updated_count + res.skipped_count}, Time={time.time() - t0:.2f}s")

    # 3. 検索実行
    db_path = f"{vault_path}/.vector_search/index.db"
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)

    def search_wrapper(query: str, top_k: int):
        resp = searcher.search(query=query, mode=SearchMode.CHUNK, top_k=top_k)
        return [{"path": r.path, "score": r.score, "title": r.title} for r in resp.results]

    print("\n全60問の包括的ベンチマークを実行中...")
    eval_res = evaluate_search_engine(search_wrapper, EVALUATION_DATASET_ALL)

    print("\n" + "=" * 65)
    print("【ruri-v3-30m (256d) 全60問ベンチマーク結果】")
    print(f"Hit Rate @ 1: {eval_res.hit_rate_at_1 * 100:.1f}% ({int(eval_res.hit_rate_at_1 * 60)}/60)")
    print(f"Hit Rate @ 3: {eval_res.hit_rate_at_3 * 100:.1f}% ({int(eval_res.hit_rate_at_3 * 60)}/60)")
    print(f"Hit Rate @ 5: {eval_res.hit_rate_at_5 * 100:.1f}% ({int(eval_res.hit_res_at_5 * 60 if hasattr(eval_res, 'hit_res_at_5') else eval_res.hit_rate_at_5 * 60)}/60)")
    print(f"MRR         : {eval_res.mrr:.4f}")
    print(f"平均検索時間 : {eval_res.avg_search_time_ms:.2f} ms")
    print(f"飽和率 (1.0): {eval_res.saturation_rate * 100:.1f}%")
    print(f"スコア標準偏差: {eval_res.score_std:.4f}")
    print("=" * 65)


if __name__ == "__main__":
    evaluate_light_model()
