/**
 * 検索結果一覧コンポーネント
 * 仕様:
 * - Top 20 検索結果のカード表示（順位、タイトル、コサイン類似度、ファイルパス）。
 * - 🏷️ 抽出キーワード（Hybrid Query）のバッジ表示とクエリ文字列コピー機能。
 * - 🤖 AI投入用コンテキスト（RAG Context Viewer: XMLタグ形式 / Markdown引用形式）のプレビューとワンクリックコピー機能。
 * - 選択用チェックボックス（人間による選別コピー機能）。
 * - Chunk検索時: ヒット文章および前後文脈（前/ヒット/後）のハイライト表示。
 * - 反応文（Salient Sentence Extraction）の自動ハイライト表示。
 */

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
} from 'lucide-react';

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
        const isMatch = uniqueKw.some((k) => k.toLowerCase() === part.toLowerCase());
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
function getRelevanceInfo(rawScore) {
  const score = typeof rawScore === 'number' && !isNaN(rawScore) ? rawScore : 0.0;
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

export function ResultList({ results, searchMode, query, responseData, onOpenGlossary }) {
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [copied, setCopied] = useState(false);
  const [kwCopied, setKwCopied] = useState(false);
  const [ragCopied, setRagCopied] = useState(false);
  const [showRagViewer, setShowRagViewer] = useState(false);
  const [ragFormat, setRagFormat] = useState('xml'); // 'xml' or 'markdown'

  const extractedKeywords = responseData?.extracted_keywords || [];
  const keywordQuery = responseData?.keyword_query || '';
  const ragXml = responseData?.rag_context_xml || '';
  const ragMd = responseData?.rag_context_markdown || '';
  const detectedTerms = responseData?.detected_terms || [];

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

  const handleCopyKwQuery = () => {
    if (!keywordQuery) return;
    navigator.clipboard.writeText(keywordQuery);
    setKwCopied(true);
    setTimeout(() => setKwCopied(false), 2000);
  };

  const handleCopyRagContext = () => {
    const text = ragFormat === 'xml' ? ragXml : ragMd;
    if (!text) return;
    navigator.clipboard.writeText(text);
    setRagCopied(true);
    setTimeout(() => setRagCopied(false), 2000);
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
      {/* 💡 検出された専門用語・類似語（Glossary）ボックス */}
      {detectedTerms.length > 0 && (
        <div className="glossary-detected-box">
          <div className="glossary-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sparkles size={16} color="#38bdf8" />
              <span className="glossary-title">💡 検出された専門用語・同義語 (Excel辞書連携):</span>
            </div>
            {onOpenGlossary && (
              <button
                className="btn btn-secondary btn-xs"
                onClick={onOpenGlossary}
                style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                title="辞書エディタを開いて用語を追加・編集"
              >
                <BookOpen size={12} color="#38bdf8" />
                <span>辞書を編集</span>
              </button>
            )}
          </div>
          <div className="glossary-cards-grid">
            {detectedTerms.map((termItem, i) => (
              <div key={i} className="glossary-term-card">
                <div className="glossary-term-name">{termItem.term}</div>
                {termItem.synonyms && termItem.synonyms.length > 0 && (
                  <div className="glossary-term-synonyms">
                    <span className="glossary-synonym-label">同義語:</span>
                    {termItem.synonyms.map((syn, sIdx) => (
                      <span key={sIdx} className="glossary-synonym-badge">{syn}</span>
                    ))}
                  </div>
                )}
                {termItem.description && (
                  <div className="glossary-term-desc">{termItem.description}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 🏷️ 抽出キーワード (Hybrid Query) バッジ表示エリア */}
      {extractedKeywords.length > 0 && (
        <div className="keyword-extracted-box">
          <div className="keyword-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Tag size={15} color="#818cf8" />
              <span className="keyword-title">抽出キーワード (Hybrid Query):</span>
            </div>
            <button
              className="btn btn-secondary btn-xs"
              onClick={handleCopyKwQuery}
              title="キーワード検索エンジン用の OR クエリ文字列をコピー"
            >
              {kwCopied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
              <span>{kwCopied ? 'クエリをコピーしました' : 'OR クエリをコピー'}</span>
            </button>
          </div>
          <div className="keyword-badge-list">
            {extractedKeywords.map((kw, i) => (
              <span key={i} className="keyword-badge">
                #{kw}
              </span>
            ))}
            <span className="keyword-query-preview">
              (クエリ: <code>{keywordQuery}</code>)
            </span>
          </div>
        </div>
      )}

      {/* 🤖 AI投入用コンテキスト（RAG Context Viewer）トグル & ツールバー */}
      <div className="rag-action-bar">
        <button
          className={`btn ${showRagViewer ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setShowRagViewer(!showRagViewer)}
          style={{ padding: '7px 14px', fontSize: '13px' }}
        >
          <Bot size={16} />
          <span>🤖 AI投入用コンテキスト (RAG Output)</span>
          {showRagViewer ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

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

      {/* 🤖 AI投入用コンテキスト プレビューパネル（展開時） */}
      {showRagViewer && (
        <div className="rag-viewer-panel">
          <div className="rag-viewer-header">
            <div className="rag-tabs">
              <button
                className={`rag-tab ${ragFormat === 'xml' ? 'active' : ''}`}
                onClick={() => setRagFormat('xml')}
              >
                <Code size={14} />
                <span>XMLタグ形式 (Claude / OpenAI標準)</span>
              </button>
              <button
                className={`rag-tab ${ragFormat === 'markdown' ? 'active' : ''}`}
                onClick={() => setRagFormat('markdown')}
              >
                <FileCode size={14} />
                <span>Markdown引用形式</span>
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

      {/* 検索結果一覧ヘッダー */}
      <div className="results-header" style={{ marginTop: '16px' }}>
        <div className="card-title" style={{ marginBottom: 0 }}>
          <ListFilter size={18} color="#6366f1" />
          <span>検索結果 (Top {results.length})</span>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontWeight: 'normal', marginLeft: '8px' }}>
            ({selectedIds.size} 件選択中)
          </span>
        </div>
      </div>

      {/* 検索結果カード一覧 */}
      <div className="results-list">
        {results.map((item, index) => {
          const idKey = `${item.document_id}_${item.chunk_id ?? index}`;
          const isSelected = selectedIds.has(idKey);
          const rel = getRelevanceInfo(item.score);

          return (
            <div
              key={idKey}
              className={`result-card ${rel.cardClass} ${isSelected ? 'selected' : ''}`}
              onClick={() => toggleSelect(idKey)}
            >
              {/* カード上部 */}
              <div className="result-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    style={{ cursor: 'pointer' }}
                  />
                  <span className="result-rank">#{index + 1}</span>
                  <span className="result-title">{item.title}</span>
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

              {/* パス */}
              <div className="result-path">{item.path}</div>

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
