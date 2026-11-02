@echo off
REM 打包成單一 exe（輸出在 dist\活動自動登錄.exe），campaigns.yaml 放在 exe 旁邊即可
cd /d %~dp0
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name 活動自動登錄 app.py
copy /Y campaigns.yaml dist\
echo 完成：dist\活動自動登錄.exe
pause
