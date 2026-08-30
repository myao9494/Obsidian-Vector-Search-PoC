"""
FAISS 高速ベクトル検索モジュール
仕様:
- FAISS (faiss.IndexFlatIP) を用いた高速・高精度コサイン類似度検索。
- スコアキャリブレーション (Dense + Lexical Hybrid) による 0.0〜0.98 の滑らかなグラデーション生成（1.0000飽和の解消と明瞭な閾値分離）。
- Document検索モード: 1 Markdown = 1 Embedding による文書単位の類似度検索。
- Chunk検索モード: チャンク単位の類似度検索と前後文脈（前/ヒット/後）の取得。
- 反応文特定 (Salient Sentence Extraction) による最もクエリに合致した根拠文の抽出。
"""

import enum
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.db import (
    get_all_chunk_embeddings,
    get_all_document_embeddings,
    get_chunk_with_context,
    get_document_by_id,
    get_model_db_path,
)
from app.dictionary import GlossaryDictionary
from app.embedder import BaseEmbedder
from app.faiss_index import FaissVectorIndex


class SearchMode(str, enum.Enum):
    DOCUMENT = "document"
    CHUNK = "chunk"


@dataclass
class SearchResultItem:
    """検索結果の1件分のデータ"""
    document_id: int
    path: str
    title: str
    score: float
    full_path: str = ""
    chunk_id: Optional[int] = None
    chunk_index: Optional[int] = None
    hit_text: Optional[str] = None
    preview: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    salient_sentence: Optional[str] = None


@dataclass
class SearchResponse:
    """検索レスポンス"""
    query: str
    mode: SearchMode
    results: List[SearchResultItem]
    total_candidates: int
    query_embedding_time_ms: float
    search_time_ms: float
    total_time_ms: float
    extracted_keywords: List[str] = field(default_factory=list)
    keyword_query: str = ""
    rag_context_xml: str = ""
    rag_context_markdown: str = ""
    detected_terms: List[Dict[str, Any]] = field(default_factory=list)


def generate_rag_contexts(results: List[SearchResultItem], query: str) -> Tuple[str, str]:
    """
    検索結果の上位ドキュメント/チャンクから、LLMに投入可能な標準RAGコンテキスト（XML形式およびMarkdown形式）を生成する。
    """
    if not results:
        xml_empty = f"<context query=\"{query}\">\n  <!-- 関連コンテキストは見つかりませんでした -->\n</context>"
        md_empty = f"## 参考コンテキスト (クエリ: {query})\n*関連するコンテキストは見つかりませんでした。*"
        return xml_empty, md_empty

    # 1. XML形式（Claude / ChatGPT / 一般的なRAGエージェント向け）
    xml_lines = [f'<context query="{query}">']
    for idx, item in enumerate(results[:5], start=1):
        content = (item.hit_text or item.preview or "").strip()
        xml_lines.append(f'  <document index="{idx}" title="{item.title}" path="{item.path}" score="{item.score:.4f}">')
        for line in content.splitlines():
            xml_lines.append(f"    {line}")
        xml_lines.append('  </document>')
    xml_lines.append('</context>')
    rag_xml = "\n".join(xml_lines)

    # 2. Markdown引用形式（ChatGPT / 一般ドキュメント向け）
    md_lines = [f"## 参考コンテキスト\nユーザーの質問: `{query}`\n"]
    for idx, item in enumerate(results[:5], start=1):
        content = (item.hit_text or item.preview or "").strip()
        md_lines.append(f"### [{idx}] {item.title} (Score: {item.score:.4f}, Path: `{item.path}`)")
        for line in content.splitlines():
            md_lines.append(f"> {line}" if line else ">")
        md_lines.append("")
    rag_md = "\n".join(md_lines).strip()

    return rag_xml, rag_md



def extract_query_keywords(query: str) -> List[str]:
    """
    クエリ文字列から助詞や記号を除いた重要キーワードリストを抽出する。
    漢字ブロック、カタカナブロック、英数単語の文字種境界や助詞で自然文を分解する。
    """
    stop_words = {
        "について", "に関する", "の基礎", "とは", "概要", "詳細", "まとめ", "方法",
        "どう", "なに", "なぜ", "これ", "それ", "あれ", "どこ", "だれ", "ので",
        "から", "たい", "です", "ます", "ある", "いる", "する", "こと", "もの"
    }

    # 1. 記号や空白で大まかに分割
    coarse_tokens = re.split(r"[\s\.,、。!?！？_/()（）「」『』【】]+", query)
    
    keywords_set = set()
    for token in coarse_tokens:
        t = token.strip()
        if not t:
            continue
        
        # ハイフン付き英単語（例: mlx-whisper）をまず保護
        hyphen_words = re.findall(r"[a-zA-Z0-9]+-[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*", t)
        for hw in hyphen_words:
            if len(hw) >= 3:
                keywords_set.add(hw)

        # 漢字の連続、カタカナの連続、英単語の連続を抽出
        chunks = re.findall(r"[\u4e00-\u9fff]+|[\u30a0-\u30ff]{2,}|[a-zA-Z0-9]{2,}", t)
        for chunk in chunks:
            c = chunk.strip()
            # 助詞・活用語尾の簡易トリミング
            c = re.sub(r"^(?:ので|から|より|など|へと|には|では|への|での)", "", c)
            c = re.sub(r"(?:について|に関する|なので|でした|ました|したい|たい|です|ます|ので|から|ない|れた|った|いた|して|する|って)$", "", c)
            if len(c) >= 2 and c not in stop_words:
                keywords_set.add(c)

    return sorted(list(keywords_set), key=lambda x: -len(x))


def compute_calibrated_score(
    dense_sim: float,
    keywords: List[str],
    title: str,
    text: str,
    path: str = "",
    keyword_boost: bool = True,
    boost_weight: float = 0.08,
) -> float:
    """
    ruri-v3 の異方性ベースラインノイズ（無関係テキストの生内積 0.65〜0.76）を除去し、
    真に関連する文書のみが 0.70〜0.98 の高スコアとなり、合っていない無関係な文書は 0.0〜0.25 に沈む
    メリハリのあるキャリブレーションスコアを算出する。
    """
    raw_sim = float(dense_sim)

    # 1. ruri-v3 の生コサイン類似度のノイズフロア除去 & 急峻な正規化
    # raw_sim < 0.70: 無関係ノイズ (0.00 〜 0.15)
    # raw_sim 0.70 〜 0.93: 実質的な意味類似度区間 (0.15 〜 0.82)
    if raw_sim < 0.70:
        base_dense = max(0.0, (raw_sim - 0.45) / 1.8)
    else:
        norm = min(max((raw_sim - 0.70) / 0.23, 0.0), 1.0)
        base_dense = 0.15 + 0.67 * (norm ** 1.6)

    if not keyword_boost or not keywords:
        return round(float(min(base_dense, 0.98)), 4)

    # 2. キーワードマッチ率およびメタデータ（Tags / Aliases / Title）一致度の計算
    title_lower = (title or "").lower()
    text_lower = (text or "").lower()
    path_lower = (path or "").lower()
    stem_lower = Path(path).stem.lower() if path else ""

    matched_kw_count = 0
    title_matched_count = 0
    meta_matched_count = 0
    exact_stem_matched = False

    # テキスト内のメタデータヘッダー部分（[Tags: ...], [Aliases: ...], [Keywords: ...]）を抽出
    meta_header_match = re.search(r"^\[.*?\](?:\s*\[Tags:.*?\])?(?:\s*\[Aliases:.*?\])?(?:\s*\[Keywords:.*?\])?", text, re.IGNORECASE)
    meta_header_text = meta_header_match.group(0).lower() if meta_header_match else ""

    for kw in keywords:
        kw_l = kw.lower()
        matched = False
        if kw_l == stem_lower:
            exact_stem_matched = True
            matched = True
        if kw_l in title_lower or kw_l in path_lower:
            title_matched_count += 1
            matched = True
        if meta_header_text and kw_l in meta_header_text:
            meta_matched_count += 1
            matched = True
        if kw_l in text_lower:
            matched = True
        if matched:
            matched_kw_count += 1

    total_kw = len(keywords)
    match_ratio = matched_kw_count / total_kw if total_kw > 0 else 0.0
    
    # ボーナス計算
    title_bonus = 0.08 if exact_stem_matched else min(title_matched_count * 0.03, 0.06)
    tag_bonus = min(meta_matched_count * 0.04, 0.08)
    lexical_score = (match_ratio * 0.12) + title_bonus + tag_bonus

    # 3. 合成 (Dense + Lexical + Metadata)
    final_score = min(max(base_dense + lexical_score, 0.0), 0.98)
    return round(final_score, 4)


def strip_markdown_to_plain(text: str) -> str:
    """Markdown記法（リンク、画像、装飾、テーブル枠）を自然言語プレーンテキストに変換する"""
    t = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    t = re.sub(r"!\[\[[^\]]+\]\]", "", t)
    t = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", t)
    t = re.sub(r"https?://[^\s\)\>]+", "", t)
    t = re.sub(r"\|", " ", t)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^[\s\t]*[-\*\+]\s+|^[\s\t]*\d+\.\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"[\*_`~]", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def is_natural_sentence(s: str) -> bool:
    """文が意味のある自然言語文であるか判定する"""
    if not s or len(s) < 8:
        return False

    jp_chars = re.findall(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]", s)
    if jp_chars:
        jp_ratio = len(jp_chars) / len(s)
        hiragana = re.findall(r"[\u3040-\u309f]", s)
        kanji = re.findall(r"[\u4e00-\u9fff]", s)
        if len(hiragana) == 0 and len(kanji) == 0:
            return False
        if jp_ratio < 0.25:
            return False

    return True


def find_salient_sentence(
    text: str,
    query_vec: np.ndarray,
    embedder: BaseEmbedder,
    min_sentence_score: float = 0.55,
) -> Optional[str]:
    """
    チャンクテキストの中から、クエリベクトルと最も類似度の高い「反応文（核となる一文）」を特定する。
    """
    if not text:
        return None

    plain_text = strip_markdown_to_plain(text)
    if not plain_text:
        return None

    raw_sentences = re.split(r"(?:\n+|(?<=[。！？\.\?!]))", plain_text)
    valid_sentences = []

    for raw_s in raw_sentences:
        s = raw_s.strip()
        cleaned_s = re.sub(r"^[\s#\-*|>|`\(\)\[\]]+|[\s#\-*|>|`\(\)\[\]]+$", "", s).strip()
        
        if len(cleaned_s) < 8:
            continue

        natural_chars = re.findall(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\w]", cleaned_s)
        if len(natural_chars) < 6:
            continue

        if re.search(r"\.(?:jp|com|net|html|php|aspx|ipynb|excalidraw)", cleaned_s, re.IGNORECASE):
            continue

        if not is_natural_sentence(cleaned_s):
            continue

        valid_sentences.append(cleaned_s)

    if not valid_sentences:
        return None

    # 高速化のため最大8文に制限
    candidates = valid_sentences[:8]
    try:
        s_vecs = embedder.encode_batch(candidates, is_query=False)
        scores = s_vecs @ query_vec
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        
        if best_score < min_sentence_score:
            return None
        return candidates[best_idx]
    except Exception:
        return None


class VectorSearcher:
    """FAISSによる高速オフラインベクトル検索エンジン（キャリブレーションスコア & 反応文特定 & 専門用語辞書連携機能付き）"""

    def __init__(
        self,
        db_path: str,
        embedder: BaseEmbedder,
        glossary: Optional[GlossaryDictionary] = None
    ):
        self.embedder = embedder
        resolved_db_path = str(Path(db_path).resolve())

        # DBパスの自動解決（指定されたパスが存在せず、モデル別DBが存在する場合はそちらを適用）
        if not os.path.exists(resolved_db_path):
            p = Path(resolved_db_path)
            vault_dir = p.parent.parent if p.parent.name == ".vector_search" else p.parent
            model_db = get_model_db_path(str(vault_dir), embedder=self.embedder)
            if os.path.exists(model_db):
                resolved_db_path = model_db
            elif os.path.exists(str(p.parent / "index.db")):
                resolved_db_path = str(p.parent / "index.db")

        self.db_path = resolved_db_path
        self._doc_faiss_index: Optional[FaissVectorIndex] = None
        self._chunk_faiss_index: Optional[FaissVectorIndex] = None
        self._doc_rows_cache: Optional[Dict[int, Dict[str, Any]]] = None
        self._chunk_rows_cache: Optional[Dict[int, Dict[str, Any]]] = None

        if glossary is not None:
            self.glossary = glossary
        else:
            self.glossary = self._auto_load_glossary()


    def _auto_load_glossary(self) -> Optional[GlossaryDictionary]:
        """Vault内から辞書ファイル（.xlsx / .csv）を自動探索してロード"""
        try:
            db_file = Path(self.db_path).resolve()
            # .vector_search ディレクトリの親（Vault）
            vault_dir = db_file.parent.parent if db_file.parent.name == ".vector_search" else db_file.parent
            if not vault_dir.exists():
                return None

            candidates = [
                "glossary.xlsx", "dictionary.xlsx", "synonyms.xlsx",
                "glossary.csv", "dictionary.csv", "synonyms.csv",
                "用語集.xlsx", "用語集.csv"
            ]
            for c in candidates:
                p = vault_dir / c
                if p.exists():
                    try:
                        return GlossaryDictionary.from_file(str(p))
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def _ensure_faiss_indexes(self, mode: SearchMode):
        """FAISSインデックスをロードまたはSQLiteから構築"""
        dim = self.embedder.embedding_dim

        if mode == SearchMode.DOCUMENT:
            if self._doc_faiss_index is None or self._doc_faiss_index.dim != dim:
                doc_rows = get_all_document_embeddings(self.db_path)
                index = FaissVectorIndex(dim=dim)
                self._doc_rows_cache = {}
                if doc_rows:
                    ids = []
                    vectors = []
                    for r in doc_rows:
                        vec = np.frombuffer(r["embedding"], dtype=np.float32)
                        if vec.shape[0] == dim:
                            ids.append(r["id"])
                            vectors.append(vec)
                            self._doc_rows_cache[r["id"]] = dict(r)
                    if ids:
                        index.add_items(ids=ids, vectors=np.vstack(vectors))
                self._doc_faiss_index = index

        elif mode == SearchMode.CHUNK:
            if self._chunk_faiss_index is None or self._chunk_faiss_index.dim != dim:
                chunk_rows = get_all_chunk_embeddings(self.db_path)
                index = FaissVectorIndex(dim=dim)
                self._chunk_rows_cache = {}
                if chunk_rows:
                    ids = []
                    vectors = []
                    for r in chunk_rows:
                        vec = np.frombuffer(r["embedding"], dtype=np.float32)
                        if vec.shape[0] == dim:
                            ids.append(r["id"])
                            vectors.append(vec)
                            self._chunk_rows_cache[r["id"]] = dict(r)
                    if ids:
                        index.add_items(ids=ids, vectors=np.vstack(vectors))
                self._chunk_faiss_index = index

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.CHUNK,
        top_k: int = 20,
        min_score: float = 0.0,
        keyword_boost: bool = True,
        boost_weight: float = 0.08,
    ) -> SearchResponse:
        """
        指定されたクエリでFAISSベクトル検索を実行する。
        専門用語・類似語辞書が存在する場合、自然文クエリを補強してEmbedding生成を行う。
        """
        t_total_start = time.perf_counter()

        # 専門用語辞書による用語検知およびEmbedding用クエリ補強
        detected_entries = self.glossary.detect_terms(query) if self.glossary else []
        enriched_query = self.glossary.build_enriched_query(query) if self.glossary else query

        # 1. クエリのEmbedding生成
        t_emb_start = time.perf_counter()
        query_vec = self.embedder.encode(enriched_query, is_query=True)
        t_emb_end = time.perf_counter()
        query_emb_time_ms = round((t_emb_end - t_emb_start) * 1000, 2)

        # 2. FAISS インデックスの確保 & 検索
        t_sim_start = time.perf_counter()
        self._ensure_faiss_indexes(mode)

        faiss_idx = self._doc_faiss_index if mode == SearchMode.DOCUMENT else self._chunk_faiss_index
        total_candidates = faiss_idx.total_count if faiss_idx else 0

        results: List[SearchResultItem] = []
        keywords = extract_query_keywords(query) if keyword_boost else []

        # 辞書で検知された用語・同義語・解説キーワードもキーワードブーストに追加
        if keyword_boost and detected_entries:
            for de in detected_entries:
                for v in de.all_variants():
                    if v and v not in keywords and len(v) >= 2:
                        keywords.append(v)
                if de.description:
                    desc_kws = extract_query_keywords(de.description)
                    for dk in desc_kws:
                        if dk not in keywords and len(dk) >= 2:
                            keywords.append(dk)

        if faiss_idx and total_candidates > 0:
            # Vaultルートディレクトリの解決
            db_resolved = Path(self.db_path).resolve()
            vault_dir = db_resolved.parent.parent if db_resolved.parent.name == ".vector_search" else db_resolved.parent

            # 余裕を持ったTop-K件を取得し、キャリブレーションスコアリングを適用
            fetch_k = min(top_k * 4, total_candidates)
            raw_hits = faiss_idx.search(query_vec, top_k=fetch_k)

            if mode == SearchMode.DOCUMENT:
                for hit in raw_hits:
                    doc_id = hit["id"]
                    sim = hit["score"]
                    row = self._doc_rows_cache.get(doc_id)
                    if not row:
                        continue

                    # キャリブレーションスコア算出
                    calibrated_score = compute_calibrated_score(
                        dense_sim=sim,
                        keywords=keywords,
                        title=row.get("title") or "",
                        text=row.get("text") or "",
                        path=row.get("path") or "",
                        keyword_boost=keyword_boost,
                        boost_weight=boost_weight,
                    )

                    if min_score > 0.0 and calibrated_score < min_score:
                        continue

                    preview_text = (row["text"] or "")[:200]
                    if len(row["text"] or "") > 200:
                        preview_text += "..."

                    rel_path = row["path"]
                    full_p = str((vault_dir / rel_path).resolve())

                    results.append(
                        SearchResultItem(
                            document_id=row["id"],
                            path=rel_path,
                            title=row["title"] or Path(rel_path).name,
                            score=calibrated_score,
                            full_path=full_p,
                            preview=preview_text,
                        )
                    )

            elif mode == SearchMode.CHUNK:
                for hit in raw_hits:
                    chunk_id = hit["id"]
                    sim = hit["score"]
                    row = self._chunk_rows_cache.get(chunk_id)
                    if not row:
                        continue

                    chunk_text = row["text"] or ""

                    # キャリブレーションスコア算出
                    calibrated_score = compute_calibrated_score(
                        dense_sim=sim,
                        keywords=keywords,
                        title=row.get("title") or "",
                        text=chunk_text,
                        path=row.get("path") or "",
                        keyword_boost=keyword_boost,
                        boost_weight=boost_weight,
                    )

                    if min_score > 0.0 and calibrated_score < min_score:
                        continue

                    # 文脈情報取得
                    ctx = get_chunk_with_context(self.db_path, chunk_id=chunk_id)
                    
                    # 反応文の特定（レスポンス高速化のため上位3件のみに適用）
                    salient = None
                    if len(results) < 3:
                        salient = find_salient_sentence(
                            text=chunk_text,
                            query_vec=query_vec,
                            embedder=self.embedder,
                            min_sentence_score=0.55,
                        )

                    rel_path = row["path"]
                    full_p = str((vault_dir / rel_path).resolve())

                    results.append(
                        SearchResultItem(
                            document_id=row["document_id"],
                            path=rel_path,
                            title=row["title"] or Path(rel_path).name,
                            score=calibrated_score,
                            full_path=full_p,
                            chunk_id=chunk_id,
                            chunk_index=row["chunk_index"],
                            hit_text=chunk_text,
                            context=ctx,
                            salient_sentence=salient,
                        )
                    )

            # スコア降順にソートして top_k 件に制限
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[:top_k]

        t_sim_end = time.perf_counter()
        search_time_ms = round((t_sim_end - t_sim_start) * 1000, 2)
        total_time_ms = round((t_sim_end - t_total_start) * 1000, 2)

        # ハイブリッド検索用キーワードおよびLLM投入用RAGコンテキストの構築
        kw_query = " OR ".join(keywords) if keywords else query
        rag_xml, rag_md = generate_rag_contexts(results, query)

        # 専門用語情報の辞書化
        detected_terms_dicts = [
            {"term": e.term, "synonyms": e.synonyms, "description": e.description}
            for e in detected_entries
        ]

        return SearchResponse(
            query=query,
            mode=mode,
            results=results,
            total_candidates=total_candidates,
            query_embedding_time_ms=query_emb_time_ms,
            search_time_ms=search_time_ms,
            total_time_ms=total_time_ms,
            extracted_keywords=keywords,
            keyword_query=kw_query,
            rag_context_xml=rag_xml,
            rag_context_markdown=rag_md,
            detected_terms=detected_terms_dicts,
        )
