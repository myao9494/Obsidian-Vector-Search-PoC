/**
 * AIコンテキスト用HTMLドキュメント生成ページコンポーネント (AiContextExportPage)
 * 仕様:
 * - 質問やキーワードを入力し、ハイブリッド検索（Vector × Keyword API）で関連候補ノート群を抽出。
 * - 抽出されたノート一覧から人間がチェックボックスで選択。
 * - 共通プロンプト（AIへの指示）を設定し、画像・図面（Base64）やMarkdown元データを含む自己完結型HTMLを生成。
 * - 生成されたHTMLのリアルタイムプレビュー、ダウンロード、クリップボードコピーを提供。
 * - 会社等のチャット型AIにワンショットで前提情報をインプットする用途に最適化。
 */

import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Search,
  Download,
  Copy,
  Check,
  FileCode,
  FileText,
  Layers,
  CheckSquare,
  Square,
  RefreshCw,
  Eye,
  ExternalLink,
  HelpCircle,
  Folder,
  Sliders,
  Zap,
  Info,
} from 'lucide-react';
import { searchHybrid, exportAiHtml } from '../api/client';
import { getSavedHybridSettings } from '../utils/hybridSettings';

const PROMPT_PRESETS = [

  {
    label: '❓ 質問に対する根拠付きの回答',
    prompt: `以下の参考ドキュメントの内容のみに基づいて、上記の質問に対して過不足なく正確に回答してください。ドキュメントに記載のない推測は含めず、根拠となるノート名やセクションを明記してください。`,
  },
  {
    label: '🛠️ 資料の修正・推敲',
    prompt: `以下の参考ドキュメントを精査し、記載内容の誤り・論理矛盾・表現の不備・不足している情報を洗い出し、具体的な修正案および改善後の文章を提示してください。`,
  },
  {
    label: '💡 総合要約 & 決定事項とアクション抽出',
    prompt: `以下の参考ドキュメントをすべて熟読した上で、全体の内容を論理的に要約し、重要な決定事項（Decisions）と今後のネクストアクション（Action Items / TODO）を箇条書きで明確に整理して回答してください。`,
  },
  {
    label: '📝 課題・リスクの網羅的レビュー',
    prompt: `以下の参考ドキュメントを精査し、プロジェクトやシステムにおける潜在的な課題・リスク・未決定事項を抽出し、その影響度と推奨対策案を整理して提示してください。`,
  },
  {
    label: '✏️ カスタム指示（自由入力）',
    prompt: ``,
  },
];


// スニペット・根拠文の整形（200文字制限 + '...'）
function truncateSnippet(item, maxLength = 200) {
  const raw = item.snippet || item.salient_sentence || item.hit_text || item.preview || '';
  if (!raw) return '';

  // タグを除いたプレーンテキスト長をチェック
  const plainText = raw.replace(/<[^>]+>/g, '').trim();
  if (!plainText) return '';

  if (plainText.length <= maxLength) {
    return raw;
  }

  return plainText.slice(0, maxLength) + '...';
}

export function AiContextExportPage({

  vaultPath,
  modelStatus,
  onOpenGlossary,
}) {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [selectedPaths, setSelectedPaths] = useState(new Set());

  // エクスポート設定
  const [docTitle, setDocTitle] = useState('AI_Context_Document');
  const [selectedPromptPresetIndex, setSelectedPromptPresetIndex] = useState(0);
  const [promptText, setPromptText] = useState(PROMPT_PRESETS[0].prompt);
  const [includeRawMarkdown, setIncludeRawMarkdown] = useState(true);
  const [includeImages, setIncludeImages] = useState(true);

  // 生成結果
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedHtmlData, setGeneratedHtmlData] = useState(null);
  const [copiedHtml, setCopiedHtml] = useState(false);
  const [previewTab, setPreviewTab] = useState('preview'); // 'preview' | 'code'

  // 検索実行
  const handleSearchCandidates = async (overrideQuery = null) => {
    const q = overrideQuery !== null ? overrideQuery : query;
    if (!q || !q.trim()) {
      alert('質問や探したいキーワードを入力してください');
      return;
    }
    if (!vaultPath) {
      alert('Vaultフォルダが選択されていません');
      return;
    }
    if (!modelStatus?.loaded) {
      alert('モデルがロードされていません。「ベクトル検索」タブでモデルをロードしてください。');
      return;
    }

    setIsSearching(true);
    try {
      // 「ハイブリッド検索」タブで設定された最新の検索設定（重み、融合方式、検索単位、API URL、ORクエリ等）を適用
      const settings = getSavedHybridSettings();

      const res = await searchHybrid(
        vaultPath,
        q.trim(),
        settings.keywordApiUrl,
        settings.searchMode,
        settings.topK,
        settings.vWeight,
        settings.kWeight,
        settings.fusionMethod,
        60,
        settings.useOrQuery ? null : q.trim()
      );

      const items = res.hybrid_results || [];
      setCandidates(items);




      // デフォルトの選択は「何も選択しない」
      setSelectedPaths(new Set());

      // タイトル自動設定
      const safeQ = q.trim().replace(/[\\/*?:"<>| ]+/g, '_').slice(0, 30);
      setDocTitle(`AI_Context_${safeQ}`);
    } catch (err) {
      alert(`候補ドキュメントの検索に失敗しました: ${err.message}`);
    } finally {
      setIsSearching(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      // 日本語IMEの変換確定（未確定文字列のEnter確定）の場合は検索を実行しない
      if (e.nativeEvent.isComposing || e.isComposing || e.keyCode === 229) {
        return;
      }
      handleSearchCandidates();
    }
  };

  // ドラッグ選択管理
  const [isDragging, setIsDragging] = useState(false);
  const isDraggingRef = React.useRef(false);
  const dragModeRef = React.useRef(true); // true: 選択 (ON), false: 解除 (OFF)

  // グローバルマウスアップ監視
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (isDraggingRef.current) {
        isDraggingRef.current = false;
        setIsDragging(false);
      }
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, []);

  // チェックボックスでのマウスダウン（ドラッグ開始）
  const handleCheckboxMouseDown = (e, path) => {
    if (e.button !== 0) return; // 左クリックのみ
    e.preventDefault(); // テキスト選択やデフォルトドラッグを防止

    const isDeselect = e.shiftKey;
    const targetMode = !isDeselect; // Shift押下時は解除(false)、通常時は選択(true)
    dragModeRef.current = targetMode;
    isDraggingRef.current = true;
    setIsDragging(true);

    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (targetMode) {
        next.add(path);
      } else {
        next.delete(path);
      }
      return next;
    });
  };

  // 行 / チェックボックス上をマウスが通過した時（ドラッグ中）
  const handleRowMouseEnter = (e, path) => {
    if (!isDraggingRef.current) return;

    // Shiftキーのリアルタイム状態も判定
    const targetMode = e.shiftKey ? false : dragModeRef.current;

    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (targetMode) {
        next.add(path);
      } else {
        next.delete(path);
      }
      return next;
    });
  };

  // 通常クリックでのトグル（行クリック用）
  const toggleSelect = (path) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelectedPaths(new Set(candidates.map((c) => c.path)));
  };


  const deselectAll = () => {
    setSelectedPaths(new Set());
  };

  // プリセット変更
  const handlePresetChange = (idx) => {
    setSelectedPromptPresetIndex(idx);
    if (idx < PROMPT_PRESETS.length - 1) {
      setPromptText(PROMPT_PRESETS[idx].prompt);
    }
  };

  // HTML生成実行
  const handleGenerateHtml = async () => {
    const paths = Array.from(selectedPaths);
    if (paths.length === 0) {
      alert('エクスポートするドキュメントを1件以上選択してください');
      return;
    }

    setIsGenerating(true);
    try {
      const fullPrompt = query.trim()
        ? `【ユーザーの質問 / テーマ】\n${query.trim()}\n\n【指示】\n${promptText}`
        : promptText;

      const res = await exportAiHtml(
        vaultPath,
        paths,
        fullPrompt,
        docTitle || 'AI_Context_Document',
        includeRawMarkdown,
        includeImages
      );

      setGeneratedHtmlData(res);
    } catch (err) {
      alert(`HTML生成に失敗しました: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // ファイルダウンロード
  const handleDownload = () => {
    if (!generatedHtmlData?.html_content) return;

    const blob = new Blob([generatedHtmlData.html_content], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = generatedHtmlData.file_name || `${docTitle}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copyHtmlCode = () => {
    if (!generatedHtmlData?.html_content) return;
    navigator.clipboard.writeText(generatedHtmlData.html_content);
    setCopiedHtml(true);
    setTimeout(() => setCopiedHtml(false), 2000);
  };

  const openFileViaHub = (fullPath) => {
    const hubBase = 'http://127.0.0.1:8001';
    const targetUrl = `${hubBase}/api/fullpath?path=${encodeURIComponent(fullPath)}`;
    window.open(targetUrl, '_blank');
  };

  return (
    <div>
      {/* イントロダクションバナー */}
      <div className="panel" style={{ marginBottom: '16px', padding: '14px 20px', background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15))', borderColor: 'rgba(168, 85, 247, 0.4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Sparkles size={22} style={{ color: 'var(--accent-purple)', flexShrink: 0 }} />
          <div>
            <strong style={{ fontSize: '14px', color: '#f8fafc' }}>
              🤖 ChatAI インプット用 HTMLドキュメントビルダー
            </strong>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '2px' }}>
              エージェント機能のない社内チャットAIに、関連ノート群＋図面・画像（Base64内包）＋マークダウン元データを1つのHTMLファイルとしてワンショット投入可能にします。
            </div>
          </div>
        </div>
      </div>

      {/* ステップ1: 質問・キーワード検索 & 候補抽出 */}
      <div className="panel" style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <h2 className="panel-title" style={{ margin: 0 }}>
            <Search size={18} />
            ステップ 1: 質問・キーワードで関連ノートを抽出
          </h2>
          {(() => {
            const currentSettings = getSavedHybridSettings();
            return (
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', background: 'rgba(255, 255, 255, 0.04)', padding: '3px 9px', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
                ⚙️ <strong>ハイブリッド設定連動中:</strong> 🔮 ベクトル {currentSettings.vectorRatio}% : 🏷️ キーワード {100 - currentSettings.vectorRatio}% | 融合: {currentSettings.fusionMethod.toUpperCase()} | 単位: {currentSettings.searchMode === 'chunk' ? 'チャンク' : 'ドキュメント'}
              </div>
            );
          })()}
        </div>


        <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
          <input
            type="text"
            className="input-field search-input"
            style={{ width: '100%', fontSize: '14.5px', padding: '9px 14px' }}
            placeholder="AIに回答させたい質問やテーマを入力（例: 次期システムの決定事項、PJ-Xの仕様と課題）"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSearching}
          />


          <button
            className="btn btn-primary"
            style={{ padding: '0 20px', fontSize: '14px', minWidth: '160px' }}
            onClick={() => handleSearchCandidates()}
            disabled={isSearching}
          >
            {isSearching ? (
              <>
                <RefreshCw size={15} className="spin" />
                検索中...
              </>
            ) : (
              <>
                <Sparkles size={15} />
                候補ノートを抽出
              </>
            )}
          </button>
        </div>
      </div>

      {/* ステップ2: 候補ドキュメントの選択 (チェックリストテーブル) */}
      {candidates.length > 0 && (
        <div className="panel" style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <h2 className="panel-title" style={{ margin: 0 }}>
                <CheckSquare size={18} />
                ステップ 2: AIにインプットするノートを選択
              </h2>
              <span className="badge badge-both" style={{ fontSize: '12px' }}>
                {selectedPaths.size} / {candidates.length} 件 選択中
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-dim)', background: 'rgba(255, 255, 255, 0.05)', padding: '2px 8px', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
                💡 <strong>ドラッグ</strong>で連続選択 / <strong>Shift + ドラッグ</strong>で連続解除
              </span>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-secondary" style={{ fontSize: '12px', padding: '4px 10px' }} onClick={selectAll}>
                全選択
              </button>
              <button className="btn btn-secondary" style={{ fontSize: '12px', padding: '4px 10px' }} onClick={deselectAll}>
                全解除
              </button>
            </div>
          </div>

          <div
            className="table-responsive-container"
            style={{
              userSelect: isDragging ? 'none' : 'auto',
              cursor: isDragging ? (dragModeRef.current ? 'crosshair' : 'not-allowed') : 'auto',
            }}
          >
            <table className="ai-export-table">
              <thead>
                <tr>
                  <th style={{ width: '44px', textAlign: 'center' }}>選択</th>
                  <th style={{ width: '60px' }}>順位</th>
                  <th style={{ width: '130px' }}>マッチ種別</th>
                  <th>ノートタイトル</th>
                  <th>パス</th>
                  <th>スニペット / 根拠文</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((item, idx) => {
                  const isChecked = selectedPaths.has(item.path);
                  return (
                    <tr
                      key={idx}
                      className={isChecked ? 'row-selected' : ''}
                      onMouseEnter={(e) => handleRowMouseEnter(e, item.path)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td
                        style={{
                          textAlign: 'center',
                          cursor: 'pointer',
                          backgroundColor: isChecked ? 'rgba(168, 85, 247, 0.12)' : 'transparent',
                          userSelect: 'none',
                        }}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          handleCheckboxMouseDown(e, item.path);
                        }}
                        title="ドラッグで連続選択 / Shift+ドラッグで連続解除"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // マウスダウンで処理
                          style={{ cursor: 'pointer', width: '16px', height: '16px', accentColor: 'var(--accent-purple)' }}
                          onMouseDown={(e) => {
                            e.stopPropagation();
                            handleCheckboxMouseDown(e, item.path);
                          }}
                        />
                      </td>
                      <td
                        style={{ fontFamily: 'JetBrains Mono', fontWeight: 600, color: 'var(--accent-cyan)' }}
                        onClick={() => toggleSelect(item.path)}
                      >
                        #{idx + 1}
                      </td>
                      <td onClick={() => toggleSelect(item.path)}>
                        {item.match_type === 'both' && (
                          <span className="badge badge-both" style={{ fontSize: '11px' }}>🌟 両方一致</span>
                        )}
                        {item.match_type === 'vector_only' && (
                          <span className="badge badge-vector" style={{ fontSize: '11px' }}>🔮 意味一致</span>
                        )}
                        {item.match_type === 'keyword_only' && (
                          <span className="badge badge-keyword" style={{ fontSize: '11px' }}>🏷️ キーワード</span>
                        )}
                      </td>
                      <td>
                        <button
                          className="table-title-link"
                          onClick={(e) => {
                            e.stopPropagation();
                            openFileViaHub(item.full_path);
                          }}
                          title="8001 Open Hubで開く"
                        >
                          <strong>{item.title}</strong>
                          <ExternalLink size={12} style={{ marginLeft: '4px', verticalAlign: 'middle' }} />
                        </button>
                      </td>
                      <td
                        style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: 'var(--text-dim)' }}
                        onClick={() => toggleSelect(item.path)}
                      >
                        {item.path}
                      </td>
                      <td
                        style={{
                          fontSize: '11.5px',
                          color: 'var(--text-dim)',
                          maxWidth: '360px',
                          lineHeight: '1.45',
                          wordBreak: 'break-word',
                        }}
                        onClick={() => toggleSelect(item.path)}
                      >
                        {(() => {
                          const formatted = truncateSnippet(item, 200);
                          return formatted.includes('<mark>') ? (
                            <span dangerouslySetInnerHTML={{ __html: formatted }} />
                          ) : (
                            <span>{formatted}</span>
                          );
                        })()}
                      </td>

                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

        </div>
      )}

      {/* ステップ3: AI共通プロンプト・設定 & 生成 */}
      {candidates.length > 0 && (
        <div className="panel" style={{ marginBottom: '16px' }}>
          <h2 className="panel-title">
            <FileCode size={18} />
            ステップ 3: AIへの指示（共通プロンプト） & エクスポート設定
          </h2>

          {/* プリセット選択ボタン */}
          <div style={{ marginTop: '12px' }}>
            <label className="field-label" style={{ fontSize: '12px' }}>
              プロンプトテンプレート
            </label>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
              {PROMPT_PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={`btn btn-sm ${selectedPromptPresetIndex === idx ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handlePresetChange(idx)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* プロンプトテキストエリア */}
          <div style={{ marginTop: '12px' }}>
            <label className="field-label" style={{ fontSize: '12px' }}>
              AIへの指示文（自由に編集可能）
            </label>
            <textarea
              className="input-field"
              style={{ width: '100%', height: '80px', fontSize: '13.5px', padding: '8px 12px', marginTop: '4px', fontFamily: 'inherit' }}
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder="AIへの具体的な指示や出力フォーマットの希望を記述"
            />
          </div>

          {/* 出力オプション & 生成ボタン */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginTop: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '18px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-dim)' }}>HTMLタイトル:</label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: '220px', fontSize: '12px', padding: '4px 8px' }}
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                />
              </div>

              <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={includeImages}
                  onChange={(e) => setIncludeImages(e.target.checked)}
                />
                <span>🖼️ 画像・図面をBase64埋め込み</span>
              </label>

              <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={includeRawMarkdown}
                  onChange={(e) => setIncludeRawMarkdown(e.target.checked)}
                />
                <span>📝 マークダウン元データを含める</span>
              </label>
            </div>

            <button
              className="btn btn-primary"
              style={{ padding: '8px 24px', fontSize: '14.5px', background: 'linear-gradient(135deg, #6366f1, #a855f7)' }}
              onClick={handleGenerateHtml}
              disabled={isGenerating || selectedPaths.size === 0}
            >
              {isGenerating ? (
                <>
                  <RefreshCw size={16} className="spin" />
                  HTML生成中...
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  🚀 AI用HTMLファイルを生成する ({selectedPaths.size}件)
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ステップ4: 生成結果プレビュー & ダウンロード */}
      {generatedHtmlData && (
        <div className="panel" style={{ marginTop: '20px', borderColor: 'rgba(16, 185, 129, 0.5)' }}>
          {/* 結果ヘッダー */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', borderBottom: '1px solid var(--border-color)', paddingBottom: '14px', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Check size={20} style={{ color: '#10b981' }} />
              <div>
                <strong style={{ fontSize: '15px', color: '#f8fafc' }}>
                  HTMLファイルの生成が完了しました！
                </strong>
                <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '2px' }}>
                  ドキュメント: {generatedHtmlData.total_documents}件 | 埋め込み画像: {generatedHtmlData.total_images_embedded}件 | サイズ: {(generatedHtmlData.size_bytes / 1024).toFixed(1)} KB
                </div>
              </div>
            </div>

            {/* アクションボタン群 */}
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                className="btn btn-primary"
                style={{ padding: '8px 18px', fontSize: '14px', background: '#10b981', borderColor: '#059669' }}
                onClick={handleDownload}
              >
                <Download size={16} />
                📥 HTMLファイルをダウンロード (.html)
              </button>
              <button
                className="btn btn-secondary"
                style={{ fontSize: '13px', padding: '6px 14px' }}
                onClick={copyHtmlCode}
              >
                {copiedHtml ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                {copiedHtml ? 'コードをコピー完了！' : 'HTMLコードをコピー'}
              </button>
            </div>
          </div>

          {/* ビュー切り替えタブ */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <button
              className={`btn btn-sm ${previewTab === 'preview' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setPreviewTab('preview')}
            >
              <Eye size={14} />
              プレビュー表示
            </button>
            <button
              className={`btn btn-sm ${previewTab === 'code' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setPreviewTab('code')}
            >
              <FileCode size={14} />
              HTMLソース
            </button>
          </div>

          {/* プレビューコンテナ */}
          {previewTab === 'preview' ? (
            <div className="html-preview-frame-container">
              <iframe
                title="AI Context HTML Preview"
                srcDoc={generatedHtmlData.html_content}
                className="html-preview-iframe"
              />
            </div>
          ) : (
            <pre className="rag-code-block" style={{ maxHeight: '500px' }}>
              {generatedHtmlData.html_content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
