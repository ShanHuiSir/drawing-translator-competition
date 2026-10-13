@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist python\python.exe (
  python\python.exe run_app.py
) else if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe run_app.py
) else (
  echo 请先运行 scripts\install_windows.bat，或使用 Windows 免安装版。
  pause
)
