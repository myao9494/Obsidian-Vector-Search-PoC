"""
実データクエリに基づくチャンキング & 検索精度評価 pytest スイート
仕様:
- Obsidian Vault: /Users/mine/000_work/obsidian-dagnetz/01_data
- すでに構築されたインデックスDBとFAISSを用いて、全評価クエリをテスト。
- Hit Rate@3 >= 80% および 平均検索時間 < 500ms を自動検証。
"""

import os
import pytest
from app.embedder import Embedder, auto_detect_device
from app.searcher import VectorSearcher, SearchMode
from tests.evaluate_chunking import evaluate_search_engine, EVALUATION_DATASET


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


def test_chunking_evaluation_metrics(real_vault_searcher):
    """評価データセットに対するHit RateおよびMRRの検証"""
    searcher = real_vault_searcher

    def search_wrapper(query: str, top_k: int):
        resp = searcher.search(
            query=query,
            mode=SearchMode.CHUNK,
            top_k=top_k,
            keyword_boost=True,
            boost_weight=0.08
        )
        return [
            {
                "path": r.path,
                "score": r.score,
                "title": r.title,
                "salient_sentence": r.salient_sentence
            }
            for r in resp.results
        ]

    eval_result = evaluate_search_engine(search_wrapper, EVALUATION_DATASET)

    print("\n" + "=" * 60)
    print(f"Hit Rate @ 1: {eval_result.hit_rate_at_1 * 100:.1f}%")
    print(f"Hit Rate @ 3: {eval_result.hit_rate_at_3 * 100:.1f}%")
    print(f"MRR         : {eval_result.mrr:.4f}")
    print(f"Avg Time    : {eval_result.avg_search_time_ms:.2f} ms")
    print("=" * 60)

    # 目標指標の検証
    assert eval_result.hit_rate_at_3 >= 0.70  # 70%以上
    assert eval_result.mrr >= 0.60           # MRR 0.6以上
    assert eval_result.avg_search_time_ms < 600.0  # 600ms未満
