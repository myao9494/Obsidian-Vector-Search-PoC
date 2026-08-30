/**
 * ハイブリッド検索設定の共通LocalStorage管理ユーティリティ
 * 仕様:
 * - 「ハイブリッド検索」タブと「AIコンテキスト作成」タブで検索設定（URL、重み、融合方式、検索単位、ORクエリ）を共有・完全同期。
 */

export const HYBRID_STORAGE_KEYS = {
  KEYWORD_URL: 'poc_keyword_api_url',
  SEARCH_MODE: 'poc_hybrid_search_mode',
  FUSION_METHOD: 'poc_hybrid_fusion_method',
  VECTOR_RATIO: 'poc_hybrid_vector_ratio',
  TOP_K: 'poc_hybrid_top_k',
  USE_OR_QUERY: 'poc_hybrid_use_or_query',
};

/**
 * 現在保存されているハイブリッド検索設定を取得する
 */
export function getSavedHybridSettings() {
  const keywordApiUrl = localStorage.getItem(HYBRID_STORAGE_KEYS.KEYWORD_URL) || 'http://127.0.0.1:8079';
  const searchMode = localStorage.getItem(HYBRID_STORAGE_KEYS.SEARCH_MODE) || 'chunk';
  const fusionMethod = localStorage.getItem(HYBRID_STORAGE_KEYS.FUSION_METHOD) || 'rrf';
  const rawRatio = localStorage.getItem(HYBRID_STORAGE_KEYS.VECTOR_RATIO);
  const vectorRatio = rawRatio !== null ? parseInt(rawRatio, 10) : 50;
  const rawTopK = localStorage.getItem(HYBRID_STORAGE_KEYS.TOP_K);
  const topK = rawTopK !== null ? parseInt(rawTopK, 10) : 20;
  const useOrQuery = localStorage.getItem(HYBRID_STORAGE_KEYS.USE_OR_QUERY) !== 'false';

  const validRatio = isNaN(vectorRatio) ? 50 : Math.max(0, Math.min(100, vectorRatio));
  const validTopK = isNaN(topK) ? 20 : Math.max(1, topK);

  const vWeight = validRatio / 100.0;
  const kWeight = (100.0 - validRatio) / 100.0;

  return {
    keywordApiUrl,
    searchMode,
    fusionMethod,
    vectorRatio: validRatio,
    vWeight,
    kWeight,
    topK: validTopK,
    useOrQuery,
  };
}

/**
 * ハイブリッド検索設定をLocalStorageに保存する
 */
export function saveHybridSettings(settings) {
  if (settings.keywordApiUrl !== undefined) {
    localStorage.setItem(HYBRID_STORAGE_KEYS.KEYWORD_URL, settings.keywordApiUrl);
  }
  if (settings.searchMode !== undefined) {
    localStorage.setItem(HYBRID_STORAGE_KEYS.SEARCH_MODE, settings.searchMode);
  }
  if (settings.fusionMethod !== undefined) {
    localStorage.setItem(HYBRID_STORAGE_KEYS.FUSION_METHOD, settings.fusionMethod);
  }
  if (settings.vectorRatio !== undefined) {
    localStorage.setItem(HYBRID_STORAGE_KEYS.VECTOR_RATIO, String(settings.vectorRatio));
  }
  if (settings.topK !== undefined) {
    localStorage.setItem(HYBRID_STORAGE_KEYS.TOP_K, String(settings.topK));
  }
  if (settings.useOrQuery !== undefined) {
    localStorage.setItem(HYBRID_STORAGE_KEYS.USE_OR_QUERY, String(settings.useOrQuery));
  }
}
