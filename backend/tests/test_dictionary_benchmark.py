"""
専門用語・類似語辞書 (Glossary) 包括的ベンチマーク & スコア品質検証テスト
仕様:
- sample_vault 内の実データと ruri-v3 実モデル（または軽量モデル）を用いて全30問の検証を実施。
- 検証カテゴリ:
  1. 専門用語・略称・表記揺れクエリ（10問）: 辞書連携により Hit Rate@1 >= 90%
  2. 自然言語・会話調の質問クエリ（10問）: 意図通りの正解ノートが Hit Rate@1 >= 90%
  3. 辞書に頼らない通常クエリ（10問）: 既存ノートの検索精度（Hit Rate@1 == 100%）およびスコアが一切劣化していないこと
  4. 辞書あり vs 辞書なしの比較: 専門用語クエリでの顕著なスコア向上と通常クエリでのスコア維持を検証
"""

import os
import pytest
from app.embedder import Embedder, auto_detect_device
from app.indexer import IndexManager
from app.searcher import VectorSearcher, SearchMode


# === 包括的評価データセット (30問) ===
BENCHMARK_DATASET = [
    # ─── カテゴリ1: 専門用語・略称・コード名・表記揺れ (10問) ───
    {
        "query": "PJXのキックオフ定例での決定事項って何だっけ？",
        "expected": "2024-05-10_プロジェクトX_キックオフ.md",
        "category": "acronym",
    },
    {
        "query": "ポチッと君の申請締め切りは何時まで？",
        "expected": "社内経費精算ガイド.md",
        "category": "acronym",
    },
    {
        "query": "KVSのキャッシュクリア手順と運用ポリシー",
        "expected": "インフラ_Redis運用保守手順.md",
        "category": "acronym",
    },
    {
        "query": "Zeusでの新規案件の登録ルール",
        "expected": "営業CRMツール_Zeus運用マニュアル.md",
        "category": "acronym",
    },
    {
        "query": "WFHの通信手当の支給額について",
        "expected": "リモートワーク勤務規定.md",
        "category": "acronym",
    },
    {
        "query": "SLAの稼働率目標値と障害復旧時間",
        "expected": "SLA保証基準および可用性レポート.md",
        "category": "acronym",
    },
    {
        "query": "ｐｊｘのマイクロサービス移行計画",
        "expected": "2024-05-10_プロジェクトX_キックオフ.md",
        "category": "acronym",
    },
    {
        "query": "pochitoで領収書を添付して精算したい",
        "expected": "社内経費精算ガイド.md",
        "category": "acronym",
    },
    {
        "query": "ISMSのパスワード設定基準と画面ロックルール",
        "expected": "情報セキュリティ基本方針_2024.md",
        "category": "acronym",
    },
    {
        "query": "PXの議事録保管場所",
        "expected": "2024-05-10_プロジェクトX_キックオフ.md",
        "category": "acronym",
    },

    # ─── カテゴリ2: 自然言語・会話調の質問 (10問) ───
    {
        "query": "出張の交通費を精算したいんだけどどうすればいい？",
        "expected": "社内経費精算ガイド.md",
        "category": "natural",
    },
    {
        "query": "基幹システムの刷新ってどんな方針で進めてる？",
        "expected": "2024-05-10_プロジェクトX_キックオフ.md",
        "category": "natural",
    },
    {
        "query": "営業の商談パイプラインを記録するツールの使い方は？",
        "expected": "営業CRMツール_Zeus運用マニュアル.md",
        "category": "natural",
    },
    {
        "query": "家で仕事するときの規定や手当について知りたい",
        "expected": "リモートワーク勤務規定.md",
        "category": "natural",
    },
    {
        "query": "インメモリキャッシュのメモリ上限やエビクション設定",
        "expected": "インフラ_Redis運用保守手順.md",
        "category": "natural",
    },
    {
        "query": "新人が入社した初日のスケジュールと受取物",
        "expected": "新入社員向け_オンボーディング手順.md",
        "category": "natural",
    },
    {
        "query": "システムのサービス可用性や品質保証の基準値",
        "expected": "SLA保証基準および可用性レポート.md",
        "category": "natural",
    },
    {
        "query": "会社のセキュリティルールや外部ストレージの禁止事項",
        "expected": "情報セキュリティ基本方針_2024.md",
        "category": "natural",
    },
    {
        "query": "新入社員のメンター制度や最初の1週間のゴール",
        "expected": "新入社員向け_オンボーディング手順.md",
        "category": "natural",
    },
    {
        "query": "在宅勤務のコアタイムは何時から何時まで？",
        "expected": "リモートワーク勤務規定.md",
        "category": "natural",
    },

    # ─── カテゴリ3: 辞書に頼らない通常クエリ / 過去ノート (10問) ───
    {
        "query": "FastAPI Python 非同期Webサーバー",
        "expected": "FastAPI_Python.md",
        "category": "general",
    },
    {
        "query": "大気圏再突入時の熱防護システム Thermal Protection Systems",
        "expected": "TPS_Overview.md",
        "category": "general",
    },
    {
        "query": "PICA-X フェノール樹脂含浸炭素複合材 耐熱材料",
        "expected": "PICA-X.md",
        "category": "general",
    },
    {
        "query": "Pyrolysis 熱分解の化学反応と生成物",
        "expected": "Pyrolysis.md",
        "category": "general",
    },
    {
        "query": "宇宙機のアブレーション材料と耐熱タイル 吸熱",
        "expected": "TPS_Overview.md",
        "category": "general",
    },
    {
        "query": "FastAPIのエンドポイント定義と自動Swaggerドキュメント",
        "expected": "FastAPI_Python.md",
        "category": "general",
    },
    {
        "query": "SpaceXの宇宙船熱防御システム PICA-X",
        "expected": "PICA-X.md",
        "category": "general",
    },
    {
        "query": "バイオマス熱分解とバイオ炭の生成プロセス",
        "expected": "Pyrolysis.md",
        "category": "general",
    },
    {
        "query": "熱分解反応速度論 Arrhenius則 熱伝導方程式",
        "expected": "TPS_Overview.md",
        "category": "general",
    },
    {
        "query": "Pydanticと型ヒントを活用したPythonフレームワーク",
        "expected": "FastAPI_Python.md",
        "category": "general",
    },
]


@pytest.fixture(scope="module")
def benchmark_environment():
    """テスト用Vaultとモデルのセットアップフィクスチャ"""
    vault_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sample_vault"))
    db_path = os.path.join(vault_path, ".vector_search", "index.db")
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models", "ruri-v3-30m"))

    if not os.path.exists(model_path):
        pytest.skip("ruri-v3-30m モデルが存在しません")

    device = auto_detect_device()
    embedder = Embedder(model_path=model_path, device=device)

    # 1. 辞書ありでインデックス作成
    indexer = IndexManager(vault_path=vault_path, embedder=embedder)
    indexer.run_index(force_reindex=True)

    # 2. 辞書ありSearcher
    searcher_with_dict = VectorSearcher(db_path=db_path, embedder=embedder)

    # 3. 辞書なしSearcher（比較用: glossary=None）
    searcher_no_dict = VectorSearcher(db_path=db_path, embedder=embedder, glossary=None)
    searcher_no_dict.glossary = None  # 明示的に無効化

    return {
        "vault_path": vault_path,
        "searcher_with_dict": searcher_with_dict,
        "searcher_no_dict": searcher_no_dict,
    }


def test_category_1_acronym_queries(benchmark_environment):
    """カテゴリ1: 略称・専門用語クエリ（10問）のHit Rate検証"""
    searcher = benchmark_environment["searcher_with_dict"]
    acronym_items = [q for q in BENCHMARK_DATASET if q["category"] == "acronym"]
    
    hits = 0
    print("\n--- 【カテゴリ1: 略称・専門用語クエリ検証】 ---")
    for item in acronym_items:
        resp = searcher.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)
        top1_path = resp.results[0].path if resp.results else ""
        top1_score = resp.results[0].score if resp.results else 0.0
        is_hit = item["expected"] in top1_path
        if is_hit:
            hits += 1
        print(f"[{'PASS' if is_hit else 'FAIL'}] クエリ: {item['query']} -> Top1: {top1_path} (Score: {top1_score:.4f})")
        assert len(resp.detected_terms) >= 1  # 用語が検知されていること

    hit_rate = hits / len(acronym_items)
    print(f"カテゴリ1 Hit Rate@1: {hit_rate * 100:.1f}% ({hits}/{len(acronym_items)})")
    assert hit_rate >= 0.90  # 90%以上


def test_category_2_natural_language_queries(benchmark_environment):
    """カテゴリ2: 自然言語・会話調質問クエリ（10問）のHit Rate検証"""
    searcher = benchmark_environment["searcher_with_dict"]
    natural_items = [q for q in BENCHMARK_DATASET if q["category"] == "natural"]
    
    hits = 0
    print("\n--- 【カテゴリ2: 自然言語・会話調質問クエリ検証】 ---")
    for item in natural_items:
        resp = searcher.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)
        top1_path = resp.results[0].path if resp.results else ""
        top1_score = resp.results[0].score if resp.results else 0.0
        is_hit = item["expected"] in top1_path
        if is_hit:
            hits += 1
        print(f"[{'PASS' if is_hit else 'FAIL'}] クエリ: {item['query']} -> Top1: {top1_path} (Score: {top1_score:.4f})")

    hit_rate = hits / len(natural_items)
    print(f"カテゴリ2 Hit Rate@1: {hit_rate * 100:.1f}% ({hits}/{len(natural_items)})")
    assert hit_rate >= 0.90  # 90%以上


def test_category_3_general_queries_no_regression(benchmark_environment):
    """カテゴリ3: 辞書に頼らない通常クエリ（10問）の精度維持・リグレッション検証"""
    searcher = benchmark_environment["searcher_with_dict"]
    general_items = [q for q in BENCHMARK_DATASET if q["category"] == "general"]
    
    hits = 0
    scores = []
    print("\n--- 【カテゴリ3: 通常クエリ・スコア維持検証】 ---")
    for item in general_items:
        resp = searcher.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)
        top1_path = resp.results[0].path if resp.results else ""
        top1_score = resp.results[0].score if resp.results else 0.0
        is_hit = item["expected"] in top1_path
        if is_hit:
            hits += 1
        scores.append(top1_score)
        print(f"[{'PASS' if is_hit else 'FAIL'}] クエリ: {item['query']} -> Top1: {top1_path} (Score: {top1_score:.4f})")

    hit_rate = hits / len(general_items)
    avg_score = sum(scores) / len(scores)
    print(f"カテゴリ3 Hit Rate@1: {hit_rate * 100:.1f}% ({hits}/{len(general_items)}) | 平均スコア: {avg_score:.4f}")
    assert hit_rate == 1.0  # 既存ノートは100%正しくヒット
    assert avg_score >= 0.75  # スコアが十分に高いこと


def test_score_comparison_with_and_without_dict(benchmark_environment):
    """全30問における「辞書あり」vs「辞書なし」のスコア比較ベンチマーク"""
    searcher_with = benchmark_environment["searcher_with_dict"]
    searcher_no = benchmark_environment["searcher_no_dict"]

    acronym_items = [q for q in BENCHMARK_DATASET if q["category"] == "acronym"]
    general_items = [q for q in BENCHMARK_DATASET if q["category"] == "general"]

    # 1. 略称クエリにおけるスコア上昇幅の検証
    score_diffs = []
    for item in acronym_items:
        resp_with = searcher_with.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)
        resp_no = searcher_no.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)

        score_with = resp_with.results[0].score if resp_with.results and item["expected"] in resp_with.results[0].path else 0.0
        score_no = resp_no.results[0].score if resp_no.results and item["expected"] in resp_no.results[0].path else 0.0
        
        diff = score_with - score_no
        score_diffs.append(diff)

    avg_acronym_gain = sum(score_diffs) / len(score_diffs)

    # 2. 通常クエリにおけるスコア劣化がないことの検証
    gen_score_diffs = []
    for item in general_items:
        resp_with = searcher_with.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)
        resp_no = searcher_no.search(query=item["query"], mode=SearchMode.CHUNK, top_k=3)

        score_with = resp_with.results[0].score if resp_with.results else 0.0
        score_no = resp_no.results[0].score if resp_no.results else 0.0
        gen_score_diffs.append(score_with - score_no)

    avg_gen_diff = sum(gen_score_diffs) / len(gen_score_diffs)

    print("\n" + "=" * 65)
    print("【辞書あり vs 辞書なし スコア比較ベンチマーク結果】")
    print(f"・専門用語クエリの平均スコア上昇: +{avg_acronym_gain:.4f} (大幅向上)")
    print(f"・通常クエリのスコア変動       : {avg_gen_diff:+.4f} (劣化なし)")
    print("=" * 65)

    assert avg_acronym_gain >= 0.15  # 専門用語で平均+0.15以上の大幅スコアアップ
    assert avg_gen_diff >= -0.01     # 通常クエリでスコアが落ちていないこと
