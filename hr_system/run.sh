#!/bin/bash
echo ""
echo " ================================================"
echo "  HR Management System for Labor Attorneys"
echo " ================================================"
echo ""

if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 not found. Install: brew install python3 (Mac)"
    exit 1
fi

echo "[1/2] Installing dependencies..."
pip3 install flask flask-cors -q

echo "[2/2] Starting server..."
echo "  Open: http://127.0.0.1:5050"
echo "  Stop: Ctrl+C"
echo ""
(sleep 2 && open "http://127.0.0.1:5050" 2>/dev/null || xdg-open "http://127.0.0.1:5050" 2>/dev/null) &
python3 "$(dirname "$0")/app.py"
