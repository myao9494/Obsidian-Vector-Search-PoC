@echo off
@rem ==============================================================================
@rem Obsidian Vector Search PoC - Windows 起動スクリプト
@rem 文字コード対策: UTF-8 (65001) に設定し、CP932/Shift_JISでの文字化け・クラッシュを防止
@rem ==============================================================================
chcp 65001 > nul
setlocal enabledelayedexpansion

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ==============================================================================
echo   Obsidian Vector Search PoC を起動しています...
echo ==============================================================================

cd /d "%~dp0"

@rem 1. Python 実行環境の確認
set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    echo [OK] 仮想環境 .venv を使用します。
) else if exist "backend\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=backend\.venv\Scripts\python.exe"
    echo [OK] 仮想環境 backend\.venv を使用します。
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=python"
        echo [INFO] システムの Python を使用します。
    ) else (
        echo [エラー] Python が見つかりませんでした。Python 3.10以上をインストールしてください。
        pause
        exit /b 1
    )
)

@rem 2. PYTHONPATH の設定
set "PYTHONPATH=%~dp0backend"

@rem 3. ブラウザを開く
echo [INFO] Web UI (http://127.0.0.1:60000) をブラウザで開きます...
start "" "http://127.0.0.1:60000"

@rem 4. FastAPI サーバーの起動 (ポート 60000)
echo [INFO] サーバーを起動します (Port: 60000)...
echo [INFO] 終了するには Ctrl + C を押してください。
echo.

"%PYTHON_CMD%" -m uvicorn app.main:app --host 127.0.0.1 --port 60000

if %errorlevel% neq 0 (
    echo.
    echo [エラー] サーバーの起動に失敗しました。
    echo 依存パッケージが不足している場合は以下を実行してください:
    echo   pip install -r backend\requirements.txt
    echo.
    pause
)
