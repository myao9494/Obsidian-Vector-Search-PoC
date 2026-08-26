"""
専門用語・類似語辞書 (Glossary / Synonyms) 管理モジュール
仕様:
- Excel (.xlsx) および CSV (.csv) ファイルから用語・類似語・解説を読み込みインメモリ管理。
- 列名（日本語「専門用語」「類似語」「意味・解説」/ 英語「Term」「Synonyms」「Description」等）の自動判定。
- 大文字小文字、全角半角、ハイフン有無（PJX ⇔ PJ-X ⇔ ｐｊｘ）の表記揺れ正規化。
- 自然言語テキスト（質問文・ノート本文）からの最長一致用語検知。
- 自然言語クエリのEmbedding用セマンティック補強文字列の生成。
- チャンキング時における同義語・解説メタデータ抽出機能の提供。
"""

import csv
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def normalize_term_key(text: str) -> str:
    """
    表記揺れを吸収するための正規化キーを生成する。
    - 全角英数を半角に変換 (NFKC)
    - 小文字化
    - ハイフン・アンダースコア・スペースの除去
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = re.sub(r"[\s\-_ー−―]+", "", normalized)
    return normalized


@dataclass
class GlossaryEntry:
    """専門用語エントリ"""
    term: str
    synonyms: List[str] = field(default_factory=list)
    description: str = ""
    # 表記揺れキー群（termおよび全synonymsの正規化後キー）
    normalized_keys: Set[str] = field(default_factory=set)

    def all_variants(self) -> List[str]:
        """代表語およびすべての類似語を含む重複なしリスト"""
        res = [self.term]
        for s in self.synonyms:
            if s not in res:
                res.append(s)
        return res


class GlossaryDictionary:
    """専門用語・類似語辞書クラス"""

    def __init__(self, entries: Optional[List[GlossaryEntry]] = None, file_path: str = ""):
        self.entries: List[GlossaryEntry] = entries or []
        self.file_path: str = file_path
        self._key_to_entry: Dict[str, GlossaryEntry] = {}
        self._raw_terms_sorted_by_len: List[Tuple[str, GlossaryEntry]] = []
        self._build_index()

    def _build_index(self):
        """検索用インデックスの構築"""
        self._key_to_entry.clear()
        raw_list = []

        for entry in self.entries:
            # 代表語と類似語をすべて登録
            variants = entry.all_variants()
            for v in variants:
                if not v:
                    continue
                k = normalize_term_key(v)
                if k:
                    entry.normalized_keys.add(k)
                    self._key_to_entry[k] = entry
                raw_list.append((v, entry))

        # 最長一致検索用に文字列長の降順でソート
        self._raw_terms_sorted_by_len = sorted(raw_list, key=lambda x: len(x[0]), reverse=True)

    @classmethod
    def from_file(cls, file_path: str) -> "GlossaryDictionary":
        """
        Excel (.xlsx) または CSV (.csv) ファイルから辞書を生成する。
        """
        if not os.path.exists(file_path):
            return cls(entries=[], file_path=file_path)

        path_obj = Path(file_path)
        ext = path_obj.suffix.lower()

        if ext == ".xlsx":
            return cls._from_excel(file_path)
        elif ext in [".csv", ".tsv", ".txt"]:
            return cls._from_csv(file_path)
        else:
            return cls(entries=[], file_path=file_path)

    @classmethod
    def _from_excel(cls, file_path: str) -> "GlossaryDictionary":
        """Excelファイル (.xlsx) の読み込み"""
        import openpyxl

        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        if ws is None:
            return cls(entries=[], file_path=file_path)

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return cls(entries=[], file_path=file_path)

        # ヘッダー行の解析
        header_row = rows[0]
        term_idx, syn_idx, desc_idx = cls._resolve_column_indices(header_row)

        entries: List[GlossaryEntry] = []
        for row in rows[1:]:
            if not row:
                continue
            term_val = str(row[term_idx]).strip() if term_idx < len(row) and row[term_idx] is not None else ""
            if not term_val or term_val == "None":
                continue

            syn_val = str(row[syn_idx]).strip() if syn_idx < len(row) and row[syn_idx] is not None else ""
            desc_val = str(row[desc_idx]).strip() if desc_idx < len(row) and row[desc_idx] is not None else ""

            synonyms = cls._parse_synonyms(syn_val)
            entries.append(GlossaryEntry(
                term=term_val,
                synonyms=synonyms,
                description="" if desc_val == "None" else desc_val
            ))

        return cls(entries=entries, file_path=file_path)

    @classmethod
    def _from_csv(cls, file_path: str) -> "GlossaryDictionary":
        """CSVファイル (.csv) の読み込み"""
        entries: List[GlossaryEntry] = []
        with open(file_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
            if not rows:
                return cls(entries=[], file_path=file_path)

            header_row = rows[0]
            term_idx, syn_idx, desc_idx = cls._resolve_column_indices(header_row)

            for row in rows[1:]:
                if not row:
                    continue
                term_val = row[term_idx].strip() if term_idx < len(row) else ""
                if not term_val:
                    continue

                syn_val = row[syn_idx].strip() if syn_idx < len(row) else ""
                desc_val = row[desc_idx].strip() if desc_idx < len(row) else ""

                synonyms = cls._parse_synonyms(syn_val)
                entries.append(GlossaryEntry(
                    term=term_val,
                    synonyms=synonyms,
                    description=desc_val
                ))

        return cls(entries=entries, file_path=file_path)

    @staticmethod
    def _resolve_column_indices(header: List[Any]) -> Tuple[int, int, int]:
        """ヘッダー行から (Term, Synonyms, Description) の列インデックスを特定"""
        term_idx = 0
        syn_idx = 1
        desc_idx = 2

        for i, col in enumerate(header):
            if col is None:
                continue
            col_str = str(col).strip().lower()
            if any(k in col_str for k in ["専門用語", "代表語", "term", "単語", "用語"]):
                term_idx = i
            elif any(k in col_str for k in ["類似語", "同義語", "略称", "別名", "synonym", "alias"]):
                syn_idx = i
            elif any(k in col_str for k in ["意味", "解説", "説明", "description", "備考", "詳細"]):
                desc_idx = i

        return term_idx, syn_idx, desc_idx

    @staticmethod
    def _parse_synonyms(syn_str: str) -> List[str]:
        """カンマや読点区切りの類似語文字列をリストに分割"""
        if not syn_str or syn_str == "None":
            return []
        tokens = re.split(r"[,、，\n\t]+", syn_str)
        res = []
        for t in tokens:
            cleaned = t.strip().strip("'\"")
            if cleaned and cleaned not in res:
                res.append(cleaned)
        return res

    def find_by_term(self, term: str) -> Optional[GlossaryEntry]:
        """代表語または類似語からエントリを検索"""
        k = normalize_term_key(term)
        return self._key_to_entry.get(k)

    def detect_terms(self, text: str) -> List[GlossaryEntry]:
        """
        自然文テキストから登録されている専門用語・類似語を最長一致で検知する。
        """
        if not text or not self.entries:
            return []

        detected_entries: List[GlossaryEntry] = []
        seen_entry_ids = set()

        # 1. 生の文字列による直接検索（最長一致）
        for raw_word, entry in self._raw_terms_sorted_by_len:
            if len(raw_word) < 2:
                continue
            # 単語が含まれているか（大文字小文字無視）
            pattern = re.escape(raw_word)
            if re.search(pattern, text, re.IGNORECASE):
                entry_id = id(entry)
                if entry_id not in seen_entry_ids:
                    seen_entry_ids.add(entry_id)
                    detected_entries.append(entry)

        # 2. 表記揺れ（ハイフン有無・全角半角）を検知するための正規化検索
        normalized_text = normalize_term_key(text)
        for k, entry in self._key_to_entry.items():
            if len(k) >= 2 and k in normalized_text:
                entry_id = id(entry)
                if entry_id not in seen_entry_ids:
                    seen_entry_ids.add(entry_id)
                    detected_entries.append(entry)

        return detected_entries

    def build_enriched_query(self, query: str) -> str:
        """
        自然言語クエリに対して、検知された専門用語の類似語・解説を自然な形で補強した文字列を生成する。
        例:
        入力: "PJXのプロジェクトでの議事録ってどんなものがあったっけ"
        出力: "PJX (プロジェクトX, 基幹システム刷新 - 2024年発足の社内基幹システム刷新PJ) のプロジェクトでの議事録ってどんなものがあったっけ"
        """
        if not query or not self.entries:
            return query

        detected = self.detect_terms(query)
        if not detected:
            return query

        # 各用語の補足情報を構成
        supplements = []
        for entry in detected:
            parts = []
            # 代表語および同義語のうち、クエリに含まれていない関連語を追加
            for v in entry.all_variants():
                if v and v not in query:
                    parts.append(v)
            if entry.description:
                parts.append(entry.description)

            if parts:
                info_str = f"{entry.term} => {', '.join(parts[:4])}"
                supplements.append(info_str)

        if not supplements:
            return query

        # クエリ先頭に文脈コンテキスト [用語補足: ...] を付与してモデルに渡す
        context_header = f"[関連用語: {'; '.join(supplements)}]"
        return f"{context_header} {query}"

    def extract_enrichment_for_text(self, text: str) -> Tuple[List[str], List[str]]:
        """
        チャンク本文に含まれる用語から、メタデータヘッダーに注入すべき (aliases, context_notes) を抽出する。
        """
        if not text or not self.entries:
            return [], []

        detected = self.detect_terms(text)
        aliases: List[str] = []
        context_notes: List[str] = []

        for entry in detected:
            for v in entry.all_variants():
                if v and v not in aliases:
                    aliases.append(v)
            if entry.description and entry.description not in context_notes:
                context_notes.append(f"{entry.term}: {entry.description}")

        return aliases, context_notes
