/**
 * インデックス管理 & 進捗表示コンポーネント
 * 仕様:
 * - ⚡ 差分インデックス更新（差分学習）ボタン: 変更・新規・削除ノートのみを高速に更新（force_reindex: false）。
 * - 🔄 全件再インデックスボタン: 全ファイルを最初からクリーンに再作成（force_reindex: true）。
 * - 対象拡張子（カンマ区切り）の入力・指定機能（初期値: .md, .markdown, .txt）。
 * - 現在ロード中のモデル情報（モデル名・次元数）および現在のインデックス状況（登録件数・サイズ）の明示。
 * - リアルタイムの進捗バー、処理件数/全件数、経過時間、推定残り時間の表示。
 * - インデックス完了サマリー（差分更新/全件更新、New / Updated / Skipped / Deleted / Chunks / 所要時間 / DBサイズ）の表示。
 */

import React, { useState } from 'react';
import { Database, Zap, RefreshCw, CheckCircle, Clock, FileText, BookOpen, AlertTriangle } from 'lucide-react';
import { startIndex, getVaultStats } from '../api/client';

export function IndexPanel({ vaultPath, modelStatus, vaultStats, setVaultStats, dictionaryStatus, onOpenGlossary, selectedModelType }) {
  const [indexing, setIndexing] = useState(false);
  const [indexMode, setIndexMode] = useState('incremental'); // 'incremental' | 'full'
  const [progress, setProgress] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [targetExtsInput, setTargetExtsInput] = useState('.md, .markdown, .txt');

  const handleStartIndex = async (forceReindex = false) => {
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
      setIndexMode(forceReindex ? 'full' : 'incremental');
      setLastResult(null);
      setProgress({
        processed_files: 0,
        total_files: 0,
        progress_pct: 0,
        current_file: forceReindex ? '全件スキャン中...' : '差分走査中...',
        elapsed_sec: 0,
        estimated_remaining_sec: 0,
      });

      const res = await startIndex(vaultPath, 600, 80, forceReindex, parsedExts);
      res._mode = forceReindex ? 'full' : 'incremental';
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

  const currentModelLabel = selectedModelType === 'standard' ? '👑 標準モデル (ruri-v3-310m: 768d)' : '⚡ 超軽量モデル (ruri-v3-30m: 256d)';

  return (
    <div className="card">
      <div className="card-title" style={{ flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Database size={18} color="#38bdf8" />
          <span>Vault インデックス管理</span>
          <span className="badge badge-poc" style={{ fontSize: '11px', marginLeft: '4px' }}>
            {currentModelLabel}
          </span>
          {vaultStats && (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '4px' }}>
              (登録: <strong style={{ color: 'var(--text-color)' }}>{vaultStats.document_count ?? 0}</strong> ノート / {vaultStats.db_size_mb ?? 0} MB)
            </span>
          )}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* 専門用語辞書 編集ボタン */}
          <button
            className="btn btn-secondary btn-sm"
            onClick={onOpenGlossary}
            title="専門用語・類似語辞書 (Excel/CSV) をWeb画面上で直接編集・保存"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <BookOpen size={14} color="#38bdf8" />
            <span>📖 専門用語辞書</span>
            {dictionaryStatus?.loaded && (
              <span className="badge badge-subtle-cyan">
                {dictionaryStatus.total_entries} 件
              </span>
            )}
          </button>

          {/* ⚡ 差分インデックス更新ボタン (差分学習) */}
          <button
            className="btn btn-primary"
            onClick={() => handleStartIndex(false)}
            disabled={indexing || !vaultPath || !modelStatus?.loaded}
            style={{
              background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 600,
              boxShadow: '0 2px 10px rgba(16, 185, 129, 0.25)',
            }}
            title="変更・新規・削除されたノートのみを高速に検知して差分インデックスを更新します"
          >
            {indexing && indexMode === 'incremental' ? (
              <RefreshCw className="spin" size={15} />
            ) : (
              <Zap size={15} />
            )}
            <span>
              {indexing && indexMode === 'incremental' ? '差分更新中...' : '⚡ 差分インデックス更新'}
            </span>
          </button>

          {/* 🔄 全件再インデックスボタン (Clean Re-index) */}
          <button
            className="btn btn-secondary"
            onClick={() => {
              if (window.confirm('現在のモデルのインデックスを完全に初期化し、全ファイルを再構築しますか？')) {
                handleStartIndex(true);
              }
            }}
            disabled={indexing || !vaultPath || !modelStatus?.loaded}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
            }}
            title="現在のモデルのインデックスを全消去してクリーンに再作成します"
          >
            {indexing && indexMode === 'full' ? (
              <RefreshCw className="spin" size={14} />
            ) : (
              <RefreshCw size={14} />
            )}
            <span>
              {indexing && indexMode === 'full' ? '全件再構築中...' : '🔄 全件再作成'}
            </span>
          </button>
        </div>
      </div>

      {/* 対象拡張子の設定インプット */}
      <div style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
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
          ※ モデルごとに独立したDB（.vector_search/index_&lt;model&gt;.db）が作成されます
        </span>
      </div>

      {/* 実行中プログレスバー */}
      {indexing && (
        <div style={{ marginBottom: '16px', padding: '10px 14px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
            <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
              <span style={{ color: 'var(--primary-color)', fontWeight: 600, marginRight: '6px' }}>
                [{indexMode === 'incremental' ? '⚡ 差分更新' : '🔄 全件再作成'}]
              </span>
              {progress?.current_file || '処理中...'}
            </span>
            <span style={{ fontWeight: 600, color: 'var(--primary-color)' }}>
              {progress?.processed_files || 0} / {progress?.total_files || 0} ファイル ({progress?.progress_pct || 0}%)
            </span>
          </div>

          <div style={{ width: '100%', height: '8px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${progress?.total_files > 0 ? (progress.processed_files / progress.total_files) * 100 : 0}%`,
                height: '100%',
                backgroundColor: indexMode === 'incremental' ? '#10b981' : 'var(--primary-color)',
                transition: 'width 0.2s ease',
              }}
            />
          </div>
          {progress?.estimated_remaining_sec > 0 && (
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px', textAlign: 'right' }}>
              推定残り時間: 約 {progress.estimated_remaining_sec} 秒 (経過: {progress.elapsed_sec}秒)
            </div>
          )}
        </div>
      )}

      {/* 完了サマリー */}
      {lastResult && (
        <div
          style={{
            marginTop: '12px',
            padding: '12px 16px',
            backgroundColor: lastResult._mode === 'incremental' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(56, 189, 248, 0.08)',
            border: `1px solid ${lastResult._mode === 'incremental' ? 'rgba(16, 185, 129, 0.25)' : 'rgba(56, 189, 248, 0.25)'}`,
            borderRadius: '8px',
            fontSize: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: lastResult._mode === 'incremental' ? '#34d399' : '#38bdf8', fontWeight: 600, marginBottom: '8px' }}>
            <CheckCircle size={16} />
            <span>
              {lastResult._mode === 'incremental' ? '⚡ 差分インデックス更新完了' : '🔄 全件再インデックス完了'}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', color: 'var(--text-muted)' }}>
            <div>新規追加: <strong style={{ color: '#34d399' }}>{lastResult.new_count ?? 0}</strong></div>
            <div>更新: <strong style={{ color: '#38bdf8' }}>{lastResult.updated_count ?? 0}</strong></div>
            <div>変更なし(スキップ): <strong style={{ color: 'var(--text-color)' }}>{lastResult.skipped_count ?? 0}</strong></div>
            <div>削除: <strong style={{ color: '#f87171' }}>{lastResult.deleted_count ?? 0}</strong></div>
            <div>総ノート数: <strong style={{ color: 'var(--text-color)' }}>{lastResult.document_count ?? 0}</strong></div>
            <div>総チャンク数: <strong style={{ color: 'var(--text-color)' }}>{lastResult.chunk_count ?? 0}</strong></div>
            <div>所要時間: <strong style={{ color: 'var(--text-color)' }}>{lastResult.indexing_time_sec != null ? Number(lastResult.indexing_time_sec).toFixed(2) : '0.00'}s</strong></div>
            <div>DBサイズ: <strong style={{ color: 'var(--text-color)' }}>{lastResult.db_size_mb ?? 0} MB</strong></div>
          </div>
        </div>
      )}
    </div>
  );
}

