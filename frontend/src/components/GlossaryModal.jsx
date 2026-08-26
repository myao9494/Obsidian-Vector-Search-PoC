/**
 * 専門用語・類似語辞書 (Glossary) 編集モーダルコンポーネント
 * 仕様:
 * - Mac等でExcelアプリが無くてもWeb UI上で専門用語辞書を直接作成・編集・保存（.xlsx書き出し）。
 * - 新2列フォーマット（第1列: 専門用語（カンマ区切りで類似語も含む）, 第2列: 意味・解説）に対応。
 * - 用語の追加、インライン編集、削除、検索絞り込み、サンプル用語挿入。
 * - 保存時にバックエンドの POST /api/dictionary/save を呼び出し、Excelファイルを即時更新・インメモリ再読み込み。
 */

import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Plus,
  Trash2,
  Save,
  X,
  Sparkles,
  FileSpreadsheet,
  Search,
  CheckCircle,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { getDictionaryStatus, saveDictionary } from '../api/client';

export function GlossaryModal({ isOpen, onClose, vaultPath, onDictionarySaved }) {
  const [entries, setEntries] = useState([]);
  const [fileName, setFileName] = useState('glossary.xlsx');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [statusMessage, setStatusMessage] = useState(null);

  // モーダルオープン時に現在の辞書を取得
  useEffect(() => {
    if (isOpen && vaultPath) {
      loadCurrentDictionary();
    }
  }, [isOpen, vaultPath]);

  const loadCurrentDictionary = async () => {
    try {
      setLoading(true);
      setStatusMessage(null);
      const res = await getDictionaryStatus(vaultPath);
      if (res.loaded && res.entries && res.entries.length > 0) {
        setEntries(res.entries);
        if (res.file_name) setFileName(res.file_name);
      } else {
        // 未作成または空の場合は初期1行を用意
        setEntries([
          { terms: '', description: '' }
        ]);
      }
    } catch (err) {
      console.error('辞書の取得に失敗:', err);
      setStatusMessage({ type: 'error', text: `辞書の取得に失敗しました: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const handleAddRow = () => {
    setEntries((prev) => [...prev, { terms: '', description: '' }]);
  };

  const handleInsertSample = () => {
    const samples = [
      { terms: 'PJ-X, プロジェクトX, PJX, PX', description: '2024年発足の社内基幹システム刷新プロジェクト' },
      { terms: 'ポチッと君, ポチット, pochito', description: '社内の交通費・経費精算および旅費申請システム' },
      { terms: 'SLA, サービスレベルアグリーメント, サービス品質保証', description: '契約上のシステム稼働率および品質保証基準' },
      { terms: 'DB, データベース, Database', description: '' },
    ];
    setEntries((prev) => {
      // 既存の空行があれば除去してサンプルを結合
      const filtered = prev.filter((e) => e.terms?.trim() || e.description?.trim());
      return [...filtered, ...samples];
    });
  };

  const handleChangeEntry = (index, field, value) => {
    setEntries((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const handleDeleteRow = (index) => {
    setEntries((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.length > 0 ? next : [{ terms: '', description: '' }];
    });
  };

  const handleSave = async () => {
    if (!vaultPath) {
      alert('先にVaultディレクトリを選択してください');
      return;
    }

    // 空行を除外
    const validEntries = entries.filter(
      (e) => (e.terms && e.terms.trim().length > 0) || (e.description && e.description.trim().length > 0)
    );

    if (validEntries.length === 0) {
      alert('保存する専門用語を最低1件入力してください');
      return;
    }

    try {
      setSaving(true);
      setStatusMessage(null);
      const res = await saveDictionary(vaultPath, validEntries, fileName);
      setStatusMessage({
        type: 'success',
        text: `辞書ファイル（${res.file_name}）に ${res.total_entries} 件の用語を保存しました！`,
      });
      if (onDictionarySaved) {
        onDictionarySaved(res);
      }
      setTimeout(() => {
        // 保存成功後に少し待って通知を消す
      }, 3000);
    } catch (err) {
      setStatusMessage({ type: 'error', text: `保存エラー: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  // 検索フィルタ適用
  const filteredEntries = entries.filter((e) => {
    if (!searchFilter) return true;
    const q = searchFilter.toLowerCase();
    const terms = (e.terms || e.term || '').toLowerCase();
    const desc = (e.description || '').toLowerCase();
    return terms.includes(q) || desc.includes(q);
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glossary-modal" onClick={(e) => e.stopPropagation()}>
        {/* モーダルヘッダー */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div className="brand-icon" style={{ width: '36px', height: '36px' }}>
              <BookOpen size={20} color="#38bdf8" />
            </div>
            <div>
              <h2 className="modal-title">📖 専門用語・類似語辞書エディタ</h2>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
                Excel (.xlsx) 直接編集 & 類似語カンマ区切り定義
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="badge badge-excel">
              <FileSpreadsheet size={13} style={{ marginRight: '4px' }} />
              {fileName} ({entries.filter((e) => e.terms?.trim()).length} 件)
            </span>
            <button className="btn-icon-close" onClick={onClose} title="閉じる">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* ガイドバナー */}
        <div className="glossary-guide-banner">
          <Sparkles size={16} color="#38bdf8" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div style={{ fontSize: '12px', lineHeight: 1.5 }}>
            <strong>新フォーマット (2列形式):</strong> 第1列（専門用語）に、代表語と同義語・略称をカンマ（<code>,</code> や <code>、</code>）区切りでまとめて入力できます（例: <code>PJ-X, プロジェクトX, PJX, PX</code>）。第2列には意味・解説（任意）を記述できます。MacでもExcelアプリなしで直接保存・更新されます。
          </div>
        </div>

        {/* ステータスメッセージ */}
        {statusMessage && (
          <div className={`status-alert ${statusMessage.type === 'success' ? 'alert-success' : 'alert-error'}`}>
            {statusMessage.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* ツールバー (検索 & 追加ボタン) */}
        <div className="glossary-toolbar">
          <div className="search-input-wrapper" style={{ flex: 1, maxWidth: '360px' }}>
            <Search size={14} color="var(--text-dim)" className="search-input-icon" />
            <input
              type="text"
              className="search-input-field"
              placeholder="登録用語・解説を検索..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto' }}>
            <button className="btn btn-secondary btn-sm" onClick={handleInsertSample} title="代表的なサンプル用語を挿入">
              <Sparkles size={14} color="#38bdf8" />
              <span>サンプル挿入</span>
            </button>
            <button className="btn btn-primary btn-sm" onClick={handleAddRow}>
              <Plus size={14} />
              <span>新規用語を追加</span>
            </button>
          </div>
        </div>

        {/* 辞書エディタ テーブル */}
        <div className="glossary-table-container">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
              <RefreshCw className="spin" size={24} style={{ margin: '0 auto 10px' }} />
              <p>辞書を読み込んでいます...</p>
            </div>
          ) : (
            <table className="glossary-table">
              <thead>
                <tr>
                  <th style={{ width: '45%' }}>
                    専門用語・類似語 <span className="th-sub">(カンマ区切りで同義語も定義可能)</span>
                  </th>
                  <th style={{ width: '47%' }}>
                    意味・解説 <span className="th-sub">(任意・社内文脈の補足)</span>
                  </th>
                  <th style={{ width: '8%', textAlign: 'center' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
                      {searchFilter ? '該当する用語が見つかりません' : '用語が登録されていません。「新規用語を追加」または「サンプル挿入」をクリックしてください。'}
                    </td>
                  </tr>
                ) : (
                  filteredEntries.map((item, index) => {
                    // 元の配列におけるインデックスを特定
                    const originalIndex = entries.indexOf(item);
                    return (
                      <tr key={originalIndex}>
                        <td>
                          <input
                            type="text"
                            className="table-input"
                            placeholder="例: PJ-X, プロジェクトX, PJX, PX"
                            value={item.terms ?? (item.term ? `${item.term}${item.synonyms?.length ? ', ' + item.synonyms.join(', ') : ''}` : '')}
                            onChange={(e) => handleChangeEntry(originalIndex, 'terms', e.target.value)}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className="table-input"
                            placeholder="例: 2024年発足の社内基幹システム刷新プロジェクト"
                            value={item.description || ''}
                            onChange={(e) => handleChangeEntry(originalIndex, 'description', e.target.value)}
                          />
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className="btn-icon-delete"
                            onClick={() => handleDeleteRow(originalIndex)}
                            title="この行を削除"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* モーダルフッター */}
        <div className="modal-footer">
          <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
            保存先: <code>{vaultPath ? `${vaultPath}/${fileName}` : fileName}</code>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={onClose} disabled={saving}>
              閉じる
            </button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving || loading}>
              {saving ? <RefreshCw className="spin" size={16} /> : <Save size={16} />}
              <span>{saving ? 'Excel保存中...' : 'Excel (.xlsx) として保存'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
