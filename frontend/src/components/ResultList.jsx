/**
 * 検索結果一覧コンポーネント
 * 仕様:
 * - Top 20 検索結果のカード表示（順位、タイトル、コサイン類似度、ファイルパス）。
 * - 選択用チェックボックス（将来のContext Pack作成を想定した人間による選別機能）。
 * - Chunk検索時: ヒット文章および前後文脈（前/ヒット/後）のハイライト表示。
 * - Document検索時: ノート本文のプレビュー表示。
 */

import React, { useState } from 'react';
import { ListFilter, CheckSquare, Square, Copy, Check } from 'lucide-react';

/**
 * テキスト内の検索クエリキーワードをハイライト表示するヘルパーコンポーネント
 */
function HighlightedText({ text, query }) {
  if (!text) return null;
  if (!query || !query.trim()) return <span>{text}</span>;

  // クエリを記号や空白で分割して2文字以上のキーワードを抽出
  const rawTokens = query.trim().split(/[\s\.,、。!?！？\-_/()（）「」『』【】]+/);
  const stopWords = new Set(['について', 'に関する', 'の基礎', 'とは', '概要', '詳細', 'まとめ', '方法', 'どう', 'なに', 'なぜ', 'これ', 'それ']);
  
  const keywords = [];
  // 全体クエリも候補に追加（短縮クエリの場合）
  if (query.trim().length >= 2) keywords.push(query.trim());
  for (const t of rawTokens) {
    const clean = t.trim();
    if (clean.length >= 2 && !stopWords.has(clean)) {
      keywords.push(clean);
    }
  }

  if (keywords.length === 0) return <span>{text}</span>;

  // 重複除去 & 長いキーワードから順にマッチさせる
  const uniqueKw = Array.from(new Set(keywords)).sort((a, b) => b.length - a.length);
  const escapedKw = uniqueKw.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  if (!escapedKw) return <span>{text}</span>;

  const regex = new RegExp(`(${escapedKw})`, 'gi');
  const parts = text.split(regex);

  return (
    <span>
      {parts.map((part, i) => {
        const isMatch = uniqueKw.some(k => k.toLowerCase() === part.toLowerCase());
        if (isMatch) {
          return <mark key={i} className="search-highlight">{part}</mark>;
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

/**
 * スコアに応じた関連度情報（クラス名、ラベル、カラー）を判定する
 */
function getRelevanceInfo(score) {
  if (score >= 0.85) {
    return {
      cardClass: 'rel-very-high',
      badgeClass: 'badge-rel-very-high',
      label: '極めて高い',
      color: '#10b981',
      pct: Math.min(100, Math.round(score * 100)),
    };
  } else if (score >= 0.78) {
    return {
      cardClass: 'rel-high',
      badgeClass: 'badge-rel-high',
      label: '高い関連性',
      color: '#38bdf8',
      pct: Math.min(100, Math.round(score * 100)),
    };
  } else if (score >= 0.70) {
    return {
      cardClass: 'rel-medium',
      badgeClass: 'badge-rel-medium',
      label: '中程度',
      color: '#f59e0b',
      pct: Math.min(100, Math.round(score * 100)),
    };
  } else {
    return {
      cardClass: 'rel-low',
      badgeClass: 'badge-rel-low',
      label: '低 / 参考',
      color: '#64748b',
      pct: Math.min(100, Math.round(score * 100)),
    };
  }
}

export function ResultList({ results, searchMode, query }) {
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [copied, setCopied] = useState(false);

  const toggleSelect = (idKey) => {
    const next = new Set(selectedIds);
    if (next.has(idKey)) {
      next.delete(idKey);
    } else {
      next.add(idKey);
    }
    setSelectedIds(next);
  };

  const handleSelectAll = () => {
    if (selectedIds.size === results.length) {
      setSelectedIds(new Set());
    } else {
      const all = new Set(results.map((r, i) => `${r.document_id}_${r.chunk_id ?? i}`));
      setSelectedIds(all);
    }
  };

  const handleCopySelected = () => {
    const selectedItems = results.filter((r, i) =>
      selectedIds.has(`${r.document_id}_${r.chunk_id ?? i}`)
    );
    const textToCopy = selectedItems
      .map((item) => `[${item.title}] (${item.path})\n${item.hit_text || item.preview || ''}\n`)
      .join('\n---\n\n');

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!results || results.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
        <ListFilter size={32} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
        <p>検索結果はここに表示されます</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="results-header">
        <div className="card-title" style={{ marginBottom: 0 }}>
          <ListFilter size={18} color="#6366f1" />
          <span>検索結果 (Top {results.length})</span>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontWeight: 'normal', marginLeft: '8px' }}>
            ({selectedIds.size} 件選択中)
          </span>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary" onClick={handleSelectAll} style={{ padding: '6px 12px', fontSize: '12px' }}>
            {selectedIds.size === results.length ? <CheckSquare size={14} /> : <Square size={14} />}
            <span>全選択/解除</span>
          </button>
          {selectedIds.size > 0 && (
            <button className="btn btn-primary" onClick={handleCopySelected} style={{ padding: '6px 12px', fontSize: '12px' }}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              <span>{copied ? 'コピー完了' : '選択をコピー'}</span>
            </button>
          )}
        </div>
      </div>

      <div className="results-list">
        {results.map((item, index) => {
          const itemKey = `${item.document_id}_${item.chunk_id ?? index}`;
          const isSelected = selectedIds.has(itemKey);
          const ctx = item.context;
          const rel = getRelevanceInfo(item.score);

          return (
            <div key={itemKey} className={`result-card ${rel.cardClass}`}>
              <div className="result-top-row">
                <div className="result-title-group">
                  <div
                    onClick={() => toggleSelect(itemKey)}
                    style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  >
                    {isSelected ? (
                      <CheckSquare size={18} color="#6366f1" />
                    ) : (
                      <Square size={18} color="#64748b" />
                    )}
                  </div>
                  <span className="result-rank">#{index + 1}</span>
                  <span className="result-title">
                    <HighlightedText text={item.title} query={query} />
                  </span>
                  {item.chunk_index !== undefined && item.chunk_index !== null && (
                    <span className="badge" style={{ background: '#1e293b', color: '#94a3b8' }}>
                      Chunk #{item.chunk_index + 1}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div className={`badge ${rel.badgeClass}`} style={{ fontWeight: 700, fontSize: '12px' }}>
                    <span>{rel.label}</span>
                    <span style={{ marginLeft: '6px', fontFamily: 'JetBrains Mono' }}>
                      {item.score.toFixed(3)}
                    </span>
                    <div className="sim-bar-bg">
                      <div
                        className="sim-bar-fill"
                        style={{
                          width: `${rel.pct}%`,
                          backgroundColor: rel.color,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="result-path">{item.path}</div>

              {/* Chunkモードの場合：前後文脈ハイライト & 反応文表示 */}
              {searchMode === 'chunk' && (
                <div className="context-box">
                  {/* 最も反応した一文の強調表示 */}
                  {item.salient_sentence && (
                    <div className="salient-sentence-box">
                      <div className="salient-tag">
                        <span>⚡ クエリに最も反応した一文:</span>
                      </div>
                      <div>
                        " <HighlightedText text={item.salient_sentence} query={query} /> "
                      </div>
                    </div>
                  )}

                  {ctx?.prev && (
                    <div className="context-prev">
                      ... <HighlightedText text={ctx.prev.text.slice(-120)} query={query} />
                    </div>
                  )}
                  {ctx?.prev && <div className="context-divider" />}

                  <div className="context-hit">
                    <div style={{ fontSize: '11px', color: '#818cf8', fontWeight: 600, marginBottom: '4px' }}>
                      🎯 該当チャンク (Hit Chunk #{ (item.chunk_index ?? 0) + 1 })
                    </div>
                    <HighlightedText text={item.hit_text || ctx?.current?.text} query={query} />
                  </div>

                  {ctx?.next && <div className="context-divider" />}
                  {ctx?.next && (
                    <div className="context-next">
                      <HighlightedText text={ctx.next.text.slice(0, 120)} query={query} /> ...
                    </div>
                  )}
                </div>
              )}

              {/* Documentモードの場合：Preview & 反応文 */}
              {searchMode === 'document' && item.preview && (
                <div>
                  {item.salient_sentence && (
                    <div className="salient-sentence-box" style={{ marginBottom: '8px' }}>
                      <div className="salient-tag">
                        <span>⚡ クエリに最も反応した一文:</span>
                      </div>
                      <div>
                        " <HighlightedText text={item.salient_sentence} query={query} /> "
                      </div>
                    </div>
                  )}
                  <div className="preview-box">
                    <HighlightedText text={item.preview} query={query} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
