@echo off
if defined ECG_UTF8_DONE goto :main
set "ECG_UTF8_DONE=1"
chcp 65001 >nul
call "%~f0" %*
exit /b %errorlevel%

:main
REM ============================================================
REM  ECG Analyzer V5 - Windows 安裝程式
REM  注意：本檔必須是 CRLF 換行（.gitattributes 已設定），
REM        若用 LF 換行，cmd 會找不到 :main 等標籤而無法執行。
REM ============================================================
title ECG Analyzer V5 安裝程式
setlocal enabledelayedexpansion

echo.
echo ================================================
echo         ECG Analyzer V5 安裝程式 (Windows)
echo ================================================
echo.

set "DIR=%~dp0"
set "LOGF=%DIR%install_log.txt"
REM  檢查用的程式碼刻意不含引號，放進 for /f 才不會被 cmd 拆錯
set "CHK=import sys, struct; v=sys.version_info; print(v[0], v[1], v[2], struct.calcsize(chr(80))*8)"

REM ── 尋找可用的 Python ──────────────────────────────────────────
REM  依序嘗試 py -3、python。Microsoft Store 的「python」只是開啟商店的
REM  捷徑（WindowsApps 資料夾），執行不了程式，要排除。
set "PY="
set "PYINFO="
for %%X in ("py -3" "python") do (
    if not defined PY (
        for /f "tokens=1-4" %%A in ('%%~X -c "!CHK!" 2^>nul') do (
            set "PY=%%~X"
            set "PYMAJ=%%A"
            set "PYMIN=%%B"
            set "PYVER=%%A.%%B.%%C"
            set "PYBITS=%%D"
        )
    )
)

if not defined PY (
    echo [錯誤] 找不到可以執行的 Python。
    echo.
    echo   請到 https://www.python.org/downloads/ 下載 Python 3.10 以上（64 位元），
    echo   安裝時務必勾選「Add python.exe to PATH」，裝好後重新執行 install.bat。
    echo.
    echo   若已安裝卻仍出現此訊息：Windows 設定 → 應用程式 → 進階應用程式設定
    echo   → 應用程式執行別名，把「python.exe」「python3.exe」兩項關閉。
    echo.
    pause
    exit /b 1
)

echo [OK] 找到 Python %PYVER%（%PYBITS% 位元），指令：%PY%

if not "%PYBITS%"=="64" (
    echo.
    echo [錯誤] 這是 32 位元的 Python，PyQt6 只支援 64 位元。
    echo        請到 https://www.python.org/downloads/ 下載「Windows installer ^(64-bit^)」。
    echo.
    pause
    exit /b 1
)

if %PYMAJ% LSS 3 goto :oldpy
if %PYMAJ% EQU 3 if %PYMIN% LSS 9 goto :oldpy
goto :pyok
:oldpy
echo.
echo [錯誤] Python %PYVER% 太舊，請安裝 Python 3.10 以上（64 位元）。
echo.
pause
exit /b 1
:pyok
echo.

REM ── 安裝套件（完整輸出存到 install_log.txt）──────────────────────
echo 開始安裝必要套件（第一次約需 2～5 分鐘）...
echo   完整記錄：%LOGF%
echo.

%PY% -m pip install --upgrade pip > "%LOGF%" 2>&1
%PY% -m pip install --upgrade -r "%DIR%requirements.txt" >> "%LOGF%" 2>&1
if errorlevel 1 (
    echo [錯誤] 套件安裝失敗，最後的錯誤訊息：
    echo ------------------------------------------------------------
    powershell -NoProfile -Command "Get-Content -LiteralPath '%LOGF%' -Tail 25"
    echo ------------------------------------------------------------
    echo 常見原因：沒有網路、公司或學校網路擋住 pip、Python 版本太新還沒有對應的套件。
    echo 請把上面的訊息（或 install_log.txt）截圖回報。
    echo.
    pause
    exit /b 1
)
echo [OK] 套件安裝完成
echo.

REM ── 驗證套件可以正常載入（例如缺少 VC++ Redistributable 會在此被抓到）──
echo 驗證套件是否能正常載入...
%PY% -c "import PyQt6.QtWidgets, pyqtgraph, numpy, scipy, pyabf, bioread, openpyxl" 2>"%DIR%install_check.log"
if errorlevel 1 (
    echo.
    echo [錯誤] 套件安裝成功，但載入時發生錯誤：
    echo ------------------------------------------------------------
    type "%DIR%install_check.log"
    echo ------------------------------------------------------------
    echo 常見原因：缺少「Microsoft Visual C++ Redistributable」。
    echo 請至以下網址下載並安裝 x64 版本後，重新執行 install.bat：
    echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    pause
    exit /b 1
)
echo [OK] 套件載入正常
del "%DIR%install_check.log" >nul 2>nul
echo.

REM ── 建立桌面捷徑 ────────────────────────────────────────────
echo 建立桌面捷徑...

set "LAUNCHER=%DIR%啟動 ECG Analyzer V5.bat"

REM  圖示與 macOS 版相同（ECG Analyzer.ico）。先複製到本機的
REM  %LOCALAPPDATA%\ECG Analyzer\ 再給捷徑用：程式資料夾若在網路位置
REM  （例如 Parallels 的 C:\Mac\Home\…），桌面捷徑常讀不到那裡的圖示，
REM  會顯示成空白頁。找不到 .ico 時才用系統內建圖示。
set "ICON_SRC=%DIR%ECG Analyzer.ico"
set "ICON_DIR=%LOCALAPPDATA%\ECG Analyzer"
set "ICON=%SystemRoot%\System32\shell32.dll"
set "ICON_IDX=220"
if exist "%ICON_SRC%" (
    if not exist "%ICON_DIR%" mkdir "%ICON_DIR%" >nul 2>nul
    copy /y "%ICON_SRC%" "%ICON_DIR%\ECG Analyzer.ico" >nul 2>nul
    if exist "%ICON_DIR%\ECG Analyzer.ico" (
        set "ICON=%ICON_DIR%\ECG Analyzer.ico"
        set "ICON_IDX=0"
    )
)

REM  路徑改用環境變數交給 PowerShell：直接寫進命令列時，中文或特殊字元
REM  在 UTF-8 命令列下可能被轉壞
set "ECG_LNK_TARGET=%LAUNCHER%"
set "ECG_LNK_DIR=%DIR%"
set "ECG_LNK_ICON=%ICON%,%ICON_IDX%"

powershell -NoProfile -Command ^
    "$d = [Environment]::GetFolderPath('Desktop');" ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'ECG Analyzer V5.lnk'));" ^
    "$s.TargetPath = $env:ECG_LNK_TARGET;" ^
    "$s.WorkingDirectory = $env:ECG_LNK_DIR;" ^
    "$s.IconLocation = $env:ECG_LNK_ICON;" ^
    "$s.Description = 'ECG Analyzer V5';" ^
    "$s.Save()" >nul 2>nul
set "LNK_ERR=%errorlevel%"

REM  重新整理 Windows 的圖示快取，否則捷徑可能還顯示舊圖示
ie4uinit.exe -show >nul 2>nul

if not "%LNK_ERR%"=="0" (
    echo [提示] 桌面捷徑建立失敗，可直接雙擊「啟動 ECG Analyzer V5.bat」開啟
) else (
    echo [OK] 已在桌面建立「ECG Analyzer V5」捷徑
)

echo.
echo ================================================
echo                安裝完成！
echo ------------------------------------------------
echo   雙擊桌面上的「ECG Analyzer V5」捷徑即可啟動
echo   或雙擊「啟動 ECG Analyzer V5.bat」
echo   也可將 .abf / .edf / .acq 檔案拖放到該檔案上直接開啟
echo ================================================
echo.

set /p RUNNOW=是否立即開啟 ECG Analyzer V5？(y/n)
if /i "%RUNNOW%"=="y" (
    start "" "%LAUNCHER%"
    echo 已啟動！
)

echo.
pause
