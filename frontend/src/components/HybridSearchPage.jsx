/**
 * ハイブリッド検索メインページコンポーネント (HybridSearchPage)
 * 仕様:
 * - 運用中キーワード検索リポジトリ (Local-fulltext-search: Port 8079) のAPIと連携。
 * - API接続先設定 & 死活監視ステータス表示（🟢 接続中 / 🔴 未接続）。
 * - 検索クエリ入力、融合方式選択 (RRF / Weighted Score)、重み比率スライダー。
 * - 抽出キーワード自動ORクエリ連携。
 * - 検索結果の表示 (HybridResultList)。
 */

import React, { useState, useEffect } from 'react';
import {
  Search,
  Sliders,
  Sparkles,
  Zap,
  RefreshCw,
  Server,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Play,
  RotateCcw,
} from 'lucide-react';
import { searchHybrid, getKeywordApiStatus } from '../api/client';
import { HybridResultList } from './HybridResultList';
import { getSavedHybridSettings, saveHybridSettings } from '../utils/hybridSettings';

export function HybridSearchPage({
  vaultPath,
  modelStatus,
  onOpenGlossary,
}) {
  const initialSettings = getSavedHybridSettings();

  const [keywordApiUrl, setKeywordApiUrl] = useState(initialSettings.keywordApiUrl);
  const [apiStatus, setApiStatus] = useState(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);

  // 検索パラメータ
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState(initialSettings.searchMode); // 'chunk' | 'document'
  const [fusionMethod, setFusionMethod] = useState(initialSettings.fusionMethod); // 'rrf' | 'weighted'
  const [vectorRatio, setVectorRatio] = useState(initialSettings.vectorRatio); // 0〜100 (50 = 50:50)
  const [topK, setTopK] = useState(initialSettings.topK);
  const [useOrQuery, setUseOrQuery] = useState(initialSettings.useOrQuery);

  // 検索結果
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [vectorResults, setVectorResults] = useState([]);
  const [keywordResults, setKeywordResults] = useState([]);
  const [responseData, setSearchResponseData] = useState(null);
  const [searchError, setSearchError] = useState(null);

  // LocalStorage 自動保存
  useEffect(() => {
    saveHybridSettings({
      keywordApiUrl,
      searchMode,
      fusionMethod,
      vectorRatio,
      topK,
      useOrQuery,
    });
  }, [keywordApiUrl, searchMode, fusionMethod, vectorRatio, topK, useOrQuery]);


  // 初回およびURL変更時のAPIステータス確認
  const checkApiConnection = async (urlToCheck = keywordApiUrl) => {
    setIsCheckingStatus(true);
    try {
      const status = await getKeywordApiStatus(urlToCheck);
      setApiStatus(status);
    } catch (err) {
      setApiStatus({
        connected: false,
        url: urlToCheck,
        message: err.message || '接続エラー',
      });
    } finally {
      setIsCheckingStatus(false);
    }
  };

  useEffect(() => {
    checkApiConnection();
  }, [keywordApiUrl]);

  // 検索実行
  const handleSearch = async (overrideQuery = null) => {
    const q = overrideQuery !== null ? overrideQuery : query;
    if (!q || !q.trim()) {
      alert('検索キーワードまたは質問を入力してください');
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
    setSearchError(null);

    const vWeight = vectorRatio / 100.0;
    const kWeight = (100 - vectorRatio) / 100.0;

    try {
      const res = await searchHybrid(
        vaultPath,
        q.trim(),
        keywordApiUrl,
        searchMode,
        topK,
        vWeight,
        kWeight,
        fusionMethod,
        60,
        useOrQuery ? null : q.trim() // useOrQueryがfalseの場合は入力クエリをそのまま送信
      );

      setSearchResponseData(res);
      setSearchResults(res.hybrid_results || []);
      setVectorResults(res.vector_results || []);
      setKeywordResults(res.keyword_results || []);
      if (res.keyword_api_status) {
        setApiStatus(res.keyword_api_status);
      }
    } catch (err) {
      setSearchError(err.message || '検索処理中にエラーが発生しました');
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
      handleSearch();
    }
  };


  const samplePresets = [
    { label: '自然文質問', q: '議事録の内容や重要な決定事項' },
    { label: '型番・固有名詞', q: 'ModernBERT ruri-v3' },
    { label: '社内用語・同義語', q: 'PJ-X プロジェクト進捗' },
    { label: 'エラー・トラブル', q: 'Memory leak OOM error' },
  ];

  return (
    <div>
      {/* キーワード検索API連携ステータスバー */}
      <div className="panel" style={{ marginBottom: '16px', padding: '12px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Server size={18} style={{ color: 'var(--accent-purple)' }} />
            <div>
              <strong style={{ fontSize: '13px' }}>キーワード検索 API 連携 (Local-fulltext-search)</strong>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                運用中の高速全文検索エンジン（ポート 8079）と協調動作
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="text"
              className="input-field"
              style={{ width: '220px', fontSize: '12px', padding: '4px 8px' }}
              value={keywordApiUrl}
              onChange={(e) => setKeywordApiUrl(e.target.value)}
              placeholder="http://127.0.0.1:8079"
            />
            <button
              className="btn btn-secondary"
              style={{ fontSize: '12px', padding: '5px 10px' }}
              onClick={() => checkApiConnection(keywordApiUrl)}
              disabled={isCheckingStatus}
            >
              <RefreshCw size={13} className={isCheckingStatus ? 'spin' : ''} />
              接続テスト
            </button>

            {apiStatus?.connected ? (
              <span className="badge badge-success" title={apiStatus.message}>
                <CheckCircle2 size={13} />
                🟢 接続中 (Port 8079)
              </span>
            ) : (
              <span className="badge badge-warning" title={apiStatus?.message || '未接続'}>
                <AlertCircle size={13} />
                🔴 未接続 (自動フォールバック)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 検索入力 & ハイブリッドチューニングパネル */}
      <div className="panel">
        <h2 className="panel-title">
          <Sparkles size={18} />
          ハイブリッド検索 (Dense × Sparse Fusion)
        </h2>

        {/* 検索入力バー */}
        <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              className="input-field search-input"
              style={{ width: '100%', fontSize: '15px', padding: '10px 14px' }}
              placeholder="自然言語の質問、またはキーワードを入力（例: 議事録の決定事項、PJ-Xの進捗、ModernBERT）"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isSearching}
            />
          </div>

          <button
            className="btn btn-primary"
            style={{ padding: '0 24px', fontSize: '15px', minWidth: '130px' }}
            onClick={() => handleSearch()}
            disabled={isSearching}
          >
            {isSearching ? (
              <>
                <RefreshCw size={16} className="spin" />
                検索中...
              </>
            ) : (
              <>
                <Search size={16} />
                検索実行
              </>
            )}
          </button>
        </div>

        {/* プリセットボタン */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>💡 クエリ例:</span>
          {samplePresets.map((p, idx) => (
            <button
              key={idx}
              className="preset-btn"
              onClick={() => {
                setQuery(p.q);
                handleSearch(p.q);
              }}
            >
              {p.label}: "{p.q}"
            </button>
          ))}
        </div>

        {/* チューニングパラメータ設定 (アコーディオン風) */}
        <div className="hybrid-tuning-box" style={{ marginTop: '16px' }}>
          <div className="grid-3" style={{ gap: '16px' }}>
            {/* 1. 融合方式 */}
            <div>
              <label className="field-label" style={{ fontSize: '12px' }}>
                <Sliders size={13} style={{ marginRight: '4px' }} />
                融合アルゴリズム (Fusion Method)
              </label>
              <div className="radio-group-modern" style={{ marginTop: '6px' }}>
                <label className={`radio-card ${fusionMethod === 'rrf' ? 'active' : ''}`}>
                  <input
                    type="radio"
                    name="fusion_method"
                    value="rrf"
                    checked={fusionMethod === 'rrf'}
                    onChange={() => setFusionMethod('rrf')}
                  />
                  <div>
                    <strong>RRF (Reciprocal Rank Fusion)</strong>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      順位ベースの頑健な融合 (推奨)
                    </div>
                  </div>
                </label>
                <label className={`radio-card ${fusionMethod === 'weighted' ? 'active' : ''}`}>
                  <input
                    type="radio"
                    name="fusion_method"
                    value="weighted"
                    checked={fusionMethod === 'weighted'}
                    onChange={() => setFusionMethod('weighted')}
                  />
                  <div>
                    <strong>Weighted Score Fusion</strong>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      正規化類似度スコアの重み合算
                    </div>
                  </div>
                </label>
              </div>
            </div>

            {/* 2. 重み比率スライダー */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="field-label" style={{ fontSize: '12px' }}>
                  重み比率 (Vector : Keyword)
                </label>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>
                  🔮 {vectorRatio}% : 🏷️ {100 - vectorRatio}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={vectorRatio}
                onChange={(e) => setVectorRatio(Number(e.target.value))}
                style={{ width: '100%', marginTop: '12px', accentColor: 'var(--accent-cyan)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dim)' }}>
                <span>0% (キーワードのみ)</span>
                <span>50:50 (バランス)</span>
                <span>100% (ベクトルのみ)</span>
              </div>
            </div>

            {/* 3. 検索単位 & キーワードクエリ設定 */}
            <div>
              <label className="field-label" style={{ fontSize: '12px' }}>
                検索単位 & API連携モード
              </label>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  className={`btn btn-sm ${searchMode === 'chunk' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                  onClick={() => setSearchMode('chunk')}
                >
                  チャンク (推奨)
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${searchMode === 'document' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                  onClick={() => setSearchMode('document')}
                >
                  ノート全文
                </button>
              </div>

              <div style={{ marginTop: '10px' }}>
                <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={useOrQuery}
                    onChange={(e) => setUseOrQuery(e.target.checked)}
                  />
                  <span>自然文から抽出したキーワード（OR結合）をAPIに送信</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        {searchError && (
          <div className="alert-box alert-danger" style={{ marginTop: '14px' }}>
            <AlertCircle size={16} />
            <div>{searchError}</div>
          </div>
        )}
      </div>

      {/* 検索結果表示 */}
      <HybridResultList
        results={searchResults}
        vectorResults={vectorResults}
        keywordResults={keywordResults}
        responseData={responseData}
        query={query}
        onOpenGlossary={onOpenGlossary}
      />
    </div>
  );
}
