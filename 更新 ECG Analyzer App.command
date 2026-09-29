#!/bin/bash
# 修改 ecg_app.py 之後，雙擊這個檔案，把最新程式放進 ECG Analyzer.app
DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$DIR/ecg_app.py"
updated=0
for APP in "$DIR/ECG Analyzer.app" "/Applications/ECG Analyzer.app" "$HOME/Applications/ECG Analyzer.app"; do
    if [ -d "$APP" ]; then
        cp "$SRC" "$APP/Contents/Resources/ecg_app.py" && echo "✅ 已更新：$APP" && updated=1
    fi
done
[ $updated -eq 0 ] && echo "❌ 找不到 ECG Analyzer.app"
sleep 2
