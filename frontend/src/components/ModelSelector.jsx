/**
 * Embedding モデル選択・ロードコンポーネント
 * 仕様:
 * - 2択ラジオ選択:
 *   1. 👑 標準モデル (ruri-v3-310m) - 768d 高精度
 *   2. ⚡ 超軽量モデル (ruri-v3-30m) - 256d 超高速 (Windows CPU推奨)
 * - 各モデルのローカルパス入力ボックス ＋ 📁 参照ボタン
 * - 各モデルごとの個別インデックス状態（インデックス済件数・サイズ / 未作成）の視覚的バッジ表示
 * - 選択切り替え時の自動ロード & ステータス自動更新
 */

import React, { useState } from 'react';
import { Cpu, FolderSearch, CheckCircle2, AlertCircle, Zap, Crown, RefreshCw, Database } from 'lucide-react';
import { selectFolderDialog, loadModel, getVaultStats } from '../api/client';

export function ModelSelector({
  selectedModelType,
  setSelectedModelType,
  standardPath,
  setStandardPath,
  lightPath,
  setLightPath,
  modelStatus,
  setModelStatus,
  vaultStats,
  setVaultStats,
  vaultPath,
}) {
  const [loading, setLoading] = useState(false);

  // 各モデルのインデックス状況の取得ヘルパー
  const getModelStatsBadge = (type) => {
    if (!vaultStats?.models) return null;
    const path = type === 'standard' ? standardPath : lightPath;
    const modelKey = path ? path.replace(/\\/g, '/').split('/').filter(Boolean).pop() : (type === 'standard' ? 'ruri-v3-310m' : 'ruri-v3-30m');
    const stat = vaultStats.models[modelKey];

    if (stat && stat.document_count > 0) {
      return (
        <span
          className="badge"
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            color: '#34d399',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            fontSize: '10px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 8px',
          }}
          title={`インデックス保存場所: ${stat.db_path}`}
        >
          <Database size={10} />
          <span>インデックス済: {stat.document_count}件 ({stat.db_size_mb}MB)</span>
        </span>
      );
    }

    return (
      <span
        className="badge"
        style={{
          backgroundColor: 'rgba(148, 163, 184, 0.1)',
          color: 'var(--text-muted)',
          border: '1px solid rgba(148, 163, 184, 0.2)',
          fontSize: '10px',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 8px',
        }}
      >
        <span>未インデックス</span>
      </span>
    );
  };

  // モデルの明示的ロード
  const handleLoad = async (typeToLoad, pathToLoad) => {
    const targetType = typeToLoad || selectedModelType;
    const targetPath = pathToLoad || (targetType === 'standard' ? standardPath : lightPath);

    if (!targetPath) {
      alert('モデルのローカルパスを入力してください');
      return;
    }

    try {
      setLoading(true);
      const res = await loadModel(targetPath, false);
      setModelStatus(res);
      if (vaultPath && setVaultStats) {
        const stats = await getVaultStats(vaultPath);
        setVaultStats(stats);
      }
    } catch (err) {
      alert(`モデルロードエラー: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ラジオ選択切り替え時のハンドラー
  const handleTypeChange = async (type) => {
    setSelectedModelType(type);
    const targetPath = type === 'standard' ? standardPath : lightPath;
    if (targetPath) {
      await handleLoad(type, targetPath);
    }
  };

  // フォルダ参照
  const handleBrowse = async (type) => {
    try {
      const selected = await selectFolderDialog('ローカルモデルのフォルダを選択してください');
      if (selected) {
        if (type === 'standard') {
          setStandardPath(selected);
        } else {
          setLightPath(selected);
        }
        if (selectedModelType === type) {
          await handleLoad(type, selected);
        }
      }
    } catch (err) {
      alert(`フォルダ選択エラー: ${err.message}`);
    }
  };

  return (
    <div className="card">
      <div className="card-title">
        <Cpu size={18} color="#10b981" />
        <span>Embedding モデル設定</span>
        {modelStatus?.loaded && (
          <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
            <CheckCircle2 size={12} />
            <span>ロード済 ({modelStatus.dim}d)</span>
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '12px' }}>
        {/* モデルタイプ 2択ラジオ */}
        <div className="model-radio-group">
          {/* 1. 標準モデル */}
          <div
            className={`model-radio-card ${selectedModelType === 'standard' ? 'active' : ''}`}
            onClick={() => handleTypeChange('standard')}
          >
            <div className="model-radio-header">
              <input
                type="radio"
                name="modelType"
                value="standard"
                checked={selectedModelType === 'standard'}
                onChange={() => handleTypeChange('standard')}
                style={{ cursor: 'pointer', accentColor: 'var(--primary)' }}
              />
              <Crown size={16} color="#fbbf24" />
              <div className="model-radio-title">👑 標準モデル (ruri-v3-310m)</div>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
                {getModelStatsBadge('standard')}
                <span className="badge badge-poc" style={{ fontSize: '10px' }}>
                  768d / 高精度
                </span>
              </div>
            </div>
            <div className="model-radio-desc">
              最高峰の文脈把握力。Mac GPU (MPS) または高性能CPU環境に最適。モデル固有の独立インデックスで管理されます。
            </div>

            {/* パス入力 */}
            <div
              className="model-path-row"
              onClick={(e) => e.stopPropagation()}
              style={{ marginTop: '8px' }}
            >
              <input
                type="text"
                className="form-input"
                placeholder="標準モデルのローカルパス"
                value={standardPath}
                onChange={(e) => setStandardPath(e.target.value)}
                style={{ fontSize: '12px', padding: '6px 10px' }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleBrowse('standard')}
                style={{ padding: '6px 10px' }}
                title="フォルダを参照"
              >
                <FolderSearch size={14} />
              </button>
            </div>
          </div>

          {/* 2. 超軽量モデル */}
          <div
            className={`model-radio-card ${selectedModelType === 'light' ? 'active' : ''}`}
            onClick={() => handleTypeChange('light')}
          >
            <div className="model-radio-header">
              <input
                type="radio"
                name="modelType"
                value="light"
                checked={selectedModelType === 'light'}
                onChange={() => handleTypeChange('light')}
                style={{ cursor: 'pointer', accentColor: 'var(--primary)' }}
              />
              <Zap size={16} color="#38bdf8" />
              <div className="model-radio-title">⚡ 超軽量モデル (ruri-v3-30m)</div>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
                {getModelStatsBadge('light')}
                <span className="badge badge-poc" style={{ fontSize: '10px', borderColor: '#38bdf8', color: '#38bdf8' }}>
                  256d / 超高速 (~60ms)
                </span>
              </div>
            </div>
            <div className="model-radio-desc">
              わずか 30M パラメータ（極小サイズ）。Windows 一般CPU環境でサクサク動作。モデル固有の独立インデックスで管理されます。
            </div>

            {/* パス入力 */}
            <div
              className="model-path-row"
              onClick={(e) => e.stopPropagation()}
              style={{ marginTop: '8px' }}
            >
              <input
                type="text"
                className="form-input"
                placeholder="超軽量モデルのローカルパス"
                value={lightPath}
                onChange={(e) => setLightPath(e.target.value)}
                style={{ fontSize: '12px', padding: '6px 10px' }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleBrowse('light')}
                style={{ padding: '6px 10px' }}
                title="フォルダを参照"
              >
                <FolderSearch size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* 再ロードボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleLoad()}
            disabled={loading}
            style={{ padding: '6px 14px', fontSize: '12px' }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>{loading ? 'モデルをロード中...' : '選択モデルを適用・再ロード'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

