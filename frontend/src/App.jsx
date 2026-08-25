/**
 * メインアプリケーションコンポーネント
 * 仕様:
 * - ヘッダー（ブランドタイトル・PoCバッジ・ポート情報）
 * - Vault & Model 設定（2カラム）
 *   - Vaultパスおよびモデルパス（標準/軽量）、選択状態を localStorage に自動記憶
 * - Index 管理パネル（進捗バー・サマリー・DB統計・対象拡張子指定）
 * - ベクトル検索パネル（Document/Chunk切り替え・速度計測）
 * - 検索結果一覧（Top 20・文脈ハイライト・抽出キーワード・AI投入用RAGコンテキスト）
 */

import React, { useState, useEffect } from 'react';
import { Compass } from 'lucide-react';
import { VaultSelector } from './components/VaultSelector';
import { ModelSelector } from './components/ModelSelector';
import { IndexPanel } from './components/IndexPanel';
import { SearchPanel } from './components/SearchPanel';
import { ResultList } from './components/ResultList';
import { getModelStatus, getVaultStats, loadModel } from './api/client';

const STORAGE_KEYS = {
  VAULT_PATH: 'poc_vault_path',
  MODEL_STANDARD: 'poc_model_standard_path',
  MODEL_LIGHT: 'poc_model_light_path',
  SELECTED_MODEL_TYPE: 'poc_selected_model_type',
};

export function App() {
  // LocalStorage からの初期値復元
  const [vaultPath, setVaultPath] = useState(() => {
    return localStorage.getItem(STORAGE_KEYS.VAULT_PATH) || '/Users/mine/000_work/obsidian-dagnetz/01_data';
  });

  const [standardPath, setStandardPath] = useState(() => {
    return localStorage.getItem(STORAGE_KEYS.MODEL_STANDARD) || '/Users/mine/000_work/test/PoC_lag/models/ruri-v3-310m';
  });

  const [lightPath, setLightPath] = useState(() => {
    return localStorage.getItem(STORAGE_KEYS.MODEL_LIGHT) || '/Users/mine/000_work/test/PoC_lag/models/ruri-v3-30m';
  });

  const [selectedModelType, setSelectedModelType] = useState(() => {
    return localStorage.getItem(STORAGE_KEYS.SELECTED_MODEL_TYPE) || 'light';
  });

  const [modelStatus, setModelStatus] = useState(null);
  const [vaultStats, setVaultStats] = useState(null);

  const [searchMode, setSearchMode] = useState('chunk');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchMetrics, setSearchMetrics] = useState(null);
  const [searchResponseData, setSearchResponseData] = useState(null);

  // LocalStorage 自動保存
  useEffect(() => {
    if (vaultPath) localStorage.setItem(STORAGE_KEYS.VAULT_PATH, vaultPath);
  }, [vaultPath]);

  useEffect(() => {
    if (standardPath) localStorage.setItem(STORAGE_KEYS.MODEL_STANDARD, standardPath);
  }, [standardPath]);

  useEffect(() => {
    if (lightPath) localStorage.setItem(STORAGE_KEYS.MODEL_LIGHT, lightPath);
  }, [lightPath]);

  useEffect(() => {
    if (selectedModelType) localStorage.setItem(STORAGE_KEYS.SELECTED_MODEL_TYPE, selectedModelType);
  }, [selectedModelType]);

  // 初期ロード
  useEffect(() => {
    const activePath = selectedModelType === 'standard' ? standardPath : lightPath;
    if (activePath) {
      loadModel(activePath, false)
        .then((st) => setModelStatus(st))
        .catch(() => {
          getModelStatus().then((st) => setModelStatus(st)).catch(() => {});
        });
    }

    if (vaultPath) {
      getVaultStats(vaultPath)
        .then((st) => setVaultStats(st))
        .catch(() => {});
    }
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
              Local Offline Vector Search Engine (ruri-v3-310m / ruri-v3-30m + FAISS)
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
          selectedModelType={selectedModelType}
          setSelectedModelType={setSelectedModelType}
          standardPath={standardPath}
          setStandardPath={setStandardPath}
          lightPath={lightPath}
          setLightPath={setLightPath}
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
