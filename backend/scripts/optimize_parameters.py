"""
検索・スコアリング パラメーター自動最適化スクリプト
仕様:
- 全60問の包括的ベンチマーク（EVALUATION_DATASET_ALL）に対してグリッドサーチを実行。
- noise_floor, norm_exponent, lexical_weight, exact_title_bonus の最適値を算出。
- 最高 MRR および Hit Rate @ 1 を達成するパラメータセットを出力。
"""

import itertools
import time
from pathlib import Path
from typing import Dict, List
import numpy as np

from app.embedder import Embedder, auto_detect_device
from app.searcher import VectorSearcher, SearchMode, extract_query_keywords
from tests.evaluate_chunking import EVALUATION_DATASET_ALL


def grid_search_parameters():
    vault_path = "/Users/mine/000_work/obsidian-dagnetz/01_data"
    db_path = f"{vault_path}/.vector_search/index.db"
    
    print("Embedding モデルをロード中...")
    embedder = Embedder("models/ruri-v3-310m", device=auto_detect_device())
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)
    searcher._ensure_faiss_indexes(SearchMode.CHUNK)

    # クエリ埋め込みとキーワードを事前キャッシュ（高速化）
    print("60問のクエリベクトルを事前計算中...")
    cached_queries = []
    for item in EVALUATION_DATASET_ALL:
        q = item["query"]
        q_vec = embedder.encode(q, is_query=True)
        kws = extract_query_keywords(q)
        cached_queries.append({
            "query": q,
            "expected": item["expected_filename"],
            "q_vec": q_vec,
            "keywords": kws
        })

    # パラメーターグリッド
    noise_floors = [0.68, 0.70, 0.72]
    norm_exponents = [1.3, 1.5, 1.6, 1.8]
    lexical_weights = [0.12, 0.15, 0.18, 0.22]
    exact_title_bonuses = [0.04, 0.08, 0.12]

    best_mrr = -1.0
    best_hit1 = -1.0
    best_params = None
    all_results = []

    total_combinations = len(noise_floors) * len(norm_exponents) * len(lexical_weights) * len(exact_title_bonuses)
    print(f"全 {total_combinations} パターンのパラメーター探索を開始...")

    faiss_idx = searcher._chunk_faiss_index
    chunk_rows = searcher._chunk_rows_cache

    for nf, exp, lex_w, title_b in itertools.product(noise_floors, norm_exponents, lexical_weights, exact_title_bonuses):
        hits_1 = 0
        hits_3 = 0
        hits_5 = 0
        rr_sum = 0.0

        for q_data in cached_queries:
            q_vec = q_data["q_vec"]
            expected = q_data["expected"]
            keywords = q_data["keywords"]

            raw_hits = faiss_idx.search(q_vec, top_k=40)
            scored_items = []

            for hit in raw_hits:
                row = chunk_rows.get(hit["id"])
                if not row:
                    continue

                raw_sim = float(hit["score"])
                # スコア計算
                if raw_sim < nf:
                    base_dense = max(0.0, (raw_sim - 0.45) / 1.8)
                else:
                    norm = min(max((raw_sim - nf) / (0.93 - nf), 0.0), 1.0)
                    base_dense = 0.15 + 0.67 * (norm ** exp)

                # キーワード一致
                t_lower = (row.get("title") or "").lower()
                p_lower = (row.get("path") or "").lower()
                text_lower = (row.get("text") or "").lower()

                matched_count = 0
                exact_title = False
                for kw in keywords:
                    kw_l = kw.lower()
                    m = False
                    if kw_l in t_lower or kw_l in p_lower:
                        m = True
                        if kw_l == Path(row.get("path") or "").stem.lower():
                            exact_title = True
                    if kw_l in text_lower:
                        m = True
                    if m:
                        matched_count += 1

                match_ratio = matched_count / len(keywords) if keywords else 0.0
                t_bonus = title_b if exact_title else min(matched_count * 0.03, 0.06)
                final_score = min(max(base_dense + (match_ratio * lex_w) + t_bonus, 0.0), 0.98)

                scored_items.append((final_score, row.get("path") or ""))

            scored_items.sort(key=lambda x: x[0], reverse=True)

            # 順位判定
            rank = None
            for idx, (_, path_str) in enumerate(scored_items):
                if expected.lower() in path_str.lower() or Path(path_str).name.lower() == expected.lower():
                    rank = idx + 1
                    break

            if rank is not None:
                if rank == 1:
                    hits_1 += 1
                if rank <= 3:
                    hits_3 += 1
                if rank <= 5:
                    hits_5 += 1
                rr_sum += 1.0 / rank

        total = len(cached_queries)
        mrr = rr_sum / total
        hit1 = hits_1 / total
        hit3 = hits_3 / total

        all_results.append({
            "params": (nf, exp, lex_w, title_b),
            "mrr": mrr,
            "hit1": hit1,
            "hit3": hit3
        })

        if mrr > best_mrr or (mrr == best_mrr and hit1 > best_hit1):
            best_mrr = mrr
            best_hit1 = hit1
            best_params = (nf, exp, lex_w, title_b)

    print("\n" + "=" * 60)
    print("【最適パラメーター探索結果】")
    print(f"Best MRR        : {best_mrr:.4f}")
    print(f"Best Hit Rate@1 : {best_hit1*100:.1f}%")
    print(f"Best Params     : noise_floor={best_params[0]}, norm_exponent={best_params[1]}, lexical_weight={best_params[2]}, exact_title_bonus={best_params[3]}")
    print("=" * 60)

    # トップ5設定を表示
    all_results.sort(key=lambda x: (x["mrr"], x["hit1"]), reverse=True)
    print("\n--- Top 5 パラメーター構成 ---")
    for idx, r in enumerate(all_results[:5], 1):
        p = r["params"]
        print(f"Top {idx}: MRR={r['mrr']:.4f}, Hit@1={r['hit1']*100:.1f}%, Hit@3={r['hit3']*100:.1f}% | nf={p[0]}, exp={p[1]}, lex_w={p[2]}, title_b={p[3]}")


if __name__ == "__main__":
    grid_search_parameters()
