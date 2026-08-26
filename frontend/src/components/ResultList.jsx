import React, { useState } from 'react';
import {
  ListFilter,
  CheckSquare,
  Square,
  Copy,
  Check,
  Tag,
  Bot,
  Code,
  FileCode,
  ChevronDown,
  ChevronUp,
  Sparkles,
  BookOpen,
  Folder,
  ExternalLink,
  FolderOpen,
  Compass,
} from 'lucide-react';
import { openFileLocation } from '../api/client';

/**
 * 検索結果クリック時に使う 8001 Open Hub のベース URL を返す
 * Local-fulltext-search の外部Openハブ契約に準拠
 */
function getOpenHubBaseUrl() {
  return (
    (typeof window !== 'undefined' && window.__OPEN_HUB_BASE_URL__) ||
    'http://127.0.0.1:8001'
  ).replace(/\/+$/, '');
}

/**
 * フルパスから親フォルダパスを取り出す
 */
function getParentFolderPath(fullPath) {
  if (!fullPath) return '';
  const lastSep = Math.max(fullPath.lastIndexOf('/'), fullPath.lastIndexOf('\\'));
  if (lastSep < 0) return fullPath;
  if (lastSep === 0) return fullPath.slice(0, 1);
  return fullPath.slice(0, lastSep);
}

/**
 * テキスト内の検索クエリキーワードをハイライト表示するヘルパーコンポーネント
 */
function HighlightedText({ text, query, keywords = [] }) {
  if (!text) return null;
  if ((!query || !query.trim()) && (!keywords || keywords.length === 0)) {
    return <span>{text}</span>;
  }

  // クエリと抽出キーワードを結合
  const candidateKeywords = [...(keywords || [])];
  if (query && query.trim().length >= 2) {
    candidateKeywords.push(query.trim());
  }

  if (candidateKeywords.length === 0) return <span>{text}</span>;

  // 重複除去 & 長いキーワードから順にマッチさせる
  const uniqueKw = Array.from(new Set(candidateKeywords))
    .filter((k) => k && k.length >= 2)
    .sort((a, b) => b.length - a.length);

  if (uniqueKw.length === 0) return <span>{text}</span>;

  const escapedKw = uniqueKw.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  if (!escapedKw) return <span>{text}</span>;

  const regex = new RegExp(`(${escapedKw})`, 'gi');
  const parts = text.split(regex);

  return (
    <span>
      {parts.map((part, i) => {
        if (!part) return null;
        const isMatch = uniqueKw.some(
          (k) => k.toLowerCase() === part.toLowerCase()
        );
        return isMatch ? (
          <mark key={i} className="highlight-keyword">
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        );
      })}
    </span>
  );
}

export function ResultList({
  results: propResults,
  searchMode = 'chunk',
  query: propQuery = '',
  responseData,
  searchResponse,
  onOpenGlossary = null,
}) {
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [copiedKw, setCopiedKw] = useState(false);
  const [ragCopied, setRagCopied] = useState(false);
  const [ragFormat, setRagFormat] = useState('xml'); // 'xml' or 'markdown'
  const [showRagViewer, setShowRagViewer] = useState(false);
  const [copiedPathKey, setCopiedPathKey] = useState(null);
  const [openingLocationKey, setOpeningLocationKey] = useState(null);

  const results = propResults || searchResponse?.results || [];
  const query = propQuery || searchResponse?.query || responseData?.query || '';
  const extractedKeywords = responseData?.extracted_keywords || searchResponse?.extracted_keywords || [];
  const keywordQuery = responseData?.keyword_query || searchResponse?.keyword_query || '';
  const ragXml = responseData?.rag_context_xml || searchResponse?.rag_context_xml || '';
  const ragMd = responseData?.rag_context_markdown || searchResponse?.rag_context_markdown || '';
  const detectedTerms = responseData?.detected_terms || searchResponse?.detected_terms || [];
  const openHubBase = getOpenHubBaseUrl();


  const toggleSelect = (idKey) => {
    const next = new Set(selectedIds);
    if (next.has(idKey)) {
      next.delete(idKey);
    } else {
      next.add(idKey);
    }
    setSelectedIds(next);
  };

  const selectAll = () => {
    if (selectedIds.size === results.length) {
      setSelectedIds(new Set());
    } else {
      const all = new Set(
        results.map((r, i) => `${r.document_id}_${r.chunk_id ?? i}`)
      );
      setSelectedIds(all);
    }
  };

  const handleCopyKwQuery = () => {
    if (!keywordQuery) return;
    navigator.clipboard.writeText(keywordQuery);
    setCopiedKw(true);
    setTimeout(() => setCopiedKw(false), 2000);
  };

  const handleCopyRagContext = () => {
    const textToCopy = ragFormat === 'xml' ? ragXml : ragMd;
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setRagCopied(true);
    setTimeout(() => setRagCopied(false), 2000);
  };

  const handleCopyPath = (e, idKey, fullPath) => {
    e.stopPropagation();
    navigator.clipboard.writeText(fullPath);
    setCopiedPathKey(idKey);
    setTimeout(() => setCopiedPathKey(null), 2000);
  };

  const handleOpenLocation = async (e, idKey, fullPath) => {
    e.stopPropagation();
    try {
      setOpeningLocationKey(idKey);
      await openFileLocation(fullPath);
    } catch (err) {
      alert(`保存場所を開けませんでした: ${err.message}`);
    } finally {
      setOpeningLocationKey(null);
    }
  };

  const getRelevanceInfo = (score) => {
    const s = Number(score ?? 0);
    if (s >= 0.70) {
      return { label: 'High', color: '#10b981', badgeClass: 'badge-high', cardClass: 'card-high' };
    }
    if (s >= 0.40) {
      return { label: 'Medium', color: '#f59e0b', badgeClass: 'badge-med', cardClass: 'card-med' };
    }
    return { label: 'Low', color: '#94a3b8', badgeClass: 'badge-low', cardClass: 'card-low' };
  };

  if (results.length === 0) {
    return (
      <div className="results-container">
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <div className="empty-state-title">該当するノートが見つかりませんでした</div>
          <div className="empty-state-desc">
            別のキーワードで試すか、インデックスの更新状況を確認してください。
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="results-container">
      {/* 💡 検出された専門用語・同義語カード */}
      {detectedTerms.length > 0 && (
        <div className="detected-terms-card">
          <div className="detected-terms-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BookOpen size={18} color="#0c8599" />
              <span className="detected-terms-title">
                検出された社内用語・同義語 (Query Enrichment 適用中)
              </span>
            </div>
            {onOpenGlossary && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={onOpenGlossary}
                style={{ fontSize: '11px', padding: '4px 8px' }}
                title="専門用語辞書を開いて編集"
              >
                辞書を編集
              </button>
            )}
          </div>
          <div className="detected-terms-list">
            {detectedTerms.map((t, idx) => (
              <div key={idx} className="detected-term-item">
                <span className="detected-term-badge">{t.term}</span>
                {t.synonyms && t.synonyms.length > 0 && (
                  <span className="detected-term-synonyms">
                    (同義語: {t.synonyms.join(', ')})
                  </span>
                )}
                {t.description && (
                  <span className="detected-term-desc">: {t.description}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 🏷️ 抽出キーワード (Hybrid Query) バナー */}
      {extractedKeywords.length > 0 && (
        <div className="keywords-banner">
          <div className="keywords-banner-left">
            <Tag size={16} color="#06b6d4" />
            <span className="keywords-label">抽出キーワード (OR検索用):</span>
            <div className="keyword-badges">
              {extractedKeywords.map((kw, i) => (
                <span key={i} className="keyword-badge">
                  {kw}
                </span>
              ))}
            </div>
          </div>

          {keywordQuery && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleCopyKwQuery}
              title={`コピー: ${keywordQuery}`}
            >
              {copiedKw ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
              <span>{copiedKw ? 'ORクエリをコピーしました' : 'ORクエリをコピー'}</span>
            </button>
          )}
        </div>
      )}

      {/* 🤖 AI投入用 RAG コンテキストビューア */}
      {ragXml && (
        <div className="rag-context-card">
          <div
            className="rag-context-header"
            onClick={() => setShowRagViewer(!showRagViewer)}
            style={{ cursor: 'pointer' }}
          >
            <div className="rag-header-left">
              <Bot size={18} color="#8b5cf6" />
              <span className="rag-title">🤖 AI（LLM）投入用 RAG コンテキスト</span>
              <span className="rag-badge">Top 5 ドキュメント抽出済</span>
            </div>

            <div className="rag-header-actions" onClick={(e) => e.stopPropagation()}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setShowRagViewer(!showRagViewer)}
                title={showRagViewer ? '折りたたむ' : '展開する'}
              >
                {showRagViewer ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                <span>{showRagViewer ? '閉じる' : 'プレビュー'}</span>
              </button>
            </div>
          </div>

          {showRagViewer && (
            <div className="rag-viewer-body">
              <div className="rag-format-tabs">
                <div className="tab-group">
                  <button
                    className={`btn-tab ${ragFormat === 'xml' ? 'active' : ''}`}
                    onClick={() => setRagFormat('xml')}
                  >
                    <Code size={14} />
                    <span>XML形式 (Claude / ChatGPT)</span>
                  </button>
                  <button
                    className={`btn-tab ${ragFormat === 'markdown' ? 'active' : ''}`}
                    onClick={() => setRagFormat('markdown')}
                  >
                    <FileCode size={14} />
                    <span>Markdown形式</span>
                  </button>
                </div>

                <button className="btn btn-primary btn-sm" onClick={handleCopyRagContext}>
                  {ragCopied ? <Check size={14} /> : <Copy size={14} />}
                  <span>{ragCopied ? 'AIプロンプト用にコピー完了！' : '📋 AIプロンプト用にコピー'}</span>
                </button>
              </div>

              <div className="rag-code-container">
                <pre className="rag-code-content">
                  {ragFormat === 'xml' ? ragXml : ragMd}
                </pre>
              </div>
              <div className="rag-help-text">
                💡 <strong>使い方:</strong> 上記の内容を ChatGPT、Claude、Gemini、またはローカルLLMのプロンプト内にそのまま貼り付けることで、Obsidianの検索結果に基づいた高精度な回答（RAG）を生成できます。
              </div>
            </div>
          )}
        </div>
      )}

      {/* 検索結果一覧ヘッダー */}
      <div className="results-header" style={{ marginTop: '16px' }}>
        <div className="card-title" style={{ marginBottom: 0 }}>
          <ListFilter size={18} color="#6366f1" />
          <span>検索結果 (Top {results.length})</span>
        </div>
      </div>

      <div className="results-list">
        {results.map((item, index) => {
          const idKey = `${item.document_id}_${item.chunk_id ?? index}`;
          const isSelected = selectedIds.has(idKey);
          const rel = getRelevanceInfo(item.score);
          const fullPath = item.full_path || item.path;
          const parentFolder = getParentFolderPath(fullPath);
          const fullPathUrl = `${openHubBase}/api/fullpath?path=${encodeURIComponent(fullPath)}`;
          const folderUrl = `${openHubBase}/?path=${encodeURIComponent(parentFolder)}`;

          return (
            <div
              key={idKey}
              className={`result-card ${rel.cardClass} ${isSelected ? 'selected' : ''}`}
              onClick={() => toggleSelect(idKey)}
            >
              {/* カード上部 */}
              <div className="result-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    style={{ cursor: 'pointer', flexShrink: 0 }}
                  />
                  <span className="result-rank">#{index + 1}</span>
                  {/* タイトルリンク: クリックで 8001 Open Hub 経由で直接ファイルを開く */}
                  <a
                    href={fullPathUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="result-title-link"
                    onClick={(e) => e.stopPropagation()}
                    title={`Open Hubでファイルを開く: ${fullPath}`}
                  >
                    <span className="result-title">{item.title}</span>
                    <ExternalLink size={14} className="title-external-icon" />
                  </a>
                </div>

                <div className="score-container">
                  <div className="score-label">関連度</div>
                  <div className="score-value" style={{ color: rel.color }}>
                    {((item.score ?? 0) * 100).toFixed(1)}%
                  </div>
                  <span className={`badge ${rel.badgeClass}`}>
                    {rel.label} ({Number(item.score ?? 0).toFixed(4)})
                  </span>
                </div>
              </div>

              {/* パス表示 & アクションバー (Local-fulltext-search 仕様準拠) */}
              <div className="result-path-container" onClick={(e) => e.stopPropagation()}>
                <code className="result-path-text" title={fullPath}>
                  {fullPath}
                </code>

                <div className="result-path-actions">
                  {/* パスコピーボタン */}
                  <button
                    type="button"
                    className="btn-path-action"
                    onClick={(e) => handleCopyPath(e, idKey, fullPath)}
                    title="フルパスをクリップボードにコピー"
                  >
                    {copiedPathKey === idKey ? (
                      <>
                        <Check size={13} color="#10b981" />
                        <span style={{ color: '#10b981' }}>コピー完了</span>
                      </>
                    ) : (
                      <>
                        <Copy size={13} />
                        <span>パスをコピー</span>
                      </>
                    )}
                  </button>

                  {/* 保存場所を表示 (Finder / Explorer) */}
                  <button
                    type="button"
                    className="btn-path-action"
                    onClick={(e) => handleOpenLocation(e, idKey, fullPath)}
                    title="OSのFinder/Explorerでファイルの保存場所を表示"
                    disabled={openingLocationKey === idKey}
                  >
                    <Compass size={13} />
                    <span>{openingLocationKey === idKey ? '表示中...' : '保存場所を表示'}</span>
                  </button>

                  {/* フォルダを開く (Open Hub リンク) */}
                  {parentFolder && (
                    <a
                      href={folderUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-path-action link-path-action"
                      title="親フォルダをOpen Hubで開く"
                    >
                      <FolderOpen size={13} />
                      <span>フォルダを開く</span>
                    </a>
                  )}
                </div>
              </div>

              {/* 反応文（Salient Sentence）の強調表示 */}
              {item.salient_sentence && (
                <div className="salient-sentence-box">
                  <span className="salient-label">
                    <Sparkles size={12} color="#818cf8" style={{ marginRight: '4px' }} />
                    反応文（核となる一文）:
                  </span>
                  <p className="salient-text">
                    <HighlightedText
                      text={item.salient_sentence}
                      query={query}
                      keywords={extractedKeywords}
                    />
                  </p>
                </div>
              )}

              {/* Chunk 検索時の前後文脈表示 */}
              {searchMode === 'chunk' && item.context && (
                <div className="chunk-context-box">
                  {item.context.prev && (
                    <div className="context-segment context-prev">
                      <span className="context-tag">前の段落</span>
                      <p>{item.context.prev.text}</p>
                    </div>
                  )}

                  <div className="context-segment context-hit">
                    <span className="context-tag tag-hit">ヒット段落</span>
                    <p>
                      <HighlightedText
                        text={item.hit_text}
                        query={query}
                        keywords={extractedKeywords}
                      />
                    </p>
                  </div>

                  {item.context.next && (
                    <div className="context-segment context-next">
                      <span className="context-tag">次の段落</span>
                      <p>{item.context.next.text}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Document 検索時のプレビュー表示 */}
              {searchMode === 'document' && item.preview && (
                <div className="document-preview-box">
                  <p>
                    <HighlightedText
                      text={item.preview}
                      query={query}
                      keywords={extractedKeywords}
                    />
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
