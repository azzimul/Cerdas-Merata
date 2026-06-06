@echo off
echo Starting Cerdas Merata (SQLite demo mode)...
set USE_SQLITE=1
set FLASK_DEBUG=1
python app.py
pause
