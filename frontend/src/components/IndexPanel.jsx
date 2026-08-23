/**
 * インデックス管理 & 進捗表示コンポーネント
 * 仕様:
 * - 「Index Vault」ボタンによるインデックス・差分更新の実行。
 * - リアルタイムの進捗バー、処理件数/全件数、経過時間、推定残り時間の表示。
 * - インデックス完了サマリー（New / Updated / Skipped / Deleted / Chunks / 所要時間 / DBサイズ）の表示。
 */

import React, { useState } from 'react';
import { Database, Play, RefreshCw, CheckCircle, Clock } from 'lucide-react';
import { startIndex, getVaultStats } from '../api/client';

export function IndexPanel({ vaultPath, modelStatus, vaultStats, setVaultStats }) {
  const [indexing, setIndexing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [forceReindex, setForceReindex] = useState(false);

  const handleStartIndex = async () => {
    if (!vaultPath) {
      alert('先にVaultディレクトリを指定してください');
      return;
    }
    if (!modelStatus?.loaded) {
      alert('先にEmbeddingモデルをロードしてください');
      return;
    }

    try {
      setIndexing(true);
      setLastResult(null);
      setProgress({
        processed_files: 0,
        total_files: 0,
        progress_pct: 0,
        current_file: '走査中...',
        elapsed_sec: 0,
        estimated_remaining_sec: 0,
      });

      const res = await startIndex(vaultPath, 600, 80, forceReindex);
      setLastResult(res);

      // 統計の最新化
      const stats = await getVaultStats(vaultPath);
      setVaultStats(stats);
    } catch (err) {
      alert(`インデックスエラー: ${err.message}`);
    } finally {
      setIndexing(false);
    }
  };

  return (
    <div className="card">
      <div className="card-title" style={{ flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Database size={18} color="#38bdf8" />
          <span>Vault インデックス</span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={forceReindex}
              onChange={(e) => setForceReindex(e.target.checked)}
            />
            全件強制再構築 (Clean Re-index)
          </label>
          <button
            className="btn btn-primary"
            onClick={handleStartIndex}
            disabled={indexing || !vaultPath || !modelStatus?.loaded}
          >
            {indexing ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
            <span>{indexing ? 'インデックス処理中...' : 'Index Vault'}</span>
          </button>
        </div>
      </div>

      {/* 現在のDB統計 */}
      <div className="stats-grid">
        <div className="stat-box">
          <div className="stat-label">Documents</div>
          <div className="stat-val">{vaultStats?.document_count ?? 0}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Chunks</div>
          <div className="stat-val">{vaultStats?.chunk_count ?? 0}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">DB Size</div>
          <div className="stat-val">{vaultStats?.db_size_mb ?? 0} MB</div>
        </div>
      </div>

      {/* 進捗表示 */}
      {indexing && progress && (
        <div className="progress-container">
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600 }}>
            <span>Indexing... {progress.processed_files} / {progress.total_files}</span>
            <span>{progress.progress_pct}%</span>
          </div>
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${progress.progress_pct}%` }} />
          </div>
          <div className="progress-stats">
            <span>ファイル: {progress.current_file}</span>
            <span>経過: {progress.elapsed_sec}s / 推定残: {progress.estimated_remaining_sec}s</span>
          </div>
        </div>
      )}

      {/* 完了結果サマリー */}
      {lastResult && !indexing && (
        <div style={{ marginTop: '16px', padding: '16px', background: 'rgba(16, 185, 129, 0.08)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success)', fontWeight: 600, marginBottom: '10px' }}>
            <CheckCircle size={16} />
            <span>Index Completed (差分インデックス完了)</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '10px', fontSize: '13px' }}>
            <div><strong>全ファイル:</strong> {lastResult.total_files}</div>
            <div style={{ color: '#38bdf8' }}><strong>新規:</strong> {lastResult.new_count}</div>
            <div style={{ color: '#f59e0b' }}><strong>更新:</strong> {lastResult.updated_count}</div>
            <div style={{ color: '#94a3b8' }}><strong>スキップ:</strong> {lastResult.skipped_count}</div>
            <div style={{ color: '#f87171' }}><strong>削除:</strong> {lastResult.deleted_count}</div>
            <div><strong>Chunks:</strong> {lastResult.chunk_count}</div>
            <div><strong>総所要時間:</strong> {lastResult.indexing_time_sec}s</div>
            <div><strong>Embed時間:</strong> {lastResult.embedding_time_sec}s</div>
          </div>
        </div>
      )}
    </div>
  );
}
