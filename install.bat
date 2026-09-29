@echo off
if defined ECG_UTF8_DONE goto :main
set "ECG_UTF8_DONE=1"
chcp 65001 >nul
call "%~f0" %*
exit /b %errorlevel%

:main
REM ============================================================
REM  ECG Analyzer V5 — Windows 安裝程式
REM ============================================================
title ECG Analyzer V5 安裝程式
setlocal enabledelayedexpansion

echo.
echo ================================================
echo         ECG Analyzer V5 安裝程式 (Windows)
echo ================================================
echo.

set "DIR=%~dp0"

REM ── 尋找 Python ──────────────────────────────────────────────
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"

if "%PY%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set "PY=python"
)

if "%PY%"=="" (
    echo [錯誤] 找不到 Python！請先安裝 Python 3.10 以上版本
    echo         https://www.python.org/downloads/
    echo         安裝時務必勾選「Add python.exe to PATH」
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('%PY% --version 2^>^&1') do set "PYVER=%%V"
echo [OK] 找到 Python：%PYVER%
echo.

REM ── 安裝套件 ────────────────────────────────────────────────
echo 開始安裝必要套件（可能需要幾分鐘）...
echo.

%PY% -m pip install --upgrade pip --quiet

set "FAILED="
for %%M in (PyQt6 pyqtgraph numpy scipy pyabf bioread openpyxl) do (
    echo   安裝 %%M ...
    %PY% -m pip install %%M --quiet --upgrade
    if errorlevel 1 (
        echo   [失敗] %%M
        set "FAILED=1 !FAILED! %%M"
    ) else (
        echo   [OK] %%M
    )
)

echo.
if defined FAILED (
    echo [警告] 部分套件安裝失敗，請檢查網路連線，或手動執行：
    echo   %PY% -m pip install PyQt6 pyqtgraph numpy scipy pyabf bioread openpyxl
    echo.
    pause
    exit /b 1
)

REM ── 驗證套件可以正常載入（例如缺少 VC++ Redistributable 會在此被抓到）──
echo 驗證套件是否能正常載入...
%PY% -c "import PyQt6.QtWidgets, pyqtgraph, numpy, scipy, pyabf, bioread, openpyxl" 2>"%DIR%install_check.log"
if errorlevel 1 (
    echo.
    echo [警告] 套件安裝成功，但載入時發生錯誤：
    echo ------------------------------------------------------------
    type "%DIR%install_check.log"
    echo ------------------------------------------------------------
    echo 常見原因：缺少「Microsoft Visual C++ Redistributable」。
    echo 請至以下網址下載並安裝 x64 版本後，重新執行 install.bat：
    echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    pause
    exit /b 1
) else (
    echo [OK] 套件載入正常
    del "%DIR%install_check.log" >nul 2>nul
)
echo.

REM ── 建立桌面捷徑 ────────────────────────────────────────────
echo 建立桌面捷徑...

set "LAUNCHER=%DIR%啟動 ECG Analyzer V5.bat"
set "SHORTCUT=%USERPROFILE%\Desktop\ECG Analyzer V5.lnk"

powershell -NoProfile -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
    "$s.TargetPath = '%LAUNCHER%';" ^
    "$s.WorkingDirectory = '%DIR%';" ^
    "$s.IconLocation = '%SystemRoot%\System32\shell32.dll,220';" ^
    "$s.Description = 'ECG Analyzer V5';" ^
    "$s.Save()" >nul 2>nul

if exist "%SHORTCUT%" (
    echo [OK] 已在桌面建立「ECG Analyzer V5」捷徑
) else (
    echo [提示] 桌面捷徑建立失敗，可直接雙擊「啟動 ECG Analyzer V5.bat」開啟
)

echo.
echo ================================================
echo                安裝完成！
echo ------------------------------------------------
echo   雙擊桌面上的「ECG Analyzer V5」捷徑即可啟動
echo   或雙擊「啟動 ECG Analyzer V5.bat」
echo   也可將 .abf / .edf 檔案拖放到該檔案上直接開啟
echo ================================================
echo.

set /p RUNNOW=是否立即開啟 ECG Analyzer V5？(y/n)
if /i "%RUNNOW%"=="y" (
    call "%LAUNCHER%"
    echo 已啟動！
)

echo.
pause
