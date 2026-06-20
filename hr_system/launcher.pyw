import sys, os, threading, webbrowser, time, logging
import tkinter as tk
from tkinter import font as tkfont

# Flask 경고 메시지 숨기기
logging.getLogger('werkzeug').setLevel(logging.ERROR)
os.environ['FLASK_ENV'] = 'production'

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

PORT = 5050
URL  = f'http://127.0.0.1:{PORT}'

def run_flask():
    from app import app
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)

# Flask 백그라운드 실행
t = threading.Thread(target=run_flask, daemon=True)
t.start()
time.sleep(1.5)
webbrowser.open(URL)

# ── 상태 창 (작은 컨트롤 패널) ───────────────────────────────────────────────
root = tk.Tk()
root.title('인사관리시스템')
root.geometry('320x140')
root.resizable(False, False)
root.configure(bg='#1e2a4a')
try:
    root.iconbitmap(default='')
except:
    pass

tk.Label(root, text='인사관리시스템', bg='#1e2a4a', fg='white',
         font=('맑은 고딕', 14, 'bold')).pack(pady=(18, 4))
tk.Label(root, text='서버 실행 중  ●', bg='#1e2a4a', fg='#1cc88a',
         font=('맑은 고딕', 10)).pack()

btn_frame = tk.Frame(root, bg='#1e2a4a')
btn_frame.pack(pady=12)

tk.Button(btn_frame, text='브라우저 열기',
          bg='#4e73df', fg='white', relief='flat',
          font=('맑은 고딕', 10), padx=14, pady=5,
          cursor='hand2',
          command=lambda: webbrowser.open(URL)).pack(side='left', padx=6)

tk.Button(btn_frame, text='종료',
          bg='#e74a3b', fg='white', relief='flat',
          font=('맑은 고딕', 10), padx=14, pady=5,
          cursor='hand2',
          command=lambda: os._exit(0)).pack(side='left', padx=6)

root.mainloop()
