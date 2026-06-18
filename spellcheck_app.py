#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한국어 맞춤법 검사기
네이버 맞춤법 검사 엔진(py-hanspell) 기반 데스크탑 앱
"""

import sys, subprocess, threading, time, difflib
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# ── py-hanspell 자동 설치 ────────────────────────────────────────────────────
def _load_hanspell():
    try:
        from hanspell import spell_checker as sc
        return sc
    except ImportError:
        pass
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "py-hanspell", "-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        from hanspell import spell_checker as sc
        return sc
    except Exception as e:
        messagebox.showerror("설치 실패",
            f"py-hanspell 패키지 설치 실패:\n{e}\n\n"
            "터미널에서 직접 실행 후 재시도:\n  pip install py-hanspell")
        sys.exit(1)

spell_checker = _load_hanspell()

# ── 색상 ─────────────────────────────────────────────────────────────────────
C = dict(
    bg        = "#1a1b2e",
    surface   = "#252641",
    surface2  = "#2e2f50",
    text      = "#e8e8f4",
    muted     = "#7070a0",
    accent    = "#7c6af7",
    acc_hover = "#9b8cf5",
    del_      = "#ff6b9d",
    ins_      = "#50fa7b",
    border    = "#3a3b60",
    spell_c   = "#ff6b6b",
    space_c   = "#4ecdc4",
    gram_c    = "#ffe66d",
)

TYPE_NAME  = {0: "정상", 1: "맞춤법", 2: "띄어쓰기", 3: "표준어", 4: "교정"}
TYPE_COLOR = {1: C["spell_c"], 2: C["space_c"], 3: C["gram_c"], 4: C["gram_c"]}
CHUNK_SIZE = 500

# ── 유틸 ─────────────────────────────────────────────────────────────────────
def _sys_font(size, bold=False):
    weight = "bold" if bold else "normal"
    if sys.platform == "win32":
        return ("맑은 고딕", size, weight)
    elif sys.platform == "darwin":
        return ("Apple SD Gothic Neo", size, weight)
    return ("Noto Sans CJK KR", size, weight)


def _find_word_changes(original: str, corrected: str) -> list[tuple[str, str]]:
    """원문과 교정문의 단어 단위 차이 목록 반환."""
    o_words = original.split()
    c_words = corrected.split()
    changes = []
    matcher = difflib.SequenceMatcher(None, o_words, c_words, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "equal":
            o = " ".join(o_words[i1:i2])
            c = " ".join(c_words[j1:j2])
            if o or c:
                changes.append((o, c))
    return changes


# ── 메인 앱 ──────────────────────────────────────────────────────────────────
class SpellApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("한국어 맞춤법 검사기")
        self.geometry("980x740")
        self.minsize(700, 500)
        self.configure(bg=C["bg"])
        self._corrected = ""
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # 헤더
        hdr = tk.Frame(self, bg=C["surface"], pady=14)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="한국어 맞춤법 검사기",
                 bg=C["surface"], fg=C["text"],
                 font=_sys_font(17, bold=True)).pack(side=tk.LEFT, padx=24)
        tk.Label(hdr, text="네이버 맞춤법 검사 엔진  ·  인터넷 연결 필요",
                 bg=C["surface"], fg=C["muted"],
                 font=_sys_font(10)).pack(side=tk.LEFT, padx=4)

        # 범례
        legend = tk.Frame(self, bg=C["bg"], pady=6)
        legend.pack(fill=tk.X, padx=20)
        for label, color in [("삭제(원문)", C["del_"]), ("추가(교정)", C["ins_"])]:
            tk.Label(legend, text=f"  ■ {label}", bg=C["bg"], fg=color,
                     font=_sys_font(9)).pack(side=tk.LEFT)

        # 분할 패널
        paned = tk.PanedWindow(self, orient=tk.VERTICAL,
                               bg=C["bg"], sashwidth=6, sashpad=2)
        paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        # ── 입력 영역 ─────────────────────────────────────────────────────────
        top = tk.Frame(paned, bg=C["bg"])
        paned.add(top, minsize=160)

        tk.Label(top, text="입력 텍스트", bg=C["bg"], fg=C["muted"],
                 font=_sys_font(9)).pack(anchor=tk.W, pady=(8, 2))
        self.inp = scrolledtext.ScrolledText(
            top, bg=C["surface"], fg=C["text"], insertbackground=C["text"],
            font=_sys_font(12), relief=tk.FLAT, bd=0, wrap=tk.WORD,
            highlightbackground=C["border"], highlightthickness=1)
        self.inp.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(top, bg=C["bg"], pady=8)
        btn_row.pack(fill=tk.X)
        self.btn = tk.Button(btn_row, text="  맞춤법 검사  ",
            bg=C["accent"], fg="white", font=_sys_font(12, bold=True),
            relief=tk.FLAT, padx=8, pady=6, cursor="hand2",
            activebackground=C["acc_hover"], command=self._start_check)
        self.btn.pack(side=tk.LEFT)
        tk.Button(btn_row, text="지우기",
            bg=C["surface2"], fg=C["text"], font=_sys_font(11),
            relief=tk.FLAT, padx=14, pady=6, cursor="hand2",
            command=self._clear).pack(side=tk.LEFT, padx=8)
        self._status = tk.StringVar(value="텍스트를 입력하고 검사 버튼을 누르세요.")
        tk.Label(btn_row, textvariable=self._status, bg=C["bg"], fg=C["muted"],
                 font=_sys_font(10)).pack(side=tk.LEFT, padx=10)

        # ── 결과 영역 ─────────────────────────────────────────────────────────
        bot = tk.PanedWindow(paned, orient=tk.HORIZONTAL,
                             bg=C["bg"], sashwidth=6)
        paned.add(bot, minsize=200)

        # 좌: diff 뷰
        lf = tk.Frame(bot, bg=C["bg"])
        bot.add(lf, minsize=340)
        tk.Label(lf, text="교정 결과 (취소선=원문 / 밑줄=교정)",
                 bg=C["bg"], fg=C["muted"], font=_sys_font(9)).pack(anchor=tk.W, pady=(8, 2))
        self.res = scrolledtext.ScrolledText(
            lf, bg=C["surface"], fg=C["text"],
            font=_sys_font(12), relief=tk.FLAT, bd=0, wrap=tk.WORD,
            highlightbackground=C["border"], highlightthickness=1,
            state=tk.DISABLED)
        self.res.tag_config("del", foreground=C["del_"], overstrike=True)
        self.res.tag_config("ins", foreground=C["ins_"], underline=True)
        self.res.pack(fill=tk.BOTH, expand=True)
        tk.Button(lf, text="교정문 복사",
            bg=C["surface2"], fg=C["text"], font=_sys_font(10),
            relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
            command=self._copy).pack(anchor=tk.E, pady=6)

        # 우: 오류 목록
        rf = tk.Frame(bot, bg=C["bg"])
        bot.add(rf, minsize=220)
        tk.Label(rf, text="교정 목록",
                 bg=C["bg"], fg=C["muted"], font=_sys_font(9)).pack(anchor=tk.W, pady=(8, 2))

        cols = ("원문", "교정", "유형")
        self.tree = ttk.Treeview(rf, columns=cols, show="headings")
        self.tree.heading("원문",  text="원문")
        self.tree.heading("교정",  text="교정")
        self.tree.heading("유형",  text="유형")
        self.tree.column("원문",  width=140, anchor=tk.W)
        self.tree.column("교정",  width=140, anchor=tk.W)
        self.tree.column("유형",  width=80,  anchor=tk.CENTER)
        sb = ttk.Scrollbar(rf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Treeview",
            background=C["surface"], foreground=C["text"],
            fieldbackground=C["surface"], font=_sys_font(10), rowheight=26)
        st.configure("Treeview.Heading",
            background=C["surface2"], foreground=C["text"],
            font=_sys_font(10, bold=True))
        st.map("Treeview", background=[("selected", C["accent"])])
        for code, color in TYPE_COLOR.items():
            self.tree.tag_configure(str(code), foreground=color)

    # ── 이벤트 ───────────────────────────────────────────────────────────────
    def _clear(self):
        self.inp.delete("1.0", tk.END)
        self._set_diff("", "")
        for r in self.tree.get_children():
            self.tree.delete(r)
        self._status.set("텍스트를 입력하고 검사 버튼을 누르세요.")
        self._corrected = ""

    def _start_check(self):
        text = self.inp.get("1.0", tk.END).strip()
        if not text:
            self._status.set("텍스트를 입력해주세요.")
            return
        self.btn.config(state=tk.DISABLED, text="  검사 중…  ")
        self._status.set("네이버 서버에 연결 중…")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, text: str):
        try:
            corrected_parts, words_merged = [], {}
            for i in range(0, len(text), CHUNK_SIZE):
                chunk = text[i:i + CHUNK_SIZE]
                r = spell_checker.check(chunk)
                corrected_parts.append(r.checked)
                if hasattr(r, "words") and r.words:
                    words_merged.update(r.words)
                if i + CHUNK_SIZE < len(text):
                    time.sleep(0.3)
            corrected = "".join(corrected_parts)
            self.after(0, self._show, text, corrected, words_merged)
        except Exception as e:
            self.after(0, self._show_error, str(e))

    def _show(self, original: str, corrected: str, words: dict):
        self._corrected = corrected
        self._set_diff(original, corrected)

        for r in self.tree.get_children():
            self.tree.delete(r)

        # 오류 목록 — words dict의 에러 항목 + diff 단어 비교
        word_changes = _find_word_changes(original, corrected)
        for o, c in word_changes[:80]:
            # 에러 유형은 words dict에서 유추 (없으면 맞춤법으로 표시)
            code = words.get(o, 1) if words else 1
            if code == 0:
                code = 1
            type_name = TYPE_NAME.get(code, "맞춤법")
            self.tree.insert("", tk.END, values=(o or "(없음)", c or "(없음)", type_name),
                             tags=(str(code),))

        if original == corrected:
            self._status.set("✅ 맞춤법 오류가 없습니다!")
        else:
            n = len(word_changes)
            self._status.set(f"교정 완료 — {n}곳 변경됨")

        self.btn.config(state=tk.NORMAL, text="  맞춤법 검사  ")

    def _show_error(self, msg: str):
        self._status.set(f"오류: {msg}")
        self.btn.config(state=tk.NORMAL, text="  맞춤법 검사  ")
        messagebox.showerror("검사 오류",
            f"{msg}\n\n인터넷 연결을 확인하거나 잠시 후 다시 시도하세요.\n\n"
            "※ Naver 서버가 일시적으로 차단할 때는 10~30초 후 재시도하세요.")

    def _set_diff(self, original: str, corrected: str):
        self.res.config(state=tk.NORMAL)
        self.res.delete("1.0", tk.END)
        if not original and not corrected:
            self.res.config(state=tk.DISABLED)
            return
        matcher = difflib.SequenceMatcher(None, original, corrected, autojunk=False)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                self.res.insert(tk.END, original[i1:i2])
            elif op == "replace":
                self.res.insert(tk.END, original[i1:i2], "del")
                self.res.insert(tk.END, corrected[j1:j2], "ins")
            elif op == "delete":
                self.res.insert(tk.END, original[i1:i2], "del")
            elif op == "insert":
                self.res.insert(tk.END, corrected[j1:j2], "ins")
        self.res.config(state=tk.DISABLED)

    def _copy(self):
        if self._corrected:
            self.clipboard_clear()
            self.clipboard_append(self._corrected)
            self._status.set("교정문을 클립보드에 복사했습니다.")
        else:
            self._status.set("먼저 검사를 실행하세요.")


if __name__ == "__main__":
    app = SpellApp()
    app.mainloop()
