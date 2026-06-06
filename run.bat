@echo off
echo Starting Cerdas Merata v2.0 (SQLite demo mode)...
set USE_SQLITE=1
set FLASK_DEBUG=1
set ADMIN_PASS=admin123
python app.py
pause
