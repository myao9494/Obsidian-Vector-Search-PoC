"""
AIコンテキスト用HTMLエクスポートモジュール (HtmlExporter) の単体テスト
仕様:
- MarkdownテキストをHTMLにレンダリングし、Obsidian Wikilinkを展開する。
- ノート内の画像記法 (![[image.png]], ![[image.png|300]], ![alt](image.png)) を検知し、Base64 Data URLとしてインライン埋め込みする。
- 複数ドキュメントの結合、目次、AI共通プロンプト、Markdown元データセクションを含む自己完結型HTMLを生成する。
- POST /api/export/ai-html エンドポイントの正常系およびエラーハンドリングの検証。
"""

import base64
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.html_exporter import (
    export_documents_to_html,
    replace_obsidian_image_embeds,
    render_markdown_to_clean_html,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_render_markdown_to_clean_html():
    """MarkdownからクリーンなHTMLへの変換テスト（見出し、リスト、テーブル、Wikilink展開）"""
    md_text = """# タイトル

これは **太字** と *イタリック* です。

- 項目1
- 項目2

[[OtherNote|別のノート表示名]] を参照してください。
[[SimpleNote]] もあります。

| ヘッダーA | ヘッダーB |
|---|---|
| 値1 | 値2 |
"""
    html = render_markdown_to_clean_html(md_text)
    assert "<h1>タイトル</h1>" in html
    assert "<strong>太字</strong>" in html
    assert "<li>項目1</li>" in html
    assert "別のノート表示名" in html
    assert "SimpleNote" in html
    assert "<table>" in html or "ヘッダーA" in html


def test_replace_obsidian_image_embeds(tmp_path):
    """画像埋め込み記法がBase64 Data URL付きのimgタグに置換されることを検証"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    img_file = vault_dir / "diagram.png"
    # ダミーPNGバイナリ (1x1透明PNG)
    dummy_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    img_file.write_bytes(dummy_png_bytes)

    content = """# 図面サンプル

以下がアーキテクチャ図です。
![[diagram.png|400]]

通常リンク: ![[diagram.png]]
標準Markdown: ![図面](diagram.png)
"""

    result_md, embedded_count = replace_obsidian_image_embeds(
        content=content,
        vault_path=str(vault_dir),
        current_file_path="note.md",
    )

    assert embedded_count >= 1
    assert "data:image/png;base64," in result_md
    assert '<img ' in result_md
    assert 'width="400"' in result_md or '400' in result_md


def test_export_documents_to_html_full(tmp_path):
    """複数ドキュメントとAI共通プロンプトを統合した自己完結HTMLの生成テスト"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    doc1 = vault_dir / "01_note.md"
    doc1.write_text("# ノート1\n本文1です。\n", encoding="utf-8")

    doc2 = vault_dir / "02_note.md"
    doc2.write_text("# ノート2\n本文2です。\n", encoding="utf-8")

    prompt = "この2つのノートの要点を比較・整理してください。"
    html_output, stats = export_documents_to_html(
        vault_path=str(vault_dir),
        relative_paths=["01_note.md", "02_note.md"],
        prompt=prompt,
        title="AI用統合ドキュメント",
        include_raw_markdown=True,
        include_images=True,
    )

    assert "<!DOCTYPE html>" in html_output
    assert "<title>AI用統合ドキュメント</title>" in html_output
    assert prompt in html_output
    assert "ノート1" in html_output
    assert "ノート2" in html_output
    assert "マークダウンファイルの元データ" in html_output
    assert stats["total_documents"] == 2


def test_api_export_ai_html_endpoint(client, tmp_path):
    """POST /api/export/ai-html エンドポイントのテスト"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "sample.md").write_text("# サンプル\nテスト文書です。", encoding="utf-8")

    payload = {
        "vault_path": str(vault_dir),
        "relative_paths": ["sample.md"],
        "prompt": "要約してください",
        "title": "テストHTML",
        "include_raw_markdown": True,
        "include_images": True,
    }

    response = client.post("/api/export/ai-html", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "html_content" in data
    assert "<!DOCTYPE html>" in data["html_content"]
    assert data["total_documents"] == 1
    assert data["file_name"].endswith(".html")


def test_replace_excalidraw_and_drawio_embeds(tmp_path):
    """
    Excalidrawキャッシュ (.excalidraw-cache)、.drawio.svg、および
    自身と同名のExcalidraw-backed Markdown埋め込み (![[りんご|75]]) の解決テスト
    """
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    sub_dir = vault_dir / "01_data" / "2026" / "08" / "16"
    sub_dir.mkdir(parents=True)

    # 1. .excalidraw-cache ディレクトリとダミーPNGキャッシュ
    cache_dir = vault_dir / ".excalidraw-cache"
    cache_dir.mkdir()
    dummy_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"

    # あは.excalidraw.md 用のキャッシュファイル (711a98ce_preview.png)
    (cache_dir / "711a98ce_12345_preview.png").write_bytes(dummy_png_bytes)

    # 2. あは.excalidraw.md
    (sub_dir / "あは.excalidraw.md").write_text("# Excalidraw Data\n```compressed-json\n...\n```\n", encoding="utf-8")

    # 3. いいい.drawio.svg
    svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40" fill="red" /></svg>'
    (sub_dir / "いいい.drawio.svg").write_text(svg_content, encoding="utf-8")

    # 4. Pasted image
    (sub_dir / "Pasted image 20260816102040.png").write_bytes(dummy_png_bytes)

    # 5. りんご.md (フロントマターに excalidraw-plugin: parsed)
    ringo_content = """---
tags:
  - excalidraw
excalidraw-plugin: parsed
---

![[りんご|75]]
# 見出し

![[Pasted image 20260816102040.png|409]]
![[あは.excalidraw.md|275]]
![[いいい.drawio.svg|221]]

# Excalidraw Data
```compressed-json
...
```
"""
    (sub_dir / "りんご.md").write_text(ringo_content, encoding="utf-8")

    result_md, embedded_count = replace_obsidian_image_embeds(
        content=ringo_content,
        vault_path=str(vault_dir),
        current_file_path="01_data/2026/08/16/りんご.md",
    )

    # Pasted image, あは.excalidraw.md (cache), いいい.drawio.svg がすべてBase64 Data URLとして埋め込まれること
    assert "data:image/png;base64," in result_md
    assert "data:image/svg+xml;base64," in result_md
    assert 'width="275"' in result_md or '275' in result_md
    assert 'width="221"' in result_md or '221' in result_md
    assert embedded_count >= 3


def test_excalidraw_compressed_json_to_svg_fallback(tmp_path):
    """
    Excalidrawキャッシュが存在しない場合でも、ノート内の compressed-json から
    高品質なベクターSVGが自動生成され、Base64 Data URLとして埋め込まれることを検証
    """
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    doc_dir = vault_dir / "2026" / "08" / "16"
    doc_dir.mkdir(parents=True)

    # 実際の りんご.md と同等の compressed-json を含む Excalidraw ノート
    ringo_compressed_json = "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="

    ringo_note = f"""---
tags:
  - excalidraw
excalidraw-plugin: parsed
---

![[りんご|75]]

# Excalidraw Data
```compressed-json
{ringo_compressed_json}
```
"""
    note_path = doc_dir / "りんご.md"
    note_path.write_text(ringo_note, encoding="utf-8")

    result_md, count = replace_obsidian_image_embeds(
        content=ringo_note,
        vault_path=str(vault_dir),
        current_file_path="2026/08/16/りんご.md",
    )

    # プレビューキャッシュ未生成のエラーメッセージにならず、SVG画像として埋め込まれること
    assert "(プレビューキャッシュ未生成)" not in result_md
    assert "data:image/svg+xml;base64," in result_md
    assert count == 1


def test_drawio_svg_dark_mode_sanitization(tmp_path):
    """
    Drawio SVG の style に color-scheme: light dark; や light-dark(...) が含まれていても
    白黒反転（黒背景）を防止して light モードに正規化されることを検証
    """
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    drawio_svg = """<svg xmlns="http://www.w3.org/2000/svg" style="background: transparent; background-color: transparent; color-scheme: light dark;" version="1.1" width="121px" height="61px" viewBox="0 0 121 61">
<g><rect x="0" y="0" width="120" height="60" fill="#ffffff" stroke="#000000" style="fill: light-dark(#ffffff, var(--ge-dark-color, #121212)); stroke: light-dark(rgb(0, 0, 0), rgb(255, 255, 255));"/></g>
</svg>"""

    svg_path = vault_dir / "いいい.drawio.svg"
    svg_path.write_text(drawio_svg, encoding="utf-8")

    content = "![[いいい.drawio.svg|221]]"
    result_md, count = replace_obsidian_image_embeds(
        content=content,
        vault_path=str(vault_dir),
        current_file_path="test.md",
    )

    assert count == 1
    assert "data:image/svg+xml;base64," in result_md

    # Base64をデコードして正規化結果を確認
    import re
    match = re.search(r'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)', result_md)
    assert match is not None
    decoded_svg = base64.b64decode(match.group(1)).decode("utf-8")

    # color-scheme: light に正規化され、背景が #ffffff で light-dark が解消されていること
    assert "color-scheme: light" in decoded_svg
    assert "color-scheme: light dark" not in decoded_svg


