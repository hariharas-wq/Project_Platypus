@echo off
REM ===== Project Platypus / Team 56 - one-click Windows launcher =====
cd /d "%~dp0"

echo Installing dependencies...
py -m pip install --quiet flask google-generativeai python-docx pdfplumber requests

if not exist evidence.json (
    echo Building evidence base from GBIF + IUCN...
    py build_evidence.py
)

echo.
echo Starting the town hall server...
echo Open http://localhost:5000 in your browser.
echo Press Ctrl+C here to stop.
echo.
py server.py

pause
