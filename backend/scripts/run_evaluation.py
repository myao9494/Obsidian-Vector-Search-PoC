"""
実Vaultデータを用いたチャンキング最適化・検索精度評価ランナー
仕様:
- Obsidian Vault: /Users/mine/000_work/obsidian-dagnetz/01_data
- Embeddingモデル: ruri-v3-310m (Apple Silicon MPS / Windows CPU)
- 検索エンジン: FAISS
- 評価データセット（EVALUATION_DATASET）を実行し、Hit Rate@1, @3, @5, MRR, 検索時間を算出・表示。
"""

import os
import sys
import time
from pathlib import Path

# パス設定
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir / "backend"))

from app.embedder import Embedder, auto_detect_device
from app.indexer import IndexManager
from app.searcher import VectorSearcher, SearchMode
from tests.evaluate_chunking import evaluate_search_engine, EVALUATION_DATASET


def main():
    vault_path = "/Users/mine/000_work/obsidian-dagnetz/01_data"
    model_path = str(root_dir / "models" / "ruri-v3-310m")

    if not os.path.exists(vault_path):
        print(f"[エラー] Vaultパスが存在しません: {vault_path}")
        return

    if not os.path.exists(model_path):
        print(f"[エラー] モデルパスが存在しません: {model_path}")
        return

    device = auto_detect_device()
    print("=" * 70)
    print("  Obsidian Vector Search PoC - チャンキング最適化 & FAISS 精度評価")
    print("=" * 70)
    print(f"  Vault パス  : {vault_path}")
    print(f"  モデル パス : {model_path} (ruri-v3-310m)")
    print(f"  推論デバイス: {device}")
    print("=" * 70)

    # 1. Embedder の初期化
    print("\n[1/3] Embedder のロード中...")
    t0 = time.time()
    embedder = Embedder(model_path=model_path, device=device)
    print(f"  --> ロード完了 ({time.time() - t0:.2f}s, 次元数: {embedder.embedding_dim}d)")

    # 2. インデックス作成 (全件新規構築)
    print("\n[2/3] Vault インデックスの全件再構築中 (ruri-v3-310m + 最適化チャンキング)...")
    indexer = IndexManager(vault_path=vault_path, embedder=embedder)
    t_idx0 = time.time()
    result = indexer.run_index(
        chunk_size=500,
        chunk_overlap=80,
        force_reindex=True  # 全件再構築
    )
    print(f"  --> インデックス完了 ({time.time() - t_idx0:.2f}s)")
    print(f"      総ファイル数: {result.total_files} (新規: {result.new_count}, 更新: {result.updated_count}, スキップ: {result.skipped_count})")
    print(f"      チャンク総数: {result.chunk_count}, DBサイズ: {result.db_size_mb:.2f}MB")

    # 3. 検索精度評価の実行
    print("\n[3/3] 評価データセットによる検索精度・速度の測定中...")
    db_path = str(Path(vault_path) / ".vector_search" / "index.db")
    searcher = VectorSearcher(db_path=db_path, embedder=embedder)

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

    # 結果サマリー表示
    print("\n" + "=" * 70)
    print("  🏆 評価結果サマリー (ruri-v3-310m + FAISS + 最適化チャンキング)")
    print("=" * 70)
    print(f"  Hit Rate @ 1 : {eval_result.hit_rate_at_1 * 100:.1f}% ({int(eval_result.hit_rate_at_1 * eval_result.total_queries)} / {eval_result.total_queries})")
    print(f"  Hit Rate @ 3 : {eval_result.hit_rate_at_3 * 100:.1f}% ({int(eval_result.hit_rate_at_3 * eval_result.total_queries)} / {eval_result.total_queries})")
    print(f"  Hit Rate @ 5 : {eval_result.hit_rate_at_5 * 100:.1f}% ({int(eval_result.hit_rate_at_5 * eval_result.total_queries)} / {eval_result.total_queries})")
    print(f"  MRR (Mean RR): {eval_result.mrr:.4f}")
    print(f"  平均検索時間 : {eval_result.avg_search_time_ms:.2f} ms")
    print("=" * 70)

    print("\n【詳細クエリ別結果】")
    for idx, d in enumerate(eval_result.details, start=1):
        status = f"✅ Rank {d['rank']}" if d["rank"] is not None else "❌ Not Found"
        top1 = Path(d["top1_result"]).name if d["top1_result"] else "None"
        print(f"[{idx:02d}] {d['query']}")
        print(f"     期待: {d['expected']} | 結果: {status} (Top 1: {top1}, Score: {d['top1_score']:.4f}, {d['elapsed_ms']:.1f}ms)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
