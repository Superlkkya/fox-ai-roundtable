@echo off
cd /d %~dp0
pip install -q -r requirements.txt
start "" pythonw app.py
