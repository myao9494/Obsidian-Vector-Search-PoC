"""
OS ネイティブフォルダ選択ダイアログモジュール
仕様:
- 実行環境のOS（macOS / Windows / Linux）に応じたネイティブのフォルダ選択ダイアログを表示する。
- ユーザーが選択したディレクトリの絶対パス文字列を返す。
- キャンセル時や失敗時は None を返す。
"""

import os
import platform
import subprocess
import sys
from typing import Optional


def open_folder_dialog(title: str = "フォルダを選択してください") -> Optional[str]:
    """
    OSネイティブのフォルダ選択ダイアログを開き、選択されたフォルダの絶対パスを返す。
    """
    current_os = platform.system()

    if current_os == "Darwin":  # macOS
        apple_script = f'''
        tell application "System Events"
            activate
            try
                set folderPath to choose folder with prompt "{title}"
                return POSIX path of folderPath
            on error
                return ""
            end try
        end tell
        '''
        try:
            res = subprocess.run(
                ["osascript", "-e", apple_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            selected = res.stdout.strip()
            return selected if selected else None
        except Exception:
            return None

    elif current_os == "Windows":  # Windows
        ps_script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $f = New-Object System.Windows.Forms.FolderBrowserDialog
        $f.Description = "{title}"
        $f.ShowNewFolderButton = $false
        if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
            Write-Output $f.SelectedPath
        }}
        '''
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            selected = res.stdout.strip()
            return selected if selected else None
        except Exception:
            return None

    # Linux等のフォールバック
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=title)
        root.destroy()
        return selected if selected else None
    except Exception:
        return None
