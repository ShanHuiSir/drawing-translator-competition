@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
py -3.12 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install --no-deps -e .
if errorlevel 1 goto fail
echo 安装完成，请运行“启动图译.bat”。
pause
exit /b 0
:fail
echo 安装失败，请确认已安装 Python 3.12，并检查网络及上方错误。
pause
exit /b 1
