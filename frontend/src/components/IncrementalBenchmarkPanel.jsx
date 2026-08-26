/**
 * ファイル差分更新・ライブベンチマーク検証パネルコンポーネント
 * 仕様:
 * - 監視フォルダ（Vault）内の特定ファイルパスを入力するインボックスを提供。
 * - ユーザーが直接テキストを編集して差分更新を実行、または外部エディタで保存されたファイルを即時検知・更新。
 * - 意地悪テスト（1万文字超長文、特殊記号、空ファイル、見出し乱舞）をワンクリックで注入・検証。
 * - 各工程の所要時間（ミリ秒: I/Oハッシュ、チャンキング、Embedding推論、DB保存、総時間）をリアルタイムにカード・バー表示。
 * - 過去の測定履歴を保持し、変更内容によるパフォーマンス変化を視覚的に比較可能。
 */

import React, { useState } from 'react';
import {
  Zap,
  Play,
  RefreshCw,
  Clock,
  Cpu,
  Layers,
  FileCode,
  Flame,
  Bomb,
  FileText,
  ListOrdered,
  CheckCircle,
  AlertTriangle,
  History,
} from 'lucide-react';
import { updateSingleFile } from '../api/client';

const EVIL_PRESETS = {
  LONG: {
    name: '🔥 超長文 (10,000文字)',
    generate: (title) => {
      let body = `# ${title || '超長文負荷テスト'}\n\n`;
      for (let i = 1; i <= 25; i++) {
        body += `## 第${i}セクション 高負荷検証用テキストブロック ${i}\n`;
        body += `これは社内検索システムのベクトル更新性能を極限まで検証するためのテストデータです。\n`;
        body += `自然言語処理モデルの推論スループットおよびチャンク分割の耐久性を確認します。\n\n`;
      }
      return body;
    },
  },
  SPECIAL: {
    name: '💣 特殊記号 & XSS',
    generate: (title) => {
      return `# ${title || '特殊記号テスト'} <script>alert('test')</script>\n\n` +
        `## 記号乱舞 !@#$%^&*()_+{}[]|:;"'<>?,./~\\\n\n` +
        `- [[ノート名|別名エイリアス]]\n` +
        `- [タグ: #AI #検証_2026 #テスト/階層/タグ]\n` +
        `- 数式: $E=mc^2$ および $$\\sum_{i=1}^n x_i$$\n` +
        `\`\`\`python\ndef evil_code():\n    return "特殊エスケープ \\n \\t \\r"\n\`\`\`\n`;
    },
  },
  EMPTY: {
    name: '📄 空ファイル',
    generate: () => '',
  },
  HEADINGS: {
    name: '📑 見出し乱舞 (30階層)',
    generate: (title) => {
      let body = `# ${title || '見出し構造テスト'}\n\n`;
      for (let i = 1; i <= 15; i++) {
        body += `## レベル2 見出し ${i}\n本文1行目\n### レベル3 見出し ${i}-A\n本文2行目\n#### レベル4 見出し ${i}-B\n本文3行目\n\n`;
      }
      return body;
    },
  },
};

export function IncrementalBenchmarkPanel({ vaultPath, isModelLoaded, onUpdateCompleted }) {
  const [filePath, setFilePath] = useState('sample_benchmark.md');
  const [content, setContent] = useState(
    '# 差分更新テストノート\n\n## 概要\nこのノートを編集して、モデルの差分更新時間をリアルタイムに検証します。\n\n## 更新メモ\nテキストを変更して「差分更新を実行」を押してください。\n'
  );
  const [isUpdating, setIsUpdating] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');

  // 差分更新の実行
  const handleRunUpdate = async (customContent = null) => {
    if (!vaultPath) {
      setErrorMessage('先にVaultフォルダを選択してください。');
      return;
    }
    if (!isModelLoaded) {
      setErrorMessage('先にEmbeddingモデルをロードしてください。');
      return;
    }
    if (!filePath.trim()) {
      setErrorMessage('ファイルパスを入力してください。');
      return;
    }

    setErrorMessage('');
    setIsUpdating(true);

    try {
      const textToSend = customContent !== null ? customContent : content;
      const res = await updateSingleFile(vaultPath, filePath.trim(), textToSend);
      setLastResult(res);
      setHistory((prev) => [
        {
          id: Date.now(),
          timestamp: new Date().toLocaleTimeString(),
          file: res.relative_path,
          status: res.status,
          chunks: res.chunk_count,
          total_ms: res.total_time_ms,
          embedding_ms: res.embedding_time_ms,
        },
        ...prev.slice(0, 7), // 直近8件
      ]);
      if (onUpdateCompleted) onUpdateCompleted();
    } catch (err) {
      setErrorMessage(err.message || '更新処理中にエラーが発生しました。');
    } finally {
      setIsUpdating(false);
    }
  };

  // 外部ファイル変更を検知して測定（テキスト送信なしでファイル自体をスキャン）
  const handleDetectExternalFile = async () => {
    if (!vaultPath || !isModelLoaded || !filePath.trim()) return;
    setErrorMessage('');
    setIsUpdating(true);
    try {
      const res = await updateSingleFile(vaultPath, filePath.trim(), null);
      setLastResult(res);
      setHistory((prev) => [
        {
          id: Date.now(),
          timestamp: new Date().toLocaleTimeString(),
          file: res.relative_path,
          status: res.status,
          chunks: res.chunk_count,
          total_ms: res.total_time_ms,
          embedding_ms: res.embedding_time_ms,
        },
        ...prev.slice(0, 7),
      ]);
      if (onUpdateCompleted) onUpdateCompleted();
    } catch (err) {
      setErrorMessage(err.message || 'ファイル検知・更新に失敗しました。');
    } finally {
      setIsUpdating(false);
    }
  };

  // 意地悪プリセットの適用
  const applyPreset = (presetKey) => {
    const preset = EVIL_PRESETS[presetKey];
    if (!preset) return;
    const newText = preset.generate(filePath.replace(/\.[^/.]+$/, ''));
    setContent(newText);
    handleRunUpdate(newText);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'created':
        return <span className="status-badge status-created">🟢 新規追加 (Created)</span>;
      case 'updated':
        return <span className="status-badge status-updated">🔵 内容更新 (Updated)</span>;
      case 'skipped':
        return <span className="status-badge status-skipped">⚪ 変更なし (Skipped)</span>;
      case 'deleted':
        return <span className="status-badge status-deleted">🔴 削除検知 (Deleted)</span>;
      case 'error':
        return <span className="status-badge status-error">⚠️ エラー (Error)</span>;
      default:
        return <span className="status-badge">{status}</span>;
    }
  };

  return (
    <div className="panel incremental-panel">
      <div className="panel-header">
        <div className="panel-title">
          <Zap className="icon icon-zap pulse-glow" size={20} />
          <span>⚡ ファイル差分更新・ライブ時間検証 (Live Benchmark)</span>
        </div>
        <span className="panel-subtitle">
          ファイルの変更検知からEmbedding・インデックス更新完了までの所要時間をミリ秒単位でリアルタイム計測
        </span>
      </div>

      {errorMessage && (
        <div className="error-alert">
          <AlertTriangle size={18} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* ファイルパス入力とアクション */}
      <div className="benchmark-controls">
        <div className="input-group flex-1">
          <label className="input-label">
            <FileCode size={16} />
            <span>対象ファイル相対パス:</span>
          </label>
          <input
            type="text"
            className="input-text"
            placeholder="例: 社内経費精算ガイド.md または test_note.md"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
          />
        </div>

        <div className="control-buttons">
          <button
            className="btn btn-primary"
            onClick={() => handleRunUpdate()}
            disabled={isUpdating || !isModelLoaded}
          >
            {isUpdating ? (
              <RefreshCw className="icon spin" size={16} />
            ) : (
              <Play className="icon" size={16} />
            )}
            <span>差分更新を実行＆測定</span>
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleDetectExternalFile}
            disabled={isUpdating || !isModelLoaded}
            title="外部エディタでファイルを編集・保存した後に押すと変更を検知して測定します"
          >
            <RefreshCw className={`icon ${isUpdating ? 'spin' : ''}`} size={16} />
            <span>外部編集を検知</span>
          </button>
        </div>
      </div>

      {/* 意地悪テストプリセットバー */}
      <div className="preset-bar">
        <span className="preset-title">🧪 意地悪テストプリセット:</span>
        <button
          className="btn-preset btn-preset-fire"
          onClick={() => applyPreset('LONG')}
          disabled={isUpdating || !isModelLoaded}
        >
          <Flame size={14} />
          <span>超長文 10,000字</span>
        </button>
        <button
          className="btn-preset btn-preset-bomb"
          onClick={() => applyPreset('SPECIAL')}
          disabled={isUpdating || !isModelLoaded}
        >
          <Bomb size={14} />
          <span>特殊記号 & XSS</span>
        </button>
        <button
          className="btn-preset"
          onClick={() => applyPreset('HEADINGS')}
          disabled={isUpdating || !isModelLoaded}
        >
          <ListOrdered size={14} />
          <span>見出し乱舞</span>
        </button>
        <button
          className="btn-preset"
          onClick={() => applyPreset('EMPTY')}
          disabled={isUpdating || !isModelLoaded}
        >
          <FileText size={14} />
          <span>空ファイル</span>
        </button>
      </div>

      {/* 編集エディタと測定結果の2カラムレイアウト */}
      <div className="benchmark-grid">
        {/* 左: 直接編集テキストエリア */}
        <div className="editor-container">
          <div className="editor-header">
            <span>📝 ファイル直接編集 (テスト用テキスト)</span>
            <span className="char-count">{content.length.toLocaleString()} 文字</span>
          </div>
          <textarea
            className="benchmark-textarea"
            rows={7}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="ここにマークダウン本文を入力して差分更新時間を検証できます..."
          />
        </div>

        {/* 右: 測定結果カード */}
        <div className="metrics-card">
          {lastResult ? (
            <div className="metrics-content">
              <div className="metrics-top">
                <div className="metrics-status">
                  {getStatusBadge(lastResult.status)}
                  <span className="metrics-path">{lastResult.relative_path}</span>
                </div>
                <div className="metrics-total">
                  <span className="total-label">総所要時間</span>
                  <span className="total-value">{lastResult.total_time_ms.toFixed(1)} <small>ms</small></span>
                </div>
              </div>

              {/* 各フェーズの内訳バー */}
              <div className="breakdown-grid">
                <div className="breakdown-item">
                  <div className="breakdown-label">
                    <Clock size={13} />
                    <span>I/O & ハッシュ</span>
                  </div>
                  <span className="breakdown-val">{lastResult.io_hash_time_ms.toFixed(2)} ms</span>
                </div>

                <div className="breakdown-item">
                  <div className="breakdown-label">
                    <Layers size={13} />
                    <span>チャンキング</span>
                  </div>
                  <span className="breakdown-val">{lastResult.chunking_time_ms.toFixed(2)} ms</span>
                </div>

                <div className="breakdown-item highlight">
                  <div className="breakdown-label">
                    <Cpu size={13} />
                    <span>Embedding推論</span>
                  </div>
                  <span className="breakdown-val">{lastResult.embedding_time_ms.toFixed(2)} ms</span>
                </div>

                <div className="breakdown-item">
                  <div className="breakdown-label">
                    <FileText size={13} />
                    <span>DB/FAISS保存</span>
                  </div>
                  <span className="breakdown-val">{lastResult.db_time_ms.toFixed(2)} ms</span>
                </div>
              </div>

              <div className="metrics-footer">
                <div className="chunk-badge">
                  <span>生成チャンク数:</span>
                  <strong>{lastResult.chunk_count} 個</strong>
                </div>
                <div className="bottleneck-hint">
                  {lastResult.total_time_ms > 0 && (
                    <span>
                      🧠 推論占有率: {((lastResult.embedding_time_ms / (lastResult.total_time_ms || 1)) * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="metrics-placeholder">
              <Zap size={32} className="placeholder-icon" />
              <span>「差分更新を実行＆測定」またはプリセットをクリックすると、ミリ秒単位の内訳が表示されます。</span>
            </div>
          )}
        </div>
      </div>

      {/* 履歴リスト */}
      {history.length > 0 && (
        <div className="history-section">
          <div className="history-header">
            <History size={14} />
            <span>直近の測定履歴</span>
          </div>
          <div className="history-list">
            {history.map((h) => (
              <div key={h.id} className="history-chip">
                <span className="history-time">{h.timestamp}</span>
                <span className="history-file">{h.file}</span>
                <span className="history-badge">{h.status}</span>
                <span className="history-chunks">{h.chunks} chunks</span>
                <span className="history-total"><strong>{h.total_ms.toFixed(1)} ms</strong></span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
