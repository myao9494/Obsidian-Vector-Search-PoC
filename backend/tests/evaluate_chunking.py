"""
実Vaultデータに基づくチャンキング & 検索精度評価スクリプト
仕様:
- /Users/mine/000_work/obsidian-dagnetz/01_data の実Markdownノートに対する自然言語検索の定量評価。
- 指標: Hit Rate@1, Hit Rate@3, Hit Rate@5, MRR (Mean Reciprocal Rank), 平均レスポンス時間(ms)。
- チャンキングアルゴリズム（旧方式 vs 見出し階層・タグ保持最適化方式）の比較・検証に使用。
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

# 評価データセット（クエリ と 正解ノートのファイル名キーワード/タイトル）
EVALUATION_DATASET = [
    {
        "query": "確定申告でマイナス繰越がない場合の注意点や配当控除",
        "expected_filename": "確定申告.md",
        "category": "税金・生活"
    },
    {
        "query": "転換社債の発行で株価が下落する希薄化懸念の理由",
        "expected_filename": "転換社債（CB）で株価下落の理由を解説.md",
        "category": "株式・投資"
    },
    {
        "query": "Obsidianの設定をGitHubに保存して会社で共用する",
        "expected_filename": "setting obsidianの設定をgithubに保存.md",
        "category": "ツール・技術"
    },
    {
        "query": "クラリネットを購入した店舗や楽器専門店ヨモギヤ",
        "expected_filename": "クラリネット.md",
        "category": "生活・楽器"
    },
    {
        "query": "全固体電池の関連銘柄や技術動向",
        "expected_filename": "全固体電池.md",
        "category": "株式・技術"
    },
    {
        "query": "テイカ 4027 銘柄情報",
        "expected_filename": "4027 テイカ.md",
        "category": "株式・銘柄"
    },
    {
        "query": "SANEI 6230 の業績と企業分析",
        "expected_filename": "6230 SANEI.md",
        "category": "株式・銘柄"
    },
    {
        "query": "つけ麺六三六のラーメンや食事",
        "expected_filename": "つけ麺 六三六.md",
        "category": "グルメ"
    },
    {
        "query": "Apple Watch SE3 の情報",
        "expected_filename": "apple watch SE3.md",
        "category": "ガジェット"
    },
    {
        "query": "信越化学の銘柄分析と業績推移",
        "expected_filename": "信越化学.md",
        "category": "株式・銘柄"
    },
    {
        "query": "ブラウザの自動操作ログイン後の要素試験",
        "expected_filename": "要素試験 ブラウザの自動操作開発手法 (ログイン後).md",
        "category": "開発・技術"
    },
    {
        "query": "免疫生物研究所 4570 の株価材料",
        "expected_filename": "4570 免疫生物研究所.md",
        "category": "株式・銘柄"
    },
    {
        "query": "Google AI Pro に関するまとめ",
        "expected_filename": "Google AI Pro.md",
        "category": "AI・ツール"
    },
    {
        "query": "ドリームベッド 7791 の銘柄分析",
        "expected_filename": "7791 ドリームベッド.md",
        "category": "株式・銘柄"
    },
    {
        "query": "メディカル一光グループ 3353 薬局事業",
        "expected_filename": "3353 メディカル一光グループ.md",
        "category": "株式・銘柄"
    }
]


@dataclass
class EvalMetricResult:
    hit_rate_at_1: float
    hit_rate_at_3: float
    hit_rate_at_5: float
    mrr: float
    avg_search_time_ms: float
    total_queries: int
    details: List[Dict]


def evaluate_search_engine(
    search_func: Callable[[str, int], List[Dict]],
    eval_dataset: List[Dict] = EVALUATION_DATASET
) -> EvalMetricResult:
    """
    検索関数に対してデータセットを一括実行し、Hit RateとMRRを計測する
    
    Args:
        search_func: (query: str, top_k: int) -> List[{"path": str, "score": float, ...}]
    """
    total = len(eval_dataset)
    hits_1 = 0
    hits_3 = 0
    hits_5 = 0
    rr_sum = 0.0
    times = []
    details = []

    for item in eval_dataset:
        query = item["query"]
        expected = item["expected_filename"]
        
        t0 = time.perf_counter()
        results = search_func(query, 10)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        times.append(elapsed_ms)

        # 検索結果のパス一覧から正解ファイルの順位を特定
        rank = None
        for idx, res in enumerate(results):
            path_str = res.get("path", "")
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
        else:
            rr_sum += 0.0

        details.append({
            "query": query,
            "expected": expected,
            "rank": rank,
            "top1_result": results[0]["path"] if results else None,
            "top1_score": results[0].get("score", 0.0) if results else 0.0,
            "elapsed_ms": elapsed_ms
        })

    return EvalMetricResult(
        hit_rate_at_1=hits_1 / total,
        hit_rate_at_3=hits_3 / total,
        hit_rate_at_5=hits_5 / total,
        mrr=rr_sum / total,
        avg_search_time_ms=float(np.mean(times)) if times else 0.0,
        total_queries=total,
        details=details
    )
