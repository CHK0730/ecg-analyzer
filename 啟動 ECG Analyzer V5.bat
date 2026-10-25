@echo off
if defined ECG_UTF8_DONE goto :main
set "ECG_UTF8_DONE=1"
chcp 65001 >nul
call "%~f0" %*
exit /b %errorlevel%

:main
REM ============================================================
REM  ECG Analyzer V5 啟動器 (Windows)
REM  支援 .abf / .edf / .acq 格式
REM  雙擊此檔案即可開啟；也可將檔案拖放到此檔案上開啟
REM  注意：本檔必須是 CRLF 換行（.gitattributes 已設定）。
REM ============================================================
setlocal enabledelayedexpansion

set "DIR=%~dp0"
set "SCRIPT=%DIR%ecg_app.py"
set "LOG=%DIR%ecg_last_run.log"

if not exist "%SCRIPT%" (
    echo [錯誤] 找不到 ecg_app.py，請確認此檔案與主程式在同一資料夾。
    pause
    exit /b 1
)

REM ── 問 Python 自己的完整路徑（sys.executable）──
REM  不用 where python：它可能先找到 Microsoft Store 的 python 捷徑
REM  （WindowsApps 資料夾），那個只會開啟商店，程式根本跑不起來。
set "PYPATH="
for %%C in ("py -3" "python") do (
    if not defined PYPATH (
        for /f "delims=" %%I in ('%%~C -c "import sys; print(sys.executable)" 2^>nul') do (
            if not defined PYPATH set "PYPATH=%%I"
        )
    )
)

if not defined PYPATH (
    echo [錯誤] 找不到可以執行的 Python，請先雙擊 install.bat 進行安裝。
    pause
    exit /b 1
)

REM ── 找同資料夾下的 pythonw.exe（沒有終端機視窗），找不到就用 python.exe ──
for %%F in ("%PYPATH%") do set "PYDIR=%%~dpF"
set "PYW=%PYDIR%pythonw.exe"

if exist "%PYW%" (
    set "RUNNER=%PYW%"
) else (
    set "RUNNER=%PYPATH%"
)

REM ── 啟動主程式；輸出／錯誤導入紀錄檔，方便除錯 ──
"%RUNNER%" "%SCRIPT%" %* 1>"%LOG%" 2>&1

REM ── 若啟動失敗（非正常關閉），顯示錯誤內容 ──
if errorlevel 1 (
    echo.
    echo [錯誤] ECG Analyzer V5 啟動失敗，錯誤訊息如下：
    echo ------------------------------------------------------------
    type "%LOG%"
    echo ------------------------------------------------------------
    echo 完整紀錄已儲存於：%LOG%
    echo 若訊息是 No module named ...，請先雙擊 install.bat 安裝套件。
    echo.
    pause
    start "" notepad "%LOG%"
)
