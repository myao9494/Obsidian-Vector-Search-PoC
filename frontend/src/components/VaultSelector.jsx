/**
 * Obsidian Vault 選択コンポーネント
 * 仕様:
 * - Vaultの絶対パス入力欄および「フォルダ選択」ボタンを提供。
 * - 「フォルダ選択」ボタン押下時に FastAPI 経由でOSネイティブダイアログを呼び出す。
 */

import React, { useState } from 'react';
import { Folder, FolderSearch, CheckCircle2 } from 'lucide-react';
import { selectFolderDialog } from '../api/client';

export function VaultSelector({ vaultPath, setVaultPath, onVaultChanged }) {
  const [loading, setLoading] = useState(false);

  const handleBrowse = async () => {
    try {
      setLoading(true);
      const selected = await selectFolderDialog('Obsidian Vault フォルダを選択してください');
      if (selected) {
        setVaultPath(selected);
        if (onVaultChanged) onVaultChanged(selected);
      }
    } catch (err) {
      alert(`フォルダ選択エラー: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div className="card-title">
        <Folder size={18} color="#6366f1" />
        <span>Obsidian Vault 設定</span>
      </div>
      <div className="form-group">
        <label className="form-label">Vault ディレクトリパス</label>
        <div className="input-row">
          <input
            type="text"
            className="input-text"
            placeholder="/Users/username/Obsidian/MyVault または D:\Obsidian\MyVault"
            value={vaultPath}
            onChange={(e) => {
              setVaultPath(e.target.value);
              if (onVaultChanged) onVaultChanged(e.target.value);
            }}
          />
          <button
            className="btn btn-secondary"
            onClick={handleBrowse}
            disabled={loading}
          >
            <FolderSearch size={16} />
            <span>{loading ? '選択中...' : 'フォルダ選択'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
