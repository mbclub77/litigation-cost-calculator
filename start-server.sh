#!/bin/bash
echo ""
echo " ============================================"
echo "  한국어 맞춤법 검사 서버 설치 및 시작"
echo " ============================================"
echo ""

# Python 확인
if ! command -v python3 &>/dev/null; then
    echo "[오류] Python3가 설치되어 있지 않습니다."
    echo "       brew install python3  (Mac)"
    echo "       sudo apt install python3-pip  (Ubuntu)"
    exit 1
fi

echo "[1/2] 필요한 패키지 설치 중..."
pip3 install flask flask-cors requests -q

echo "[2/2] 서버 시작 중..."
echo ""
echo " 맞춤법 검사기 HTML 파일을 열면 자동으로 연결됩니다."
echo " 종료: Ctrl+C"
echo ""
python3 "$(dirname "$0")/spellcheck-server.py"
