#!/bin/bash
# ECG Analyzer V4 啟動器
# 支援 .abf 和 .edf 格式
# 雙擊此檔案即可開啟（不需要 .app）

DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$DIR/ecg_app.py"

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display alert "找不到 Python" message "請先執行 install.command 安裝。"'
    exit 1
fi

exec "$PYTHON" "$SCRIPT" "$@"
