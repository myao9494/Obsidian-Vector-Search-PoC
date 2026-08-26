/**
 * バックエンド REST API クライアントモジュール
 * 仕様:
 * - FastAPI サーバー（http://127.0.0.1:60000）との通信を担う。
 * - ダイアログ起動、モデルロード、インデックス開始、進捗ポーリング、DB統計、検索の各APIを呼び出す。
 */

const API_BASE = '/api';

export async function selectFolderDialog(title = 'フォルダを選択してください') {
  const res = await fetch(`${API_BASE}/dialog/select-folder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('フォルダ選択ダイアログの表示に失敗しました');
  const data = await res.json();
  return data.selected_path;
}

export async function loadModel(modelPath, useMock = false) {
  const res = await fetch(`${API_BASE}/model/load`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_path: modelPath, use_mock: useMock }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'モデルのロードに失敗しました');
  }
  return await res.json();
}

export async function getModelStatus() {
  const res = await fetch(`${API_BASE}/model/status`);
  if (!res.ok) throw new Error('モデル状態の取得に失敗しました');
  return await res.json();
}

export async function startIndex(
  vaultPath,
  chunkSize = 600,
  chunkOverlap = 80,
  forceReindex = false,
  targetExtensions = ['.md', '.markdown', '.txt']
) {
  const res = await fetch(`${API_BASE}/index/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vault_path: vaultPath,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      force_reindex: forceReindex,
      target_extensions: targetExtensions,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'インデックス処理の開始に失敗しました');
  }
  return await res.json();
}

export async function getIndexProgress() {
  const res = await fetch(`${API_BASE}/index/progress`);
  if (!res.ok) throw new Error('進捗の取得に失敗しました');
  return await res.json();
}

export async function getVaultStats(vaultPath) {
  const res = await fetch(`${API_BASE}/index/stats?vault_path=${encodeURIComponent(vaultPath)}`);
  if (!res.ok) throw new Error('統計情報の取得に失敗しました');
  return await res.json();
}

export async function searchVector(
  vaultPath,
  query,
  mode = 'chunk',
  topK = 20,
  minScore = 0.0,
  keywordBoost = true,
  boostWeight = 0.08
) {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vault_path: vaultPath,
      query,
      mode,
      top_k: topK,
      min_score: minScore,
      keyword_boost: keywordBoost,
      boost_weight: boostWeight,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || '検索に失敗しました');
  }
  return await res.json();
}

export async function updateSingleFile(vaultPath, relativePath, content = null, chunkSize = 600, chunkOverlap = 80) {
  const res = await fetch(`${API_BASE}/index/update-file`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vault_path: vaultPath,
      relative_path: relativePath,
      content,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'ファイル差分更新に失敗しました');
  }
  return await res.json();
}

export async function getDictionaryStatus(vaultPath) {
  const res = await fetch(`${API_BASE}/dictionary/status?vault_path=${encodeURIComponent(vaultPath)}`);
  if (!res.ok) throw new Error('専門用語辞書ステータスの取得に失敗しました');
  return await res.json();
}

export async function saveDictionary(vaultPath, entries, fileName = 'glossary.xlsx') {
  const res = await fetch(`${API_BASE}/dictionary/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vault_path: vaultPath,
      file_name: fileName,
      entries,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || '専門用語辞書の保存に失敗しました');
  }
  return await res.json();
}

export async function openFileLocation(path) {
  const res = await fetch(`${API_BASE}/files/open-location`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'ファイルの保存場所を開くのに失敗しました');
  }
  return await res.json();
}




