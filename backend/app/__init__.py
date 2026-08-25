"""
Obsidian Vector Search PoC - アプリケーションパッケージ
仕様:
- macOS / Windows 環境での OpenMP / PyTorch / FAISS の多重初期化エラーを防ぐ。
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    import torch
except ImportError:
    pass
