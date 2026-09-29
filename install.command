#!/bin/bash
# ============================================================
#  ECG Analyzer — 安裝程式
# ============================================================

osascript -e 'tell application "Terminal" to activate' 2>/dev/null

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        ECG Analyzer V5 安裝程式             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 找 python3 ──────────────────────────────────────────────
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ 找不到 Python 3！請先安裝 Python"
    echo "   https://www.python.org/downloads/"
    read -p "按 Enter 關閉..."
    exit 1
fi

PYTHON_PATH=$(command -v "$PYTHON")
PY_VER=$("$PYTHON" --version 2>&1)
echo "✅ 找到 Python：$PY_VER"
echo "   路徑：$PYTHON_PATH"
echo ""

# ── 安裝套件 ────────────────────────────────────────────────
PACKAGES=("PyQt6" "pyqtgraph" "numpy" "scipy" "pyabf" "bioread" "openpyxl")
echo "📦 開始安裝必要套件..."
echo ""

FAILED=()
for pkg in "${PACKAGES[@]}"; do
    echo -n "  安裝 $pkg ... "
    if "$PYTHON" -m pip install "$pkg" --quiet --upgrade 2>/dev/null; then
        echo "✅"
    else
        echo "❌"
        FAILED+=("$pkg")
    fi
done

echo ""
if [ ${#FAILED[@]} -ne 0 ]; then
    echo "⚠️  以下套件安裝失敗：${FAILED[*]}"
    read -p "按 Enter 關閉..."
    exit 1
fi

# ── 更新 Mac App ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PATH="$SCRIPT_DIR/ECG Analyzer.app"

if [ -d "$APP_PATH" ]; then
    echo "🔨 更新 ECG Analyzer.app ..."
    cp "$SCRIPT_DIR/ecg_app.py" "$APP_PATH/Contents/Resources/ecg_app.py"
    chmod 755 "$APP_PATH/Contents/MacOS/launcher"
    xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true
else
    echo "⚠️  找不到 ECG Analyzer.app，可改用「啟動 ECG Analyzer V5.command」開啟"
fi

if "$PYTHON" -m py_compile "$SCRIPT_DIR/ecg_app.py" 2>/dev/null; then
    echo "✅ 主程式語法正確"
else
    echo "⚠️  主程式語法有誤，請回報此問題"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           ✅ 安裝完成！                  ║"
echo "╠══════════════════════════════════════════╣"
echo "║  雙擊「ECG Analyzer.app」即可啟動 V5     ║"
echo "║  或將 .abf / .edf 檔案拖放到 App 圖示上  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

read -p "是否立即開啟 ECG Analyzer V5？(y/n) " yn
if [[ "$yn" == "y" || "$yn" == "Y" ]]; then
    open "$APP_PATH"
    echo "已啟動！"
fi
