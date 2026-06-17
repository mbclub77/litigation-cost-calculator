#!/bin/bash
echo ""
echo " ================================================"
echo "  Ollama 한국어 AI 맞춤법 검사 환경 설정"
echo " ================================================"
echo ""
echo "[1단계] Ollama 설치 중..."
curl -fsSL https://ollama.com/install.sh | sh
echo ""
echo "[2단계] 한국어 AI 모델 다운로드 (qwen2.5:7b, 약 4.7GB)"
echo "        시간이 걸립니다. 완료될 때까지 기다리세요."
echo ""
ollama pull qwen2.5:7b
echo ""
echo " ================================================"
echo "  설치 완료! spellchecker-pro.html 을 열면"
echo "  자동으로 AI 연결됩니다."
echo " ================================================"
