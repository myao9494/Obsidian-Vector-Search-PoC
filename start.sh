#!/usr/bin/env bash
# ==============================================================================
# Obsidian Vector Search PoC - macOS / Linux 起動スクリプト
# ==============================================================================
set -e

# プロジェクトルートディレクトリに移動
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONPATH="$DIR/backend"

echo "=============================================================================="
echo "  Obsidian Vector Search PoC を起動しています..."
echo "=============================================================================="

# 1. Python 実行環境の探索
PYTHON_CMD=""
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$DIR/.venv/bin/python"
    echo "[OK] 仮想環境 .venv を使用します。"
elif [ -f "$DIR/backend/.venv/bin/python" ]; then
    PYTHON_CMD="$DIR/backend/.venv/bin/python"
    echo "[OK] 仮想環境 backend/.venv を使用します。"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
    echo "[INFO] システムの python3 を使用します。"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
    echo "[INFO] システムの python を使用します。"
else
    echo "[エラー] Python が見つかりませんでした。Python 3.10以上をインストールしてください。"
    exit 1
fi

# 2. ブラウザを自動で開く
URL="http://127.0.0.1:60000"
echo "[INFO] Web UI ($URL) をブラウザで開きます..."
if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
fi

# 3. Uvicorn サーバーの起動
echo "[INFO] サーバーを起動します (Port: 60000)..."
echo "[INFO] 終了するには Ctrl + C を押してください。"
echo ""

exec "$PYTHON_CMD" -m uvicorn app.main:app --host 127.0.0.1 --port 60000
