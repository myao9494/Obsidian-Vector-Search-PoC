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
import { Compass, Zap, Sparkles, FileCode } from 'lucide-react';
import { VaultSelector } from './components/VaultSelector';
import { ModelSelector } from './components/ModelSelector';
import { IndexPanel } from './components/IndexPanel';
import { IncrementalBenchmarkPanel } from './components/IncrementalBenchmarkPanel';
import { SearchPanel } from './components/SearchPanel';
import { ResultList } from './components/ResultList';
import { GlossaryModal } from './components/GlossaryModal';
import { HybridSearchPage } from './components/HybridSearchPage';
import { AiContextExportPage } from './components/AiContextExportPage';
import { getModelStatus, getVaultStats, loadModel, getDictionaryStatus } from './api/client';


const STORAGE_KEYS = {
  VAULT_PATH: 'poc_vault_path',
  MODEL_STANDARD: 'poc_model_standard_path',
  MODEL_LIGHT: 'poc_model_light_path',
  SELECTED_MODEL_TYPE: 'poc_selected_model_type',
  ACTIVE_NAV_TAB: 'poc_active_nav_tab',
};

export function App() {
  const [activeNavTab, setActiveNavTab] = useState(() => {
    return localStorage.getItem(STORAGE_KEYS.ACTIVE_NAV_TAB) || 'hybrid';
  });

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
  const [dictionaryStatus, setDictionaryStatus] = useState(null);
  const [isGlossaryModalOpen, setIsGlossaryModalOpen] = useState(false);

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

  // 初期ロード & ウィンドウフォーカス時の自動リフレッシュ（外部でExcel等を編集した場合の自動検知）
  useEffect(() => {
    const activePath = selectedModelType === 'standard' ? standardPath : lightPath;
    if (activePath) {
      loadModel(activePath, false)
        .then((st) => setModelStatus(st))
        .catch(() => {
          getModelStatus().then((st) => setModelStatus(st)).catch(() => {});
        });
    }

    const refreshVaultAndDict = () => {
      if (vaultPath) {
        getVaultStats(vaultPath)
          .then((st) => setVaultStats(st))
          .catch(() => {});
        getDictionaryStatus(vaultPath)
          .then((st) => setDictionaryStatus(st))
          .catch(() => {});
      }
    };

    refreshVaultAndDict();

    window.addEventListener('focus', refreshVaultAndDict);
    return () => {
      window.removeEventListener('focus', refreshVaultAndDict);
    };
  }, [vaultPath]);

  useEffect(() => {
    if (activeNavTab) localStorage.setItem(STORAGE_KEYS.ACTIVE_NAV_TAB, activeNavTab);
  }, [activeNavTab]);


  const handleVaultChanged = (path) => {
    if (path) {
      getVaultStats(path)
        .then((st) => setVaultStats(st))
        .catch(() => setVaultStats(null));
      getDictionaryStatus(path)
        .then((st) => setDictionaryStatus(st))
        .catch(() => setDictionaryStatus(null));
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

      {/* トップレベル ナビゲーションタブ */}
      <div className="main-nav-tabs">
        <button
          className={`main-nav-tab ${activeNavTab === 'hybrid' ? 'active' : ''}`}
          onClick={() => setActiveNavTab('hybrid')}
        >
          <Sparkles size={17} />
          <span>🔀 ハイブリッド検索 (Hybrid Search - PoC)</span>
        </button>
        <button
          className={`main-nav-tab ${activeNavTab === 'ai-export' ? 'active' : ''}`}
          onClick={() => setActiveNavTab('ai-export')}
        >
          <FileCode size={17} />
          <span>🤖 AIコンテキスト生成 (Chat AI Export)</span>
          <span className="badge badge-new">New</span>
        </button>
        <button
          className={`main-nav-tab ${activeNavTab === 'vector' ? 'active' : ''}`}
          onClick={() => setActiveNavTab('vector')}
        >
          <Zap size={17} />
          <span>⚡ ベクトル検索 (Vector Search 単体)</span>
        </button>
      </div>

      {/* 共通: Vault & Model 設定 (2カラム) */}
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
          vaultStats={vaultStats}
          setVaultStats={setVaultStats}
          vaultPath={vaultPath}
        />
      </div>

      {/* ページコンテンツ切り替え */}
      {activeNavTab === 'hybrid' && (
        /* ハイブリッド検索専用ページ */
        <HybridSearchPage
          vaultPath={vaultPath}
          modelStatus={modelStatus}
          onOpenGlossary={() => setIsGlossaryModalOpen(true)}
        />
      )}

      {activeNavTab === 'ai-export' && (
        /* AIコンテキスト用HTMLエクスポートページ */
        <AiContextExportPage
          vaultPath={vaultPath}
          modelStatus={modelStatus}
          onOpenGlossary={() => setIsGlossaryModalOpen(true)}
        />
      )}

      {activeNavTab === 'vector' && (
        /* ベクトル検索単体ページ */
        <>
          {/* Index パネル */}
          <IndexPanel
            vaultPath={vaultPath}
            modelStatus={modelStatus}
            vaultStats={vaultStats}
            setVaultStats={setVaultStats}
            dictionaryStatus={dictionaryStatus}
            onOpenGlossary={() => setIsGlossaryModalOpen(true)}
            selectedModelType={selectedModelType}
          />

          {/* 差分更新ライブ検証パネル */}
          <IncrementalBenchmarkPanel
            vaultPath={vaultPath}
            isModelLoaded={modelStatus?.loaded}
            onUpdateCompleted={() => {
              if (vaultPath) {
                getVaultStats(vaultPath)
                  .then((st) => setVaultStats(st))
                  .catch(() => {});
              }
            }}
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
            onOpenGlossary={() => setIsGlossaryModalOpen(true)}
          />
        </>
      )}


      {/* 専門用語辞書モーダルエディタ */}
      <GlossaryModal
        isOpen={isGlossaryModalOpen}
        onClose={() => setIsGlossaryModalOpen(false)}
        vaultPath={vaultPath}
        onDictionarySaved={(newStatus) => {
          setDictionaryStatus(newStatus);
        }}
      />
    </div>
  );
}

export default App;


