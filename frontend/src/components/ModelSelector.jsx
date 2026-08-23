/**
 * Embedding モデル選択・ロードコンポーネント
 * 仕様:
 * - ローカルモデルのパス指定、フォルダ選択ダイアログ呼び出し、モデルロードボタンを提供。
 * - MockEmbedderへの切り替え機能もサポート。
 * - ロード状態、モデル名、次元数をバッジ等で表示。
 */

import React, { useState } from 'react';
import { Cpu, FolderSearch, CheckCircle2, AlertCircle } from 'lucide-react';
import { selectFolderDialog, loadModel } from '../api/client';

export function ModelSelector({ modelPath, setModelPath, modelStatus, setModelStatus }) {
  const [loading, setLoading] = useState(false);
  const [useMock, setUseMock] = useState(false);

  const handleBrowse = async () => {
    try {
      const selected = await selectFolderDialog('ローカルモデルのフォルダを選択してください');
      if (selected) {
        setModelPath(selected);
      }
    } catch (err) {
      alert(`フォルダ選択エラー: ${err.message}`);
    }
  };

  const handleLoad = async () => {
    try {
      setLoading(true);
      const res = await loadModel(useMock ? 'mock' : modelPath, useMock);
      setModelStatus(res);
    } catch (err) {
      alert(`モデルロードエラー: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const PRESETS = [
    { label: '🌟 Multilingual E5 Base (多言語推奨・速度精度バランス, 768d, ~0.1s)', path: '/Users/mine/000_work/test/PoC_lag/models/multilingual-e5-base' },
    { label: '🇯🇵 Sup-SimCSE-JA Large (日本語特化SOTA・高精度, 1024d, ~0.3s)', path: '/Users/mine/000_work/test/PoC_lag/models/sup-simcse-ja-large' },
    { label: '🇯🇵 Sup-SimCSE-JA Base (日本語特化・高速, 768d, ~0.1s)', path: '/Users/mine/000_work/test/PoC_lag/models/sup-simcse-ja-base' },
    { label: '🇯🇵 SBERT-Base-JA (日本語BERT定番・MIT, 768d, ~0.1s)', path: '/Users/mine/000_work/test/PoC_lag/models/sbert-base-ja' },
    { label: '⚡ Static-Embedding-JA (超高速埋め込み・MIT, 1024d, ~0.01s)', path: '/Users/mine/000_work/test/PoC_lag/models/static-embedding-japanese' },
    { label: '🏆 BGE-M3 (最高峰多言語SOTA・長文対応, 1024d, ~1.4s)', path: '/Users/mine/000_work/test/PoC_lag/models/bge-m3' },
    { label: '🚀 Multilingual E5 Large (E5大型版, 1024d, ~0.4s)', path: '/Users/mine/000_work/test/PoC_lag/models/multilingual-e5-large' },
    { label: '⚡ Multilingual E5 Small (超高速・軽量, 384d, ~0.03s)', path: '/Users/mine/000_work/test/PoC_lag/models/multilingual-e5-small' },
    { label: '📁 カスタムパス指定', path: '' },
  ];

  return (
    <div className="card">
      <div className="card-title">
        <Cpu size={18} color="#10b981" />
        <span>Embedding モデル設定</span>
        {modelStatus?.loaded && (
          <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
            {modelStatus.is_mock ? 'Mock (384d)' : `Loaded (${modelStatus.dim}d)`}
          </span>
        )}
      </div>

      <div className="form-group">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <label className="form-label" style={{ marginBottom: 0 }}>ローカルモデル選択</label>
          <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={useMock}
              onChange={(e) => setUseMock(e.target.checked)}
            />
            検証用Mockモデルを使用
          </label>
        </div>

        {!useMock && (
          <select
            className="input-text"
            style={{ marginBottom: '8px', width: '100%', cursor: 'pointer' }}
            value={PRESETS.some(p => p.path === modelPath) ? modelPath : ''}
            onChange={(e) => {
              if (e.target.value) setModelPath(e.target.value);
            }}
          >
            {PRESETS.map((p, idx) => (
              <option key={idx} value={p.path}>{p.label}</option>
            ))}
          </select>
        )}

        <div className="input-row">
          <input
            type="text"
            className="input-text"
            placeholder="/path/to/models/embedding-model"
            value={useMock ? 'Mock Embedder (オフライン高速検証用)' : modelPath}
            onChange={(e) => setModelPath(e.target.value)}
            disabled={useMock}
          />
          {!useMock && (
            <button
              className="btn btn-secondary"
              onClick={handleBrowse}
              disabled={loading}
            >
              <FolderSearch size={16} />
              <span>選択</span>
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={handleLoad}
            disabled={loading || (!useMock && !modelPath)}
          >
            <CheckCircle2 size={16} />
            <span>{loading ? 'ロード中...' : 'Load Model'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
