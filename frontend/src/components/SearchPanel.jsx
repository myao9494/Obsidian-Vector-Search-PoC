/**
 * ベクトル検索パネルコンポーネント
 * 仕様:
 * - 検索モード（Document / Chunk）のトグル切り替え。
 * - クエリ入力欄および検索実行ボタン。
 * - 検索処理時間（Embedding時間 vs ベクトル類似度計算時間）の分離メトリクス表示。
 */

import React, { useState } from 'react';
import { Search, FileText, Layers, Zap, Clock } from 'lucide-react';
import { searchVector } from '../api/client';

export function SearchPanel({
  vaultPath,
  modelStatus,
  searchMode,
  setSearchMode,
  setSearchResults,
  setSearchMetrics,
  searchMetrics,
  searchQuery,
  setSearchQuery,
}) {
  const [searching, setSearching] = useState(false);
  const [minScore, setMinScore] = useState(0.0);
  const [keywordBoost, setKeywordBoost] = useState(true);

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    if (!vaultPath) {
      alert('先にVaultを指定してください');
      return;
    }
    if (!modelStatus?.loaded) {
      alert('先にモデルをロードしてください');
      return;
    }

    try {
      setSearching(true);
      const res = await searchVector(vaultPath, searchQuery.trim(), searchMode, 20, minScore, keywordBoost, 0.08);
      setSearchResults(res.results || []);
      setSearchMetrics({
        query_embedding_time_ms: res.query_embedding_time_ms,
        search_time_ms: res.search_time_ms,
        total_time_ms: res.total_time_ms,
        total_candidates: res.total_candidates,
      });
    } catch (err) {
      alert(`検索エラー: ${err.message}`);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="card">
      <div className="card-title">
        <Search size={18} color="#f59e0b" />
        <span>ベクトル検索 (Vector Search)</span>
      </div>

      <form onSubmit={handleSearch}>
        {/* モード選択 */}
        <div className="form-group">
          <label className="form-label">Search Mode</label>
          <div className="mode-selector">
            <div
              className={`mode-option ${searchMode === 'document' ? 'active' : ''}`}
              onClick={() => setSearchMode('document')}
            >
              <FileText size={14} />
              <span>Document モード (1 Note = 1 Vector)</span>
            </div>
            <div
              className={`mode-option ${searchMode === 'chunk' ? 'active' : ''}`}
              onClick={() => setSearchMode('chunk')}
            >
              <Layers size={14} />
              <span>Chunk モード (段落・文脈単位)</span>
            </div>
          </div>
        </div>

        {/* クエリ入力 */}
        <div className="form-group">
          <div className="input-row">
            <input
              type="text"
              className="input-text"
              placeholder="例: PICA-Xの熱分解モデルについて"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={searching || !searchQuery.trim() || !vaultPath || !modelStatus?.loaded}
            >
              <Search size={16} />
              <span>{searching ? '検索中...' : 'Search'}</span>
            </button>
          </div>
        </div>

        {/* 精度調整コントロール */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'center', padding: '10px 14px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginBottom: '14px', fontSize: '13px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: 'var(--text-main)' }}>
            <input
              type="checkbox"
              checked={keywordBoost}
              onChange={(e) => setKeywordBoost(e.target.checked)}
            />
            <span>🎯 キーワード一致ブースト (Lexical Boost: 無関係な誤ヒットを抑制)</span>
          </label>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginLeft: 'auto' }}>
            <span style={{ color: 'var(--text-muted)' }}>最小類似度閾値 (Filter):</span>
            <input
              type="range"
              min="0.0"
              max="0.90"
              step="0.05"
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              style={{ cursor: 'pointer' }}
            />
            <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 'bold', color: minScore > 0 ? 'var(--accent)' : 'var(--text-dim)', minWidth: '40px' }}>
              {minScore > 0 ? `≥ ${minScore.toFixed(2)}` : 'OFF'}
            </span>
          </div>
        </div>
      </form>

      {/* 検索性能メトリクス */}
      {searchMetrics && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '12px', color: 'var(--text-muted)', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Zap size={14} color="#f59e0b" />
            <span>対象件数: <strong>{searchMetrics.total_candidates} 件</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={14} color="#38bdf8" />
            <span>Query Embed: <strong>{searchMetrics.query_embedding_time_ms} ms</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={14} color="#10b981" />
            <span>類似度計算 (NumPy): <strong>{searchMetrics.search_time_ms} ms</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={14} color="#6366f1" />
            <span>合計時間: <strong>{searchMetrics.total_time_ms} ms</strong></span>
          </div>
        </div>
      )}
    </div>
  );
}
