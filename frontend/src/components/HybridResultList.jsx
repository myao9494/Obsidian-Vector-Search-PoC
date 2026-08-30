/**
 * ハイブリッド検索結果リストコンポーネント (HybridResultList)
 * 仕様:
 * - 3つのビューモード:
 *   1. 🔀 ハイブリッド統合ランキング (メイン)
 *   2. ⚖️ 3ペイン並列比較ビュー (Vector Top10 vs Hybrid Top10 vs Keyword Top10)
 *   3. 🤖 AI (LLM) 投入用 RAG コンテキスト (XML / Markdown コピー)
 * - マッチ種別バッジ（🌟 ベクトル+キーワード両方一致 / 🔮 意味類似のみ / 🏷️ キーワードのみ）
 * - 8001 Open Hub 連携、OSネイティブ保存場所表示 (Finder/Explorer)、パスクリップボードコピー
 * - キーワードハイライト (<mark>) & 反応文 (Salient Sentence) & 文脈アコーディオン
 */

import React, { useState } from 'react';
import {
  ExternalLink,
  Folder,
  Copy,
  Check,
  Zap,
  Sparkles,
  Search,
  Code,
  FileText,
  HelpCircle,
  Sliders,
  Layers,
  ChevronDown,
  ChevronUp,
  Columns,
  List,
} from 'lucide-react';
import { openFileLocation } from '../api/client';

export function HybridResultList({
  results = [],
  vectorResults = [],
  keywordResults = [],
  responseData = null,
  query = '',
  onOpenGlossary = null,
}) {
  const [activeTab, setActiveTab] = useState('hybrid'); // 'hybrid' | 'compare' | 'rag'
  const [ragFormat, setRagFormat] = useState('xml'); // 'xml' | 'markdown'
  const [copiedRag, setCopiedRag] = useState(false);
  const [copiedQuery, setCopiedQuery] = useState(false);
  const [copiedPathMap, setCopiedPathMap] = useState({});
  const [expandedContexts, setExpandedContexts] = useState({});

  if (!responseData && results.length === 0) {
    return null;
  }

  const openFileViaHub = (fullPath) => {
    const hubBase = 'http://127.0.0.1:8001';
    const targetUrl = `${hubBase}/api/fullpath?path=${encodeURIComponent(fullPath)}`;
    window.open(targetUrl, '_blank');
  };

  const openFolderViaHub = (fullPath) => {
    const hubBase = 'http://127.0.0.1:8001';
    const parentPath = fullPath.substring(0, fullPath.lastIndexOf('/')) || fullPath;
    const targetUrl = `${hubBase}/api/fullpath?path=${encodeURIComponent(parentPath)}`;
    window.open(targetUrl, '_blank');
  };

  const handleOpenLocation = async (fullPath) => {
    try {
      await openFileLocation(fullPath);
    } catch (err) {
      alert(`保存場所の表示に失敗しました: ${err.message}`);
    }
  };

  const copyPath = (path, id) => {
    navigator.clipboard.writeText(path);
    setCopiedPathMap((prev) => ({ ...prev, [id]: true }));
    setTimeout(() => {
      setCopiedPathMap((prev) => ({ ...prev, [id]: false }));
    }, 2000);
  };

  const copyRagContext = () => {
    const text =
      ragFormat === 'xml'
        ? responseData?.rag_context_xml
        : responseData?.rag_context_markdown;
    if (text) {
      navigator.clipboard.writeText(text);
      setCopiedRag(true);
      setTimeout(() => setCopiedRag(false), 2000);
    }
  };

  const toggleContext = (idx) => {
    setExpandedContexts((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const renderHighlight = (text, keywords = []) => {
    if (!text) return null;
    if (text.includes('<mark>')) {
      return <span dangerouslySetInnerHTML={{ __html: text }} />;
    }
    if (!keywords || keywords.length === 0) return text;

    const escaped = keywords
      .filter((kw) => kw && kw.length >= 2)
      .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('|');
    if (!escaped) return text;

    const regex = new RegExp(`(${escaped})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      keywords.some((kw) => kw.toLowerCase() === part.toLowerCase()) ? (
        <mark key={i} className="search-highlight">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const getMatchBadge = (matchType) => {
    switch (matchType) {
      case 'both':
        return (
          <span className="badge badge-both" title="ベクトル検索とキーワード検索の双方が高スコアで一致">
            <Sparkles size={13} style={{ marginRight: '4px' }} />
            🌟 両方一致 (Dense × Sparse)
          </span>
        );
      case 'vector_only':
        return (
          <span className="badge badge-vector" title="意味・概念の類似性でベクトル検索が検出">
            <Zap size={13} style={{ marginRight: '4px' }} />
            🔮 意味一致 (Dense)
          </span>
        );
      case 'keyword_only':
        return (
          <span className="badge badge-keyword" title="キーワード検索APIのテキスト完全一致・FTS5で検出">
            <Search size={13} style={{ marginRight: '4px' }} />
            🏷️ キーワード一致 (Sparse)
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="panel" style={{ marginTop: '20px' }}>
      {/* 上部ヘッダー & ビュー切り替えタブ */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          borderBottom: '1px solid var(--border-color)',
          paddingBottom: '14px',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h2 className="panel-title" style={{ margin: 0 }}>
            🔀 ハイブリッド検索結果
          </h2>
          <span className="badge badge-pill">{results.length} 件</span>
          {responseData?.metrics && (
            <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'JetBrains Mono' }}>
              ⚡ ベクトル {responseData.metrics.vector_time_ms}ms ＋ 🏷️ キーワード {responseData.metrics.keyword_time_ms}ms ＝ 計 {responseData.metrics.total_time_ms}ms
            </span>
          )}
        </div>

        {/* タブボタングループ */}
        <div className="tab-group">
          <button
            className={`tab-btn ${activeTab === 'hybrid' ? 'active' : ''}`}
            onClick={() => setActiveTab('hybrid')}
          >
            <List size={15} />
            統合ランキング ({results.length})
          </button>
          <button
            className={`tab-btn ${activeTab === 'compare' ? 'active' : ''}`}
            onClick={() => setActiveTab('compare')}
          >
            <Columns size={15} />
            ⚖️ 3ペイン並列比較
          </button>
          <button
            className={`tab-btn ${activeTab === 'rag' ? 'active' : ''}`}
            onClick={() => setActiveTab('rag')}
          >
            <Code size={15} />
            🤖 AI (RAG) コンテキスト
          </button>
        </div>
      </div>

      {/* 専門用語辞書検知カード */}
      {responseData?.detected_terms && responseData.detected_terms.length > 0 && (
        <div className="glossary-alert-card" style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <HelpCircle size={17} style={{ color: 'var(--accent-orange)' }} />
              <strong>💡 クエリから社内専門用語・類似語を検知しました:</strong>
            </div>
            {onOpenGlossary && (
              <button
                className="btn btn-secondary"
                style={{ fontSize: '11px', padding: '3px 8px' }}
                onClick={onOpenGlossary}
              >
                辞書を編集
              </button>
            )}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
            {responseData.detected_terms.map((t, idx) => (
              <div key={idx} className="glossary-term-badge">
                <span className="term-main">{t.term}</span>
                {t.synonyms && t.synonyms.length > 0 && (
                  <span className="term-syns">({t.synonyms.join(', ')})</span>
                )}
                {t.description && <span className="term-desc">: {t.description}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 抽出キーワードバッジ */}
      {responseData?.extracted_keywords && responseData.extracted_keywords.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>🏷️ 抽出キーワード:</span>
          {responseData.extracted_keywords.map((kw, i) => (
            <span key={i} className="badge badge-keyword-pill">
              {kw}
            </span>
          ))}
          {responseData.keyword_query && (
            <span style={{ fontSize: '12px', color: 'var(--text-dim)', marginLeft: '8px' }}>
              (API送信クエリ: <code>{responseData.keyword_query}</code>)
            </span>
          )}
        </div>
      )}

      {/* ビュー1: 🔀 ハイブリッド統合ランキング */}
      {activeTab === 'hybrid' && (
        <div className="result-cards-container">
          {results.length === 0 ? (
            <div className="empty-state">該当する検索結果は見つかりませんでした。</div>
          ) : (
            results.map((item, idx) => {
              const itemKey = item.full_path || idx;
              const isExpanded = expandedContexts[idx];

              return (
                <div
                  key={idx}
                  className={`result-card ${
                    item.match_type === 'both'
                      ? 'result-card-both'
                      : item.match_type === 'vector_only'
                      ? 'result-card-vector'
                      : 'result-card-keyword'
                  }`}
                >
                  {/* カードヘッダー */}
                  <div className="result-card-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
                      <span className="result-rank-num">#{idx + 1}</span>
                      <button
                        className="result-title-link"
                        onClick={() => openFileViaHub(item.full_path)}
                        title="8001 Open Hub経由でファイルを開く"
                      >
                        {item.title}
                        <ExternalLink size={14} style={{ marginLeft: '4px', verticalAlign: 'middle' }} />
                      </button>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      {getMatchBadge(item.match_type)}
                      <span className="badge badge-hybrid-score" title="融合スコア">
                        Hybrid: {item.hybrid_score}
                      </span>
                    </div>
                  </div>

                  {/* パス & アクションバー */}
                  <div className="result-path-bar">
                    <span className="result-path-text" title={item.full_path}>
                      {item.path || item.full_path}
                    </span>
                    <div className="result-path-actions">
                      <button
                        className="btn-icon-subtle"
                        onClick={() => handleOpenLocation(item.full_path)}
                        title="macOS Finder / Windows Explorer で保存場所を表示"
                      >
                        <Folder size={14} />
                        保存場所
                      </button>
                      <button
                        className="btn-icon-subtle"
                        onClick={() => copyPath(item.full_path, itemKey)}
                        title="フルパスをコピー"
                      >
                        {copiedPathMap[itemKey] ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                        {copiedPathMap[itemKey] ? 'コピー済' : 'パスコピー'}
                      </button>
                    </div>
                  </div>

                  {/* スコア内訳バッジ */}
                  <div className="score-breakdown-bar">
                    {item.vector_rank !== null && (
                      <span className="score-breakdown-tag vector-tag">
                        🔮 ベクトル #{item.vector_rank} (Score: {item.vector_score})
                      </span>
                    )}
                    {item.keyword_rank !== null && (
                      <span className="score-breakdown-tag keyword-tag">
                        🏷️ キーワード #{item.keyword_rank} (Score: {item.keyword_score})
                      </span>
                    )}
                  </div>

                  {/* 反応文 (Salient Sentence) */}
                  {item.salient_sentence && (
                    <div className="salient-sentence-box">
                      <Zap size={14} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: '2px' }} />
                      <div>
                        <strong style={{ fontSize: '11px', color: 'var(--accent-cyan)' }}>🎯 核心反応文:</strong>
                        <div style={{ fontSize: '13px', color: 'var(--text-main)', marginTop: '2px' }}>
                          {renderHighlight(item.salient_sentence, responseData?.extracted_keywords)}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* スニペット / 本文プレビュー */}
                  <div className="result-snippet-box">
                    {item.snippet ? (
                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'block', marginBottom: '3px' }}>
                          🏷️ キーワード一致スニペット:
                        </span>
                        {renderHighlight(item.snippet, responseData?.extracted_keywords)}
                      </div>
                    ) : item.hit_text ? (
                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'block', marginBottom: '3px' }}>
                          🔮 ベクトル一致テキスト:
                        </span>
                        {renderHighlight(item.hit_text, responseData?.extracted_keywords)}
                      </div>
                    ) : (
                      item.preview && renderHighlight(item.preview, responseData?.extracted_keywords)
                    )}
                  </div>

                  {/* チャンク文脈アコーディオン */}
                  {item.context && (item.context.prev || item.context.next) && (
                    <div style={{ marginTop: '8px' }}>
                      <button
                        className="btn-context-toggle"
                        onClick={() => toggleContext(idx)}
                      >
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? '前後の文脈を閉じる' : '前後の文脈（前後チャンク）を表示'}
                      </button>

                      {isExpanded && (
                        <div className="context-expanded-box">
                          {item.context.prev && (
                            <div className="context-sub-chunk">
                              <span className="context-label">◀ 直前のチャンク</span>
                              <pre className="context-text">{item.context.prev.text}</pre>
                            </div>
                          )}
                          <div className="context-sub-chunk current">
                            <span className="context-label">▶ ヒットしたチャンク</span>
                            <pre className="context-text">{item.hit_text}</pre>
                          </div>
                          {item.context.next && (
                            <div className="context-sub-chunk">
                              <span className="context-label">▶ 直後のチャンク</span>
                              <pre className="context-text">{item.context.next.text}</pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ビュー2: ⚖️ 3ペイン並列比較ビュー */}
      {activeTab === 'compare' && (
        <div className="comparison-grid-3">
          {/* カラム1: ベクトル検索 Top 10 */}
          <div className="comparison-col">
            <div className="comparison-col-header vector-header">
              <Zap size={16} />
              <h3>🔮 ベクトル検索 Top 10</h3>
              <span className="badge badge-vector-pill">{vectorResults.length}</span>
            </div>
            <div className="comparison-items-list">
              {vectorResults.slice(0, 10).map((v, i) => (
                <div key={i} className="comparison-mini-card">
                  <div className="mini-card-top">
                    <span className="mini-rank">#{i + 1}</span>
                    <span className="mini-title" title={v.title}>{v.title}</span>
                    <span className="mini-score">{v.score}</span>
                  </div>
                  <div className="mini-snippet">
                    {(v.salient_sentence || v.hit_text || v.preview || '').slice(0, 90)}...
                  </div>
                </div>
              ))}
              {vectorResults.length === 0 && (
                <div className="mini-empty">ベクトル結果なし</div>
              )}
            </div>
          </div>

          {/* カラム2: ハイブリッド融合 Top 10 */}
          <div className="comparison-col">
            <div className="comparison-col-header hybrid-header">
              <Sparkles size={16} />
              <h3>🔀 ハイブリッド融合 Top 10</h3>
              <span className="badge badge-both-pill">{results.length}</span>
            </div>
            <div className="comparison-items-list">
              {results.slice(0, 10).map((h, i) => (
                <div
                  key={i}
                  className={`comparison-mini-card ${
                    h.match_type === 'both' ? 'highlight-both' : ''
                  }`}
                >
                  <div className="mini-card-top">
                    <span className="mini-rank">#{i + 1}</span>
                    <span className="mini-title" title={h.title}>{h.title}</span>
                    <span className="mini-score">{h.hybrid_score}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '4px', margin: '4px 0' }}>
                    {getMatchBadge(h.match_type)}
                  </div>
                  <div className="mini-snippet">
                    {(h.snippet || h.salient_sentence || h.hit_text || '').slice(0, 90)}...
                  </div>
                </div>
              ))}
              {results.length === 0 && (
                <div className="mini-empty">ハイブリッド結果なし</div>
              )}
            </div>
          </div>

          {/* カラム3: キーワード検索 Top 10 */}
          <div className="comparison-col">
            <div className="comparison-col-header keyword-header">
              <Search size={16} />
              <h3>🏷️ キーワードAPI Top 10</h3>
              <span className="badge badge-keyword-pill">{keywordResults.length}</span>
            </div>
            <div className="comparison-items-list">
              {keywordResults.slice(0, 10).map((k, i) => (
                <div key={i} className="comparison-mini-card">
                  <div className="mini-card-top">
                    <span className="mini-rank">#{i + 1}</span>
                    <span className="mini-title" title={k.file_name}>{k.file_name}</span>
                    <span className="mini-score">{k.utility_score || k.click_count || '-'}</span>
                  </div>
                  <div
                    className="mini-snippet"
                    dangerouslySetInnerHTML={{ __html: (k.snippet || '').slice(0, 120) }}
                  />
                </div>
              ))}
              {keywordResults.length === 0 && (
                <div className="mini-empty">
                  {responseData?.keyword_api_status?.connected === false
                    ? '⚠️ キーワードAPI未接続'
                    : 'キーワード結果なし'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ビュー3: 🤖 AI (RAG) コンテキスト */}
      {activeTab === 'rag' && (
        <div className="rag-context-container">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className={`btn btn-sm ${ragFormat === 'xml' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setRagFormat('xml')}
              >
                XML形式 (Claude / OpenAI / RAG)
              </button>
              <button
                className={`btn btn-sm ${ragFormat === 'markdown' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setRagFormat('markdown')}
              >
                Markdown引用形式
              </button>
            </div>

            <button className="btn btn-primary" onClick={copyRagContext}>
              {copiedRag ? <Check size={14} /> : <Copy size={14} />}
              {copiedRag ? 'コピー完了！' : 'プロンプト用コンテキストをコピー'}
            </button>
          </div>

          <pre className="rag-code-block">
            {ragFormat === 'xml'
              ? responseData?.rag_context_xml
              : responseData?.rag_context_markdown}
          </pre>
        </div>
      )}
    </div>
  );
}
