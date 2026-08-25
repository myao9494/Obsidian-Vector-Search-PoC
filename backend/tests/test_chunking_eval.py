"""
実データクエリに基づくチャンキング & 検索精度・メタデータ活用 pytest スイート
仕様:
- Obsidian Vault: /Users/mine/000_work/obsidian-dagnetz/01_data
- データセットA（15問）、データセットB（20問）、データセットC（25問）、全60問の統合検証。
- 検証項目:
  1. 全60問の Hit Rate@1 >= 90% (圧倒的な高精度)
  2. 全60問の Hit Rate@3 >= 98% (ほぼ完全なTop3的中)
  3. 全60問の MRR >= 0.93 (極めて高い順位精度)
  4. スコア飽和率 == 0% (1.0000張り付き完全解消)
  5. 平均検索時間 < 300ms (高速レスポンス)
"""

import os
import pytest
from app.embedder import Embedder, auto_detect_device
from app.searcher import VectorSearcher, SearchMode
from tests.evaluate_chunking import (
    evaluate_search_engine,
    EVALUATION_DATASET_A,
    EVALUATION_DATASET_B,
    EVALUATION_DATASET_C,
    EVALUATION_DATASET_ALL
)


@pytest.fixture(scope="module")
def real_vault_searcher():
    vault_path = "/Users/mine/000_work/obsidian-dagnetz/01_data"
    db_path = os.path.join(vault_path, ".vector_search", "index.db")
    model_path = "/Users/mine/000_work/test/PoC_lag/models/ruri-v3-310m"

    if not os.path.exists(db_path) or not os.path.exists(model_path):
        pytest.skip("実データVaultのDBまたはruri-v3-310mモデルが存在しません")

    device = auto_detect_device()
    embedder = Embedder(model_path=model_path, device=device)
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)
    return searcher


def test_chunking_evaluation_dataset_a(real_vault_searcher):
    """データセットA（基本15問）の精度・スコア分布検証"""
    searcher = real_vault_searcher

    def search_wrapper(query: str, top_k: int):
        resp = searcher.search(query=query, mode=SearchMode.CHUNK, top_k=top_k)
        return [{"path": r.path, "score": r.score, "title": r.title} for r in resp.results]

    res_a = evaluate_search_engine(search_wrapper, EVALUATION_DATASET_A)
    assert res_a.hit_rate_at_1 >= 0.80
    assert res_a.hit_rate_at_3 >= 0.90
    assert res_a.mrr >= 0.85
    assert res_a.saturation_rate == 0.0


def test_chunking_evaluation_dataset_b(real_vault_searcher):
    """データセットB（新規20問: 多様ドメイン）の精度・スコア分布検証"""
    searcher = real_vault_searcher

    def search_wrapper(query: str, top_k: int):
        resp = searcher.search(query=query, mode=SearchMode.CHUNK, top_k=top_k)
        return [{"path": r.path, "score": r.score, "title": r.title} for r in resp.results]

    res_b = evaluate_search_engine(search_wrapper, EVALUATION_DATASET_B)
    assert res_b.hit_rate_at_1 >= 0.70
    assert res_b.hit_rate_at_3 >= 0.90
    assert res_b.mrr >= 0.80
    assert res_b.saturation_rate == 0.0


def test_chunking_evaluation_dataset_c(real_vault_searcher):
    """データセットC（新規拡張25問: 技術、運用、銘柄、制度、日常）の精度検証"""
    searcher = real_vault_searcher

    def search_wrapper(query: str, top_k: int):
        resp = searcher.search(query=query, mode=SearchMode.CHUNK, top_k=top_k)
        return [{"path": r.path, "score": r.score, "title": r.title} for r in resp.results]

    res_c = evaluate_search_engine(search_wrapper, EVALUATION_DATASET_C)
    assert res_c.hit_rate_at_1 >= 0.85
    assert res_c.hit_rate_at_3 >= 0.95
    assert res_c.mrr >= 0.90
    assert res_c.saturation_rate == 0.0


def test_chunking_evaluation_all_60_benchmark(real_vault_searcher):
    """全60問の包括的ベンチマーク検証（最高精度と速度の両立）"""
    searcher = real_vault_searcher

    def search_wrapper(query: str, top_k: int):
        resp = searcher.search(query=query, mode=SearchMode.CHUNK, top_k=top_k)
        return [{"path": r.path, "score": r.score, "title": r.title} for r in resp.results]

    res_all = evaluate_search_engine(search_wrapper, EVALUATION_DATASET_ALL)

    print("\n" + "=" * 65)
    print("【全60問 包括的ベンチマーク最終検証結果】")
    print(f"Hit Rate @ 1: {res_all.hit_rate_at_1 * 100:.1f}% ({int(res_all.hit_rate_at_1 * 60)}/60)")
    print(f"Hit Rate @ 3: {res_all.hit_rate_at_3 * 100:.1f}% ({int(res_all.hit_rate_at_3 * 60)}/60)")
    print(f"Hit Rate @ 5: {res_all.hit_rate_at_5 * 100:.1f}% ({int(res_all.hit_rate_at_5 * 60)}/60)")
    print(f"MRR         : {res_all.mrr:.4f}")
    print(f"平均検索時間 : {res_all.avg_search_time_ms:.2f} ms")
    print(f"飽和率 (1.0): {res_all.saturation_rate * 100:.1f}%")
    print(f"スコア標準偏差: {res_all.score_std:.4f}")
    print("=" * 65)

    assert res_all.hit_rate_at_1 >= 0.90  # 90%以上
    assert res_all.hit_rate_at_3 >= 0.98  # 98%以上
    assert res_all.mrr >= 0.93            # MRR 0.93以上
    assert res_all.saturation_rate == 0.0 # 飽和ゼロ
    assert res_all.avg_search_time_ms < 300.0 # 300ms未満
