/**
 * メインアプリケーションコンポーネント
 * 仕様:
 * - ヘッダー（ブランドタイトル・PoCバッジ・ポート情報）
 * - Vault & Model 設定（2カラム）
 * - Index 管理パネル（進捗バー・サマリー・DB統計）
 * - ベクトル検索パネル（Document/Chunk切り替え・速度計測）
 * - 検索結果一覧（Top 20・文脈ハイライト・選択機能）
 */

import React, { useState, useEffect } from 'react';
import { Compass, Sparkles } from 'lucide-react';
import { VaultSelector } from './components/VaultSelector';
import { ModelSelector } from './components/ModelSelector';
import { IndexPanel } from './components/IndexPanel';
import { SearchPanel } from './components/SearchPanel';
import { ResultList } from './components/ResultList';
import { getModelStatus, getVaultStats } from './api/client';

export function App() {
  const [vaultPath, setVaultPath] = useState('');
  const [modelPath, setModelPath] = useState('/Users/mine/000_work/test/PoC_lag/models/ruri-v3-310m');
  const [modelStatus, setModelStatus] = useState(null);
  const [vaultStats, setVaultStats] = useState(null);

  const [searchMode, setSearchMode] = useState('chunk');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchMetrics, setSearchMetrics] = useState(null);
  const [searchResponseData, setSearchResponseData] = useState(null);

  // 初期ステータス取得
  useEffect(() => {
    getModelStatus()
      .then((st) => setModelStatus(st))
      .catch(() => {});
  }, []);

  const handleVaultChanged = (path) => {
    if (path) {
      getVaultStats(path)
        .then((st) => setVaultStats(st))
        .catch(() => setVaultStats(null));
    }
  };

  return (
    <div className="container">
      {/* アプリヘッダー */}
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">
            <Compass size={22} />
          </div>
          <div>
            <h1 className="brand-title">Obsidian Vector Search PoC</h1>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
              Local Offline Vector Search Engine (ruri-v3-310m + FAISS)
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="badge badge-poc">PWA Standalone</span>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'JetBrains Mono' }}>
            Port: :60000
          </span>
        </div>
      </header>

      {/* Vault & Model 設定 (2カラム) */}
      <div className="grid-2">
        <VaultSelector
          vaultPath={vaultPath}
          setVaultPath={setVaultPath}
          onVaultChanged={handleVaultChanged}
        />
        <ModelSelector
          modelPath={modelPath}
          setModelPath={setModelPath}
          modelStatus={modelStatus}
          setModelStatus={setModelStatus}
        />
      </div>

      {/* Index パネル */}
      <IndexPanel
        vaultPath={vaultPath}
        modelStatus={modelStatus}
        vaultStats={vaultStats}
        setVaultStats={setVaultStats}
      />

      {/* 検索パネル */}
      <SearchPanel
        vaultPath={vaultPath}
        modelStatus={modelStatus}
        searchMode={searchMode}
        setSearchMode={setSearchMode}
        setSearchResults={setSearchResults}
        setSearchMetrics={setSearchMetrics}
        setSearchResponseData={setSearchResponseData}
        searchMetrics={searchMetrics}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
      />

      {/* 検索結果リスト */}
      <ResultList
        results={searchResults}
        searchMode={searchMode}
        query={searchQuery}
        responseData={searchResponseData}
      />
    </div>
  );
}

export default App;
