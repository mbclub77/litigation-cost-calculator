import sys, os, threading, webbrowser, time, logging, subprocess
import tkinter as tk

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)
PORT = 5050
URL  = f'http://127.0.0.1:{PORT}'

# ── 상태 창 먼저 띄우기 ───────────────────────────────────────────────────────
root = tk.Tk()
root.title('인사관리시스템')
root.geometry('360x180')
root.resizable(False, False)
root.configure(bg='#1e2a4a')

lbl_status = tk.Label(root, text='시작 중…', bg='#1e2a4a', fg='#f6c23e',
                      font=('맑은 고딕', 11), wraplength=330, justify='center')
lbl_status.pack(pady=(24, 6))

lbl_sub = tk.Label(root, text='', bg='#1e2a4a', fg='#b8c7e0',
                   font=('맑은 고딕', 9), wraplength=330, justify='center')
lbl_sub.pack()

btn_frame = tk.Frame(root, bg='#1e2a4a')
btn_frame.pack(pady=14)

def set_status(msg, sub='', color='#f6c23e'):
    lbl_status.config(text=msg, fg=color)
    lbl_sub.config(text=sub)
    root.update()

def open_browser():
    webbrowser.open(URL)

def stop_app():
    os._exit(0)

flask_ready = threading.Event()
flask_error = []

def run_flask():
    try:
        # 필수 패키지 설치 확인
        try:
            import flask, flask_login
            from werkzeug.security import generate_password_hash
        except ImportError:
            root.after(0, set_status, '패키지 설치 중… (최초 1회)', '잠시 기다려 주세요.')
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'flask', 'flask-login', 'werkzeug', '-q'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        from app import app
        flask_ready.set()
        app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
    except OSError as e:
        if '5050' in str(e) or 'address already in use' in str(e).lower():
            flask_error.append('PORT_IN_USE')
        else:
            flask_error.append(str(e))
        flask_ready.set()
    except Exception as e:
        flask_error.append(str(e))
        flask_ready.set()

def after_flask_ready():
    if flask_error:
        err = flask_error[0]
        if err == 'PORT_IN_USE':
            set_status('이미 실행 중입니다!', f'{URL} 으로 바로 접속하세요.', '#1cc88a')
            webbrowser.open(URL)
        else:
            set_status('실행 오류', err[:120], '#e74a3b')
        tk.Button(btn_frame, text='브라우저 열기', bg='#4e73df', fg='white',
                  relief='flat', font=('맑은 고딕', 10), padx=14, pady=5,
                  cursor='hand2', command=open_browser).pack(side='left', padx=6)
    else:
        set_status('서버 실행 중  ●', URL, '#1cc88a')
        webbrowser.open(URL)
        tk.Button(btn_frame, text='브라우저 열기', bg='#4e73df', fg='white',
                  relief='flat', font=('맑은 고딕', 10), padx=14, pady=5,
                  cursor='hand2', command=open_browser).pack(side='left', padx=6)

    tk.Button(btn_frame, text='종료', bg='#e74a3b', fg='white',
              relief='flat', font=('맑은 고딕', 10), padx=14, pady=5,
              cursor='hand2', command=stop_app).pack(side='left', padx=6)

def poll_ready():
    if flask_ready.is_set():
        after_flask_ready()
    else:
        root.after(300, poll_ready)

t = threading.Thread(target=run_flask, daemon=True)
t.start()
root.after(300, poll_ready)
root.mainloop()
