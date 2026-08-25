/**
 * インデックス管理 & 進捗表示コンポーネント
 * 仕様:
 * - 「Index Vault」ボタンによるインデックス・差分更新の実行。
 * - 対象拡張子（カンマ区切り）の入力・指定機能（初期値: .md, .markdown, .txt）。
 * - リアルタイムの進捗バー、処理件数/全件数、経過時間、推定残り時間の表示。
 * - インデックス完了サマリー（New / Updated / Skipped / Deleted / Chunks / 所要時間 / DBサイズ）の表示。
 */

import React, { useState } from 'react';
import { Database, Play, RefreshCw, CheckCircle, Clock, FileText } from 'lucide-react';
import { startIndex, getVaultStats } from '../api/client';

export function IndexPanel({ vaultPath, modelStatus, vaultStats, setVaultStats }) {
  const [indexing, setIndexing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [forceReindex, setForceReindex] = useState(false);
  const [targetExtsInput, setTargetExtsInput] = useState('.md, .markdown, .txt');

  const handleStartIndex = async () => {
    if (!vaultPath) {
      alert('先にVaultディレクトリを指定してください');
      return;
    }
    if (!modelStatus?.loaded) {
      alert('先にEmbeddingモデルをロードしてください');
      return;
    }

    // カンマまたはスペースで拡張子を分割して配列化
    const parsedExts = targetExtsInput
      .split(/[,;\s]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
      .map((s) => (s.startsWith('.') ? s : `.${s}`));

    if (parsedExts.length === 0) {
      alert('対象の拡張子を最低1つ指定してください（例: .md）');
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

      const res = await startIndex(vaultPath, 600, 80, forceReindex, parsedExts);
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

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
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

      {/* 対象拡張子の設定インプット */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          <FileText size={14} color="#a855f7" />
          <span>対象拡張子:</span>
        </div>
        <input
          type="text"
          value={targetExtsInput}
          onChange={(e) => setTargetExtsInput(e.target.value)}
          placeholder=".md, .markdown, .txt"
          disabled={indexing}
          style={{
            flex: 1,
            minWidth: '200px',
            padding: '6px 10px',
            fontSize: '12px',
            backgroundColor: 'rgba(0, 0, 0, 0.25)',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            color: 'var(--text-color)',
          }}
        />
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          ※ .excalidraw.md や図面バイナリは自動除外されます
        </span>
      </div>

      {/* 実行中プログレスバー */}
      {indexing && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
            <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
              {progress?.current_file || '処理中...'}
            </span>
            <span style={{ fontWeight: 600, color: 'var(--primary-color)' }}>
              {progress?.processed_files || 0} / {progress?.total_files || 0} ファイル
            </span>
          </div>

          <div style={{ width: '100%', height: '8px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${progress?.total_files > 0 ? (progress.processed_files / progress.total_files) * 100 : 0}%`,
                height: '100%',
                backgroundColor: 'var(--primary-color)',
                transition: 'width 0.2s ease',
              }}
            />
          </div>
        </div>
      )}

      {/* 完了サマリー */}
      {lastResult && (
        <div
          style={{
            marginTop: '12px',
            padding: '12px 16px',
            backgroundColor: 'rgba(34, 197, 94, 0.08)',
            border: '1px solid rgba(34, 197, 94, 0.2)',
            borderRadius: '8px',
            fontSize: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#4ade80', fontWeight: 600, marginBottom: '8px' }}>
            <CheckCircle size={16} />
            <span>インデックス完了</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', color: 'var(--text-muted)' }}>
            <div>新規追加: <strong style={{ color: 'var(--text-color)' }}>{lastResult.new_count ?? 0}</strong></div>
            <div>更新: <strong style={{ color: 'var(--text-color)' }}>{lastResult.updated_count ?? 0}</strong></div>
            <div>スキップ: <strong style={{ color: 'var(--text-color)' }}>{lastResult.skipped_count ?? 0}</strong></div>
            <div>削除: <strong style={{ color: 'var(--text-color)' }}>{lastResult.deleted_count ?? 0}</strong></div>
            <div>総チャンク数: <strong style={{ color: 'var(--text-color)' }}>{lastResult.total_chunks ?? lastResult.new_chunks ?? 0}</strong></div>
            <div>所要時間: <strong style={{ color: 'var(--text-color)' }}>{lastResult.total_time_sec != null ? Number(lastResult.total_time_sec).toFixed(2) : '0.00'}s</strong></div>
          </div>
        </div>
      )}
    </div>
  );
}
