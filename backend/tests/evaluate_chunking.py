"""
実Vaultデータに基づくチャンキング & 検索精度評価スクリプト
仕様:
- /Users/mine/000_work/obsidian-dagnetz/01_data の実Markdownノートに対する自然言語検索の定量評価。
- データセットA（基本15問）、データセットB（新規追加20問）、データセットC（拡張25問: 合計60問）をサポート。
- 指標: Hit Rate@1, Hit Rate@3, Hit Rate@5, MRR, 平均検索時間(ms), スコア飽和率, スコア標準偏差。
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

# 評価データセット A（基本15問）
EVALUATION_DATASET_A = [
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

# 評価データセット B（新規20問: 日常、生活、旅行、健康、個人開発、技術、株式）
EVALUATION_DATASET_B = [
    {
        "query": "Macのローカル環境でmlx-whisperを使って動画から文字起こしする",
        "expected_filename": "動画からローカルで文字起こしする方法.md",
        "category": "AI・ツール"
    },
    {
        "query": "オキシクリーンの粉末とお湯を使った泡スプレーの作り方手順",
        "expected_filename": "オキシクリーンの泡スプレー.md",
        "category": "生活・掃除"
    },
    {
        "query": "上西内科で紹介された血糖値を下げる筋トレや有酸素運動",
        "expected_filename": "血糖値を下げるトレーニング.md",
        "category": "健康・病院"
    },
    {
        "query": "飛騨高山への旅行で食べた高山ラーメンやいちご大福",
        "expected_filename": "飛驒高山の旅.md",
        "category": "旅行・グルメ"
    },
    {
        "query": "ローソンアプリとApple初売りのくじキャンペーン",
        "expected_filename": "ローソンアプリ.md",
        "category": "生活・アプリ"
    },
    {
        "query": "Geminiの新APIでDeep Researchを呼び出す要素試験",
        "expected_filename": "要素試験 Deep Researchを呼び出せるGeminiの新API.md",
        "category": "AI・技術"
    },
    {
        "query": "ピーパンドットコム 3559 を買った理由",
        "expected_filename": "3559　ピーパンドットコム 買った理由.md",
        "category": "株式・投資"
    },
    {
        "query": "コーエーテクモホールディングス 3635 の銘柄分析",
        "expected_filename": "コーエーテクモホールディングス 3635.md",
        "category": "株式・銘柄"
    },
    {
        "query": "四季報データのパース処理とスクレイピング",
        "expected_filename": "四季報データのパース.md",
        "category": "開発・データ"
    },
    {
        "query": "発電所やトランス重電系のAI電力需要",
        "expected_filename": "重電系､トランス､発電所､AI需要.md",
        "category": "株式・テーマ"
    },
    {
        "query": "個人開発のガントチャートアプリ gantt chart",
        "expected_filename": "gantt_chart_myao_kojin 個人開発.md",
        "category": "個人開発"
    },
    {
        "query": "メールアドレス作成ツールの個人開発",
        "expected_filename": "mail_adress_creater 個人開発.md",
        "category": "個人開発"
    },
    {
        "query": "フライヤー 323A の銘柄情報とビジネスモデル",
        "expected_filename": "フライヤー 323A.md",
        "category": "株式・銘柄"
    },
    {
        "query": "マジックスピード4 アシックスのランニングシューズ",
        "expected_filename": "マジックスピード 4.md",
        "category": "生活・靴"
    },
    {
        "query": "アプリックスの株価や材料",
        "expected_filename": "アプリックス.md",
        "category": "株式・銘柄"
    },
    {
        "query": "日常で使う便利なgitコマンド一覧",
        "expected_filename": "git command.md",
        "category": "開発・技術"
    },
    {
        "query": "楽天証券の口座やサービス",
        "expected_filename": "楽天証券.md",
        "category": "株式・口座"
    },
    {
        "query": "ファイルマネージャーの個人開発 file_viewer後継",
        "expected_filename": "file_manager 個人開発.md",
        "category": "個人開発"
    },
    {
        "query": "IPOセカンダリの投資手法と立ち回り",
        "expected_filename": "IPOセカンダリ.md",
        "category": "株式・投資"
    },
    {
        "query": "ポプラのコンビニや銘柄情報",
        "expected_filename": "ポプラ.md",
        "category": "株式・銘柄"
    }
]

# 評価データセット C（新規拡張25問: 技術ガイド、開発運用、制度、銘柄分析、日常）
EVALUATION_DATASET_C = [
    {
        "query": "macOSでuvを使ってPython3.12環境を構築するガイド",
        "expected_filename": "uv による Python 環境構築ガイド (macOS).md",
        "category": "開発・環境"
    },
    {
        "query": "Spoonfeederのコード反映運用ルールまとめ",
        "expected_filename": "Spoonfeeder 運用ルール まとめ.md",
        "category": "開発・運用"
    },
    {
        "query": "J-Quants APIのプラン別データ仕様と無料プランの制限",
        "expected_filename": "jquants.md",
        "category": "開発・株データ"
    },
    {
        "query": "ソニー 6758 のPER割安感とソニーFGスピンオフ",
        "expected_filename": "ソニー 6758.md",
        "category": "株式・銘柄"
    },
    {
        "query": "海底ケーブル関連銘柄 住友電工や神島化学工業",
        "expected_filename": "海底ケーブル.md",
        "category": "株式・テーマ"
    },
    {
        "query": "小牧図書館の利用とwifi接続",
        "expected_filename": "小牧図書館.md",
        "category": "生活・施設"
    },
    {
        "query": "ノムラシステムコーポレーション 3940 の銘柄情報",
        "expected_filename": "3940 ノムラシステムコーポレーション.md",
        "category": "株式・銘柄"
    },
    {
        "query": "銘柄ランクの考え方と投資判断の基準",
        "expected_filename": "銘柄ランクの考え方.md",
        "category": "株式・手法"
    },
    {
        "query": "アエリア 3758 の銘柄分析と材料",
        "expected_filename": "3758 アエリア.md",
        "category": "株式・銘柄"
    },
    {
        "query": "東証再編と東証経過措置関連の銘柄",
        "expected_filename": "東証再編（東証経過措置）関連.md",
        "category": "株式・制度"
    },
    {
        "query": "Tailscaleを使ったローカルネットワーク構築",
        "expected_filename": "tailscale.md",
        "category": "開発・インフラ"
    },
    {
        "query": "ふるさと納税の申し込みや限度額の計算",
        "expected_filename": "ふるさと納税.md",
        "category": "生活・税金"
    },
    {
        "query": "楽天RSS株価データ管理システムの開発構想",
        "expected_filename": "楽天RSS株価データ管理システム.md",
        "category": "開発・株"
    },
    {
        "query": "株を買うときのチェックリストと事前確認事項",
        "expected_filename": "株を買うときのチェックリスト.md",
        "category": "株式・手法"
    },
    {
        "query": "浅野外科内科の病院情報と診察",
        "expected_filename": "浅野外科内科.md",
        "category": "生活・病院"
    },
    {
        "query": "ミックス指数とグレアム流の割安株投資",
        "expected_filename": "ミックス指数.md",
        "category": "株式・手法"
    },
    {
        "query": "上西内科の通院メモと健康管理",
        "expected_filename": "上西内科.md",
        "category": "生活・病院"
    },
    {
        "query": "柳橋きたろう場内店のお寿司ランチ",
        "expected_filename": "柳橋きたろう場内店 ランチ.md",
        "category": "グルメ"
    },
    {
        "query": "MacBook Pro M1 のスペックと使用感",
        "expected_filename": "mac book pro M1.md",
        "category": "ガジェット"
    },
    {
        "query": "ベイカレントのコンサルティング事業と銘柄分析",
        "expected_filename": "ベイカレント.md",
        "category": "株式・銘柄"
    },
    {
        "query": "株主優待サイトのパスワード管理メモ",
        "expected_filename": "株主優待のサイトメモ パスワードとか.md",
        "category": "株式・優待"
    },
    {
        "query": "リアル損切りを例題にした資金管理の大事さ",
        "expected_filename": "リアル損切りを例題に資金管理の大事さと未来の優位性を伝えます.md",
        "category": "株式・手法"
    },
    {
        "query": "デイトレードのアイデアとトレードルール",
        "expected_filename": "デイトレアイデア.md",
        "category": "株式・手法"
    },
    {
        "query": "4月に仕込む銘柄リストと先回り投資",
        "expected_filename": "4月に仕込む銘柄.md",
        "category": "株式・銘柄"
    },
    {
        "query": "Claude AIの使い方やプロンプト設定",
        "expected_filename": "claude.md",
        "category": "AI・ツール"
    }
]

# 全60問の統合データセット
EVALUATION_DATASET_ALL = EVALUATION_DATASET_A + EVALUATION_DATASET_B + EVALUATION_DATASET_C
EVALUATION_DATASET = EVALUATION_DATASET_ALL


@dataclass
class EvalMetricResult:
    hit_rate_at_1: float
    hit_rate_at_3: float
    hit_rate_at_5: float
    mrr: float
    avg_search_time_ms: float
    saturation_rate: float  # Score == 1.0000 の割合
    score_std: float        # Top 1〜3 スコアの標準偏差
    total_queries: int
    details: List[Dict]


def evaluate_search_engine(
    search_func: Callable[[str, int], List[Dict]],
    eval_dataset: List[Dict] = EVALUATION_DATASET_ALL
) -> EvalMetricResult:
    """
    検索関数に対してデータセットを一括実行し、Hit Rate、MRR、スコア分散を計測する
    """
    total = len(eval_dataset)
    hits_1 = 0
    hits_3 = 0
    hits_5 = 0
    rr_sum = 0.0
    times = []
    details = []
    top_scores = []
    perfect_count = 0

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

        if results:
            t1_score = results[0].get("score", 0.0)
            top_scores.append(t1_score)
            if t1_score >= 0.9999:
                perfect_count += 1

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
        saturation_rate=perfect_count / total if total > 0 else 0.0,
        score_std=float(np.std(top_scores)) if top_scores else 0.0,
        total_queries=total,
        details=details
    )
