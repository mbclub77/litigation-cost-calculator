#!/usr/bin/env python3
"""
한국어 맞춤법 검사 로컬 서버 — 부산대 맞춤법 검사기 API 중계

의존성 설치:
    pip install flask flask-cors requests

실행:
    python spellcheck-server.py

접속: http://127.0.0.1:5000
"""

import os
import sys
import time
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
CORS(app, origins=['*'])

PNU_URL    = 'https://speller.cs.pusan.ac.kr/results'
CHUNK_SIZE = 500   # PNU API 권장 최대 길이

ERROR_TYPE = {
    1: 'spell',    # 맞춤법
    2: 'spacing',  # 띄어쓰기
    3: 'spell',    # 표준어
    4: 'punct',    # 문장부호
    5: 'style',    # 문체
}


def pnu_check(text: str) -> list:
    """부산대 맞춤법 검사기 API 호출 (긴 텍스트 자동 분할)"""
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Referer': 'https://speller.cs.pusan.ac.kr/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Origin': 'https://speller.cs.pusan.ac.kr',
    }
    results = []
    offset  = 0

    for i in range(0, len(text), CHUNK_SIZE):
        chunk = text[i:i + CHUNK_SIZE]
        resp = requests.post(
            PNU_URL,
            data={'text1': chunk},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        for err in data.get('errInfo', []):
            start = err.get('start', 0) + offset
            end   = err.get('end',   0) + offset
            org   = err.get('orgStr',  '')
            cand  = err.get('candStr', '')
            if not org or org == cand:
                continue
            results.append({
                'pos':        start,
                'len':        max(end - start, len(org)),
                'original':   org,
                'correction': cand,
                'type':       ERROR_TYPE.get(err.get('errorIdx', 1), 'spell'),
                'reason':     err.get('help', '').replace('<br>', ' ').strip(),
            })
        offset += len(chunk)
        if i + CHUNK_SIZE < len(text):
            time.sleep(0.3)   # API 과부하 방지

    return results


# ── 엔드포인트 ────────────────────────────────────────────────────

@app.route('/')
def index():
    """HTML 파일을 서버에서 직접 서빙 (CORS 문제 방지)"""
    return send_from_directory(BASE_DIR, 'spellchecker-pro.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'engine': 'pnu'})


@app.route('/check', methods=['POST'])
def check():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'error': '텍스트가 없습니다.'})
    try:
        errors = pnu_check(text)
        return jsonify({'success': True, 'errors': errors})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': '인터넷 연결을 확인하세요.'}), 503
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'API 응답 시간 초과'}), 504
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── 실행 ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 55)
    print('  한국어 맞춤법 검사 서버 (부산대 API 중계)')
    print('  브라우저에서 아래 주소를 여세요:')
    print('  >>> http://127.0.0.1:5000 <<<')
    print('  종료 : Ctrl+C')
    print('=' * 55)
    try:
        app.run(host='127.0.0.1', port=5000, debug=False)
    except OSError as e:
        print(f'\n오류: {e}')
        print('이미 5000번 포트가 사용 중입니다. 기존 서버를 종료 후 재시작하세요.')
        sys.exit(1)
