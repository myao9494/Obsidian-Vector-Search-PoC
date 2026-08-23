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

# 2. ポート 60000 を使用中の既存プロセスがあれば自動終了
PORT=60000
OLD_PIDS=""
if command -v lsof >/dev/null 2>&1; then
    OLD_PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
fi

if [ -n "$OLD_PIDS" ]; then
    echo "[INFO] ポート $PORT を使用中の既存プロセス (PID: $OLD_PIDS) を検知しました。終了して再起動します..."
    for pid in $OLD_PIDS; do
        kill -9 "$pid" 2>/dev/null || true
    done
    sleep 0.5
fi

# 3. ブラウザを自動で開く
URL="http://127.0.0.1:$PORT"
echo "[INFO] Web UI ($URL) をブラウザで開きます..."
if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
fi

# 4. Uvicorn サーバーの起動
echo "[INFO] サーバーを起動します (Port: $PORT)..."
echo "[INFO] 終了するには Ctrl + C を押してください。"
echo ""

exec "$PYTHON_CMD" -m uvicorn app.main:app --host 127.0.0.1 --port $PORT
