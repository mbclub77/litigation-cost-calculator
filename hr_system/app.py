#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, make_response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, init_db, calc_annual_leave, calc_work_hours
from datetime import datetime, date, timedelta
import os, traceback, logging, json
import calendar as cal_module

logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error.log'),
    level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s'
)

_BASE = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(_BASE, 'static', 'photos')
os.makedirs(PHOTO_DIR, exist_ok=True)

def _find_folder(name, marker):
    sub = os.path.join(_BASE, name)
    if os.path.isfile(os.path.join(sub, marker)): return sub
    if os.path.isfile(os.path.join(_BASE, marker)): return _BASE
    return sub

app = Flask(__name__,
    template_folder=_find_folder('templates', 'dashboard.html'),
    static_folder=_find_folder('static', 'style.css'))
app.secret_key = 'hr-system-secret-2024'

# ── Flask-Login ───────────────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'
login_manager.login_message = '로그인이 필요합니다.'

class User(UserMixin):
    def __init__(self, row):
        self.id          = row['id']
        self.username    = row['username']
        self.role        = row['role']
        self.company_id  = row['company_id']
        self.name        = row['name'] or row['username']
        self.employee_id = row['employee_id'] if 'employee_id' in row.keys() else None

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_employee(self):
        return self.role == 'employee'

    @property
    def is_company(self):
        return self.role == 'company'

@login_manager.user_loader
def load_user(uid):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return User(row) if row else None

@app.context_processor
def inject_globals():
    def get_active_cat():
        ep = request.endpoint or ''
        if ep in ['employees','employee_add','employee_edit','employee_delete','companies',
                  'company_add','company_edit','company_delete','users','user_add',
                  'user_delete','user_reset_pw']:
            return 'hr'
        if ep in ['attendance','attendance_add','attendance_bulk_add','attendance_delete',
                  'leave','leave_add','leave_delete','calendar_view','checkin']:
            return 'attendance'
        if ep in ['trip','trip_add','trip_delete','trip_status']:
            return 'trip'
        if ep in ['salary','salary_add','salary_edit','salary_delete','salary_json',
                  'salary_settings','allowance_add','allowance_delete',
                  'deduction_add','deduction_delete','api_allowance_master',
                  'salary_severance','severance_calc','severance_delete']:
            return 'salary'
        if ep in ['welfare','welfare_add','welfare_delete']:
            return 'welfare'
        if ep in ['education','education_add','education_delete','education_status']:
            return 'education'
        if ep in ['performance','performance_add','performance_delete','performance_score']:
            return 'performance'
        if ep in ['grievance','grievance_add','grievance_delete','grievance_respond']:
            return 'grievance'
        if ep in ['notices','notice_add','notice_delete','consultation']:
            return 'notices'
        return 'home'
    return {'now': datetime.now(), 'today_str': date.today().isoformat(),
            'active_cat': get_active_cat()}

@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    logging.error(tb)
    return f"<pre style='color:red;padding:20px'><b>오류:</b>\n{tb}</pre>", 500

@app.before_request
def setup():
    init_db()
    if current_user.is_authenticated:
        if current_user.is_employee:
            session['company_id'] = current_user.company_id
        elif not current_user.is_admin:
            session['company_id'] = current_user.company_id

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def _cid_filter():
    """현재 사용자의 회사 ID 필터를 반환한다."""
    if current_user.is_authenticated and not current_user.is_admin:
        return current_user.company_id
    return session.get('company_id')

def _eid_filter():
    """직원 역할이거나 관리자가 직원 뷰 중일 때 employee_id를 반환한다."""
    if current_user.is_authenticated and current_user.is_employee:
        return current_user.employee_id
    if current_user.is_authenticated and current_user.is_admin:
        return session.get('view_employee_id')
    return None

def selected_company():
    cid = _cid_filter()
    if not cid: return None
    db = get_db()
    c = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
    db.close()
    return c

def all_companies():
    db = get_db()
    if current_user.is_authenticated and not current_user.is_admin:
        rows = db.execute("SELECT * FROM companies WHERE id=?", (current_user.company_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM companies ORDER BY name").fetchall()
    db.close()
    return rows

# ── API 엔드포인트 ─────────────────────────────────────────────────────────────
@app.route('/api/companies')
def api_companies():
    db = get_db()
    rows = db.execute("SELECT id, name FROM companies ORDER BY name").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/employees/<int:cid>')
def api_employees(cid):
    db = get_db()
    rows = db.execute(
        "SELECT id, name, emp_no, dept FROM employees WHERE company_id=? AND status='재직' ORDER BY name",
        (cid,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── 로그인 / 로그아웃 ─────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        db = get_db()
        row = db.execute(
            "SELECT * FROM users WHERE username=?",
            (request.form.get('username', '').strip(),)).fetchone()
        db.close()
        if row and check_password_hash(row['password_hash'], request.form.get('password', '')):
            user = User(row)
            login_user(user, remember=True)
            if not user.is_admin:
                session['company_id'] = user.company_id
            return redirect(url_for('dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    """공개 회원가입 — company/employee 역할만 허용 (admin 불가)"""
    f = request.form
    username = f.get('username', '').strip()
    password = f.get('password', '').strip()
    role     = f.get('role', 'company')
    name     = f.get('name', '').strip()

    if role == 'admin':
        flash('관리자 계정은 직접 등록할 수 없습니다.')
        return redirect(url_for('login_page'))
    if not username or not password or len(password) < 4:
        flash('아이디와 비밀번호(4자 이상)를 입력하세요.')
        return redirect(url_for('login_page'))

    company_id  = f.get('company_id') or None
    employee_id = f.get('employee_id') or None

    if role == 'employee' and not employee_id:
        flash('직원 역할은 직원을 선택해야 합니다.')
        return redirect(url_for('login_page'))
    if role == 'company' and not company_id:
        flash('기업담당자 역할은 회사를 선택해야 합니다.')
        return redirect(url_for('login_page'))

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users(username,password_hash,role,company_id,employee_id,name,status) "
            "VALUES(?,?,?,?,?,?,'active')",
            (username, generate_password_hash(password), role,
             company_id, employee_id, name))
        db.commit()
        flash('계정이 생성되었습니다. 로그인하세요.')
    except Exception as e:
        flash(f'오류: {e}')
    finally:
        db.close()
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    resp = make_response(redirect(url_for('login_page')))
    resp.delete_cookie('session')
    resp.delete_cookie('remember_token')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old = request.form.get('old_password', '')
    new = request.form.get('new_password', '')
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (current_user.id,)).fetchone()
    if row and check_password_hash(row['password_hash'], old) and new:
        db.execute("UPDATE users SET password_hash=? WHERE id=?",
                   (generate_password_hash(new), current_user.id))
        db.commit()
        flash('비밀번호가 변경되었습니다.')
    else:
        flash('현재 비밀번호가 올바르지 않습니다.')
    db.close()
    return redirect(url_for('dashboard'))

# ── 관리자 보기 모드 ─────────────────────────────────────────────────────────
@app.route('/admin/set_view', methods=['POST'])
@login_required
def admin_set_view():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    eid = request.form.get('view_employee_id') or None
    cid = request.form.get('company_id') or None
    if eid:
        session['view_employee_id'] = int(eid)
    else:
        session.pop('view_employee_id', None)
    if cid:
        session['company_id'] = int(cid)
    else:
        session.pop('company_id', None)
    return redirect(request.referrer or url_for('dashboard'))

# ── 계정 관리 (관리자 전용) ───────────────────────────────────────────────────
@app.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    db = get_db()
    rows = db.execute(
        "SELECT u.*, c.name as co_name, e.name as emp_name "
        "FROM users u "
        "LEFT JOIN companies c ON u.company_id=c.id "
        "LEFT JOIN employees e ON u.employee_id=e.id "
        "ORDER BY u.role DESC, u.username").fetchall()
    db.close()
    return render_template('users.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/users/add', methods=['POST'])
@login_required
def user_add():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users(username,password_hash,role,company_id,employee_id,name) VALUES(?,?,?,?,?,?)",
            (f['username'], generate_password_hash(f['password']),
             f.get('role', 'company'),
             f.get('company_id') or None,
             f.get('employee_id') or None,
             f.get('name', '')))
        db.commit()
        flash('계정이 생성되었습니다.')
    except Exception as e:
        flash(f'오류: {e}')
    db.close()
    return redirect(url_for('users'))

@app.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
def user_delete(uid):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("DELETE FROM users WHERE id=? AND username!='admin'", (uid,))
    db.commit()
    db.close()
    return redirect(url_for('users'))

@app.route('/users/<int:uid>/reset_pw', methods=['POST'])
@login_required
def user_reset_pw(uid):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    pw = request.form.get('password', '')
    if pw:
        db = get_db()
        db.execute("UPDATE users SET password_hash=? WHERE id=?",
                   (generate_password_hash(pw), uid))
        db.commit()
        db.close()
        flash('비밀번호가 변경되었습니다.')
    return redirect(url_for('users'))

# ── 회사 선택 ─────────────────────────────────────────────────────────────────
@app.route('/select_company/<int:cid>')
@login_required
def select_company(cid):
    if current_user.is_admin:
        session['company_id'] = cid if cid else None
        session.pop('view_employee_id', None)
    return redirect(request.referrer or url_for('dashboard'))

# ── 대시보드 ──────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    # 직원 역할: 개인 대시보드
    if current_user.is_employee:
        eid = current_user.employee_id
        db = get_db()
        today_str  = date.today().isoformat()
        this_month = date.today().strftime('%Y-%m')

        today_att = db.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
            (eid, today_str)).fetchone()

        month_atts = db.execute(
            "SELECT COUNT(*) as days, SUM(work_hours) as total_h "
            "FROM attendance WHERE employee_id=? AND work_date LIKE ?",
            (eid, this_month + '%')).fetchone()

        year = date.today().year
        leave_bal = db.execute(
            "SELECT total_days, used_days FROM leave_balance WHERE employee_id=? AND year=?",
            (eid, year)).fetchone()

        last_salaries = db.execute(
            "SELECT s.*, e.name as emp_name, c.name as co_name "
            "FROM salary s JOIN employees e ON s.employee_id=e.id "
            "JOIN companies c ON e.company_id=c.id "
            "WHERE s.employee_id=? ORDER BY s.year DESC, s.month DESC LIMIT 3",
            (eid,)).fetchall()

        emp_info = db.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()

        # 이번달 출퇴근 목록 (캘린더용)
        month_atts_list = db.execute(
            "SELECT work_date, check_in, check_out, work_hours FROM attendance WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date",
            (eid, this_month + '%')).fetchall()

        # 공지사항
        cid2 = emp_info['company_id'] if emp_info else None
        nq = "SELECT * FROM notices WHERE 1=1"
        np_ = []
        if cid2:
            nq += " AND (company_id=? OR company_id IS NULL)"; np_ = [cid2]
        notice_rows = db.execute(nq + " ORDER BY is_pinned DESC, created_at DESC LIMIT 5", np_).fetchall()
        db.close()

        return render_template('dashboard.html',
            is_employee_view=True,
            today_att=today_att,
            today_str=today_str,
            month_days=month_atts['days'] or 0 if month_atts else 0,
            month_hours=month_atts['total_h'] or 0 if month_atts else 0,
            leave_bal=leave_bal,
            last_salaries=last_salaries,
            emp_info=emp_info,
            month_atts_list=month_atts_list,
            notice_rows=notice_rows,
            companies=all_companies(), sel=selected_company())

    # 관리자/기업담당자 대시보드
    cid = _cid_filter()
    db = get_db()
    total_co = db.execute(
        "SELECT COUNT(*) FROM companies" + (" WHERE id=?" if cid else ""),
        ([cid] if cid else [])).fetchone()[0]
    total_emp = db.execute(
        "SELECT COUNT(*) FROM employees e WHERE e.status='재직'" +
        (" AND e.company_id=?" if cid else ""),
        ([cid] if cid else [])).fetchone()[0]
    this_month = date.today().strftime('%Y-%m')
    consult_cnt = db.execute(
        "SELECT COUNT(*) FROM consultations WHERE created_at LIKE ?" +
        (" AND company_id=?" if cid else ""),
        ([this_month + '%', cid] if cid else [this_month + '%'])).fetchone()[0]
    recent = db.execute(
        "SELECT c.*, co.name as co_name FROM consultations c JOIN companies co ON c.company_id=co.id" +
        (" WHERE c.company_id=?" if cid else "") +
        " ORDER BY c.created_at DESC LIMIT 6",
        ([cid] if cid else [])).fetchall()
    co_stats = db.execute(
        "SELECT co.id, co.name, COUNT(e.id) as cnt FROM companies co "
        "LEFT JOIN employees e ON e.company_id=co.id AND e.status='재직'" +
        (" WHERE co.id=?" if cid else "") +
        " GROUP BY co.id ORDER BY cnt DESC",
        ([cid] if cid else [])).fetchall()

    # 공지사항
    nq = "SELECT * FROM notices WHERE 1=1"
    np_ = []
    if cid:
        nq += " AND (company_id=? OR company_id IS NULL)"; np_ = [cid]
    notice_rows = db.execute(nq + " ORDER BY is_pinned DESC, created_at DESC LIMIT 5", np_).fetchall()

    # 이번달 출퇴근 요약
    ym = date.today().strftime('%Y-%m')
    att_summary = db.execute(
        "SELECT COUNT(DISTINCT employee_id) as emp_cnt, COUNT(*) as att_cnt "
        "FROM attendance WHERE work_date LIKE ?" + (" AND employee_id IN (SELECT id FROM employees WHERE company_id=?)" if cid else ""),
        ([ym+'%', cid] if cid else [ym+'%'])).fetchone()

    db.close()
    return render_template('dashboard.html',
        is_employee_view=False,
        total_co=total_co, total_emp=total_emp,
        consult_cnt=consult_cnt, recent=recent, co_stats=co_stats,
        notice_rows=notice_rows, att_summary=att_summary,
        companies=all_companies(), sel=selected_company())

# ── 회사 관리 ─────────────────────────────────────────────────────────────────
@app.route('/companies')
@login_required
def companies():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    db = get_db()
    rows = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM employees WHERE company_id=c.id AND status='재직') as emp_cnt "
        "FROM companies c ORDER BY c.name").fetchall()
    db.close()
    return render_template('companies.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/companies/add', methods=['POST'])
@login_required
def company_add():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    db.execute(
        "INSERT INTO companies(name,biz_no,ceo,address,phone,industry,contract_date,memo) VALUES(?,?,?,?,?,?,?,?)",
        (f['name'], f.get('biz_no'), f.get('ceo'), f.get('address'),
         f.get('phone'), f.get('industry'), f.get('contract_date'), f.get('memo')))
    db.commit()
    db.close()
    flash('회사가 등록되었습니다.')
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/edit', methods=['POST'])
@login_required
def company_edit(cid):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    db.execute(
        "UPDATE companies SET name=?,biz_no=?,ceo=?,address=?,phone=?,industry=?,contract_date=?,memo=? WHERE id=?",
        (f['name'], f.get('biz_no'), f.get('ceo'), f.get('address'),
         f.get('phone'), f.get('industry'), f.get('contract_date'), f.get('memo'), cid))
    db.commit()
    db.close()
    flash('수정되었습니다.')
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/delete', methods=['POST'])
@login_required
def company_delete(cid):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("DELETE FROM companies WHERE id=?", (cid,))
    db.commit()
    db.close()
    if session.get('company_id') == cid:
        session.pop('company_id', None)
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/json')
@login_required
def company_json(cid):
    db = get_db()
    row = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 인사정보 ──────────────────────────────────────────────────────────────────
@app.route('/employees')
@login_required
def employees():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    cid = _cid_filter()
    db = get_db()
    if cid:
        rows = db.execute(
            "SELECT e.*, c.name as co_name FROM employees e "
            "JOIN companies c ON e.company_id=c.id WHERE e.company_id=? ORDER BY e.name",
            (cid,)).fetchall()
    else:
        rows = db.execute(
            "SELECT e.*, c.name as co_name FROM employees e "
            "JOIN companies c ON e.company_id=c.id ORDER BY c.name, e.name").fetchall()
    db.close()
    return render_template('employees.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/employees/add', methods=['POST'])
@login_required
def employee_add():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    co_id = current_user.company_id if not current_user.is_admin else f['company_id']
    db.execute(
        "INSERT INTO employees(company_id,name,emp_no,dept,position,hire_date,birth_date,phone,email,emp_type,status,base_salary,memo) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (co_id, f['name'], f.get('emp_no'), f.get('dept'), f.get('position'),
         f.get('hire_date'), f.get('birth_date'), f.get('phone'), f.get('email'),
         f.get('emp_type', '정규직'), f.get('status', '재직'),
         int(f.get('base_salary') or 0), f.get('memo')))
    db.commit()
    db.close()
    flash('직원이 등록되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/edit', methods=['POST'])
@login_required
def employee_edit(eid):
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    db.execute(
        "UPDATE employees SET name=?,emp_no=?,dept=?,position=?,hire_date=?,birth_date=?,phone=?,email=?,emp_type=?,status=?,base_salary=?,memo=? WHERE id=?",
        (f['name'], f.get('emp_no'), f.get('dept'), f.get('position'),
         f.get('hire_date'), f.get('birth_date'), f.get('phone'), f.get('email'),
         f.get('emp_type'), f.get('status'), int(f.get('base_salary') or 0),
         f.get('memo'), eid))
    db.commit()
    db.close()
    flash('수정되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/photo', methods=['POST'])
@login_required
def employee_photo(eid):
    f = request.files.get('photo')
    if f and f.filename:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            fname = f'emp_{eid}{ext}'
            for old in os.listdir(PHOTO_DIR):
                if old.startswith(f'emp_{eid}.'):
                    os.remove(os.path.join(PHOTO_DIR, old))
            f.save(os.path.join(PHOTO_DIR, fname))
            db = get_db()
            db.execute("UPDATE employees SET photo=? WHERE id=?", (fname, eid))
            db.commit()
            db.close()
            flash('사진이 등록되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/delete', methods=['POST'])
@login_required
def employee_delete(eid):
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("DELETE FROM employees WHERE id=?", (eid,))
    db.commit()
    db.close()
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/json')
@login_required
def employee_json(eid):
    db = get_db()
    row = db.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 출퇴근 ────────────────────────────────────────────────────────────────────
@app.route('/attendance')
@login_required
def attendance():
    cid   = _cid_filter()
    eid   = _eid_filter()
    year  = int(request.args.get('year',  date.today().year))
    month = int(request.args.get('month', date.today().month))
    tab   = request.args.get('tab', 'search')  # search|status|input|record|current|late
    # 하위 호환: 기존 mode 파라미터 지원
    legacy_mode = request.args.get('mode', '')
    if legacy_mode == 'year':
        tab = 'status'

    ym = f"{year}-{month:02d}"
    db = get_db()

    base_att = ("FROM attendance a JOIN employees e ON a.employee_id=e.id "
                "JOIN companies c ON e.company_id=c.id WHERE a.work_date LIKE ?")
    base_p = [ym + '%']
    if eid:
        base_att += " AND a.employee_id=?"
        base_p.append(eid)
    elif cid:
        base_att += " AND e.company_id=?"
        base_p.append(cid)

    sel_att = "SELECT a.*, e.name as emp_name, e.dept, c.name as co_name, e.id as emp_id "

    rows = db.execute(sel_att + base_att + " ORDER BY a.work_date, e.name", base_p).fetchall()

    emps_q = ("SELECT e.id, e.name, e.dept, c.name as co_name FROM employees e "
              "JOIN companies c ON e.company_id=c.id WHERE e.status='재직'")
    emps_p = []
    if eid:
        emps_q += " AND e.id=?"
        emps_p.append(eid)
    elif cid:
        emps_q += " AND e.company_id=?"
        emps_p.append(cid)
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    # 연간 통계 (status 탭에서 사용)
    year_monthly, year_emps = [], []
    if tab == 'status':
        ybase = ("FROM attendance a JOIN employees e ON a.employee_id=e.id "
                 "JOIN companies c ON e.company_id=c.id WHERE a.work_date LIKE ?")
        yp = [str(year) + '%']
        if eid:
            ybase += " AND a.employee_id=?"
            yp.append(eid)
        elif cid:
            ybase += " AND e.company_id=?"
            yp.append(cid)
        year_monthly = db.execute(
            f"SELECT strftime('%m', a.work_date) as mon, COUNT(*) as days, "
            f"SUM(a.work_hours) as total_h, SUM(a.overtime_hours) as total_ot {ybase} "
            f"GROUP BY mon ORDER BY mon", yp).fetchall()
        year_emps = db.execute(
            f"SELECT e.id, e.name, e.dept, c.name as co_name, COUNT(*) as days, "
            f"SUM(a.work_hours) as total_h, SUM(a.overtime_hours) as total_ot {ybase} "
            f"GROUP BY e.id ORDER BY c.name, e.name", yp).fetchall()

    # 출퇴근현황: 직원×날짜 그리드
    att_grid   = {}  # {emp_id: {day: record}}
    total_days_in_month = cal_module.monthrange(year, month)[1]
    if tab == 'current':
        for r in rows:
            day = int(r['work_date'][-2:])
            att_grid.setdefault(r['emp_id'], {})[day] = dict(r)

    # 지각현황: check_in > std_time
    late_rows = []
    std_time  = '09:00'
    if tab == 'late':
        late_q = (sel_att + base_att + " AND a.check_in IS NOT NULL AND a.check_in > ?")
        late_rows = db.execute(late_q + " ORDER BY a.work_date, e.name",
                               base_p + [std_time]).fetchall()

    db.close()
    return render_template('attendance.html',
        rows=rows, emps=emps, year=year, month=month,
        tab=tab, std_time=std_time,
        year_monthly=year_monthly, year_emps=year_emps,
        att_grid=att_grid, late_rows=late_rows,
        total_days_in_month=total_days_in_month,
        companies=all_companies(), sel=selected_company())

@app.route('/attendance/add', methods=['POST'])
@login_required
def attendance_add():
    f = request.form
    ci   = f.get('check_in', '')
    co_t = f.get('check_out', '')
    wh = ot = 0.0
    if ci and co_t:
        t1    = datetime.strptime(ci, '%H:%M')
        t2    = datetime.strptime(co_t, '%H:%M')
        total = (t2 - t1).seconds / 3600
        wh, ot, _ = calc_work_hours(total)
    # 직원 역할은 자기 자신 ID만 허용
    if current_user.is_employee:
        emp_id = current_user.employee_id
    else:
        emp_id = f['employee_id']
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO attendance(employee_id,work_date,check_in,check_out,work_hours,overtime_hours,memo) "
        "VALUES(?,?,?,?,?,?,?)",
        (emp_id, f['work_date'], ci, co_t, round(wh, 2), round(ot, 2), f.get('memo')))
    db.commit()
    db.close()
    flash('출퇴근이 기록되었습니다.')
    return redirect(url_for('attendance',
        year=f['work_date'][:4], month=int(f['work_date'][5:7]),
        tab=f.get('redirect_tab', 'search')))

@app.route('/attendance/<int:aid>/delete', methods=['POST'])
@login_required
def attendance_delete(aid):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE id=?", (aid,))
    db.commit()
    db.close()
    return redirect(url_for('attendance'))

@app.route('/attendance/bulk_add', methods=['POST'])
@login_required
def attendance_bulk_add():
    """평일/주말 패턴을 기반으로 기간 내 출퇴근을 일괄 등록한다."""
    f = request.form
    if current_user.is_employee:
        emp_id = current_user.employee_id
    else:
        emp_id = f.get('employee_id')
    if not emp_id:
        flash('직원을 선택해주세요.')
        return redirect(url_for('attendance'))

    start_str = f.get('bulk_start_date', '')
    end_str   = f.get('bulk_end_date', '')
    ci        = f.get('bulk_check_in',  '09:00')
    co_t      = f.get('bulk_check_out', '18:00')
    weekdays  = [int(w) for w in f.getlist('bulk_weekdays')]  # 0=월 … 6=일

    if not start_str or not end_str:
        flash('날짜 범위를 입력해주세요.')
        return redirect(url_for('attendance'))

    try:
        start_d = date.fromisoformat(start_str)
        end_d   = date.fromisoformat(end_str)
    except Exception:
        flash('날짜 형식이 올바르지 않습니다.')
        return redirect(url_for('attendance'))

    if end_d < start_d:
        flash('종료일이 시작일보다 앞입니다.')
        return redirect(url_for('attendance'))
    if (end_d - start_d).days > 366:
        flash('최대 1년(366일) 범위까지 등록 가능합니다.')
        return redirect(url_for('attendance'))

    wh = ot = 0.0
    if ci and co_t:
        t1 = datetime.strptime(ci, '%H:%M')
        t2 = datetime.strptime(co_t, '%H:%M')
        total = max(0, (t2 - t1).seconds / 3600)
        wh, ot, _ = calc_work_hours(total)

    db = get_db()
    count = 0
    cur = start_d
    while cur <= end_d:
        if cur.weekday() in weekdays:
            db.execute(
                "INSERT OR IGNORE INTO attendance"
                "(employee_id,work_date,check_in,check_out,work_hours,overtime_hours) "
                "VALUES(?,?,?,?,?,?)",
                (emp_id, cur.isoformat(), ci, co_t, round(wh, 2), round(ot, 2)))
            count += 1
        cur += timedelta(days=1)
    db.commit()
    db.close()
    flash(f'총 {count}일 출퇴근 기록이 일괄 등록되었습니다.')
    return redirect(url_for('attendance', year=start_d.year, month=start_d.month, tab='input'))

# ── 직원 출퇴근 체크인/아웃 ────────────────────────────────────────────────────
@app.route('/checkin', methods=['POST'])
@login_required
def checkin():
    if not current_user.is_employee:
        return redirect(url_for('dashboard'))
    action    = request.form.get('action', 'in')
    now_dt    = datetime.now()
    today_str = now_dt.strftime('%Y-%m-%d')
    time_str  = now_dt.strftime('%H:%M')
    eid = current_user.employee_id
    db = get_db()
    existing = db.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
        (eid, today_str)).fetchone()
    if action == 'in':
        if existing:
            db.execute("UPDATE attendance SET check_in=? WHERE id=?",
                       (time_str, existing['id']))
        else:
            db.execute(
                "INSERT INTO attendance(employee_id,work_date,check_in) VALUES(?,?,?)",
                (eid, today_str, time_str))
        flash(f'출근 기록: {time_str}')
    elif action == 'out':
        if existing:
            ci = existing['check_in'] or '09:00'
            t1 = datetime.strptime(ci, '%H:%M')
            t2 = datetime.strptime(time_str, '%H:%M')
            total = max(0, (t2 - t1).seconds / 3600)
            wh, ot, _ = calc_work_hours(total)
            db.execute(
                "UPDATE attendance SET check_out=?, work_hours=?, overtime_hours=? WHERE id=?",
                (time_str, round(wh, 2), round(ot, 2), existing['id']))
            flash(f'퇴근 기록: {time_str} (근무 {wh:.1f}h)')
        else:
            db.execute(
                "INSERT INTO attendance(employee_id,work_date,check_out) VALUES(?,?,?)",
                (eid, today_str, time_str))
            flash(f'퇴근 기록: {time_str}')
    db.commit()
    db.close()
    return redirect(url_for('dashboard'))

# ── 연차 ──────────────────────────────────────────────────────────────────────
@app.route('/leave')
@login_required
def leave():
    cid = _cid_filter()
    eid = _eid_filter()
    year = int(request.args.get('year', date.today().year))
    db = get_db()

    emps_q = (
        "SELECT e.id,e.name,e.dept,e.hire_date,c.name as co_name,"
        "COALESCE(lb.total_days,0) as total_days,COALESCE(lb.used_days,0) as used_days "
        "FROM employees e JOIN companies c ON e.company_id=c.id "
        "LEFT JOIN leave_balance lb ON lb.employee_id=e.id AND lb.year=? "
        "WHERE e.status='재직'")
    emps_p = [year]
    if eid:
        emps_q += " AND e.id=?"
        emps_p.append(eid)
    elif cid:
        emps_q += " AND e.company_id=?"
        emps_p.append(cid)
    emps_q += " ORDER BY c.name, e.name"
    emps = db.execute(emps_q, emps_p).fetchall()

    reqs_q = (
        "SELECT lr.*, e.name as emp_name, c.name as co_name FROM leave_requests lr "
        "JOIN employees e ON lr.employee_id=e.id JOIN companies c ON e.company_id=c.id "
        "WHERE lr.start_date LIKE ?")
    reqs_p = [str(year) + '%']
    if eid:
        reqs_q += " AND lr.employee_id=?"
        reqs_p.append(eid)
    elif cid:
        reqs_q += " AND e.company_id=?"
        reqs_p.append(cid)
    reqs = db.execute(reqs_q + " ORDER BY lr.created_at DESC", reqs_p).fetchall()
    db.close()
    return render_template('leave.html', emps=emps, reqs=reqs, year=year,
        companies=all_companies(), sel=selected_company(), calc_annual_leave=calc_annual_leave)

@app.route('/leave/auto_assign', methods=['POST'])
@login_required
def leave_auto_assign():
    year = int(request.form.get('year', date.today().year))
    cid = _cid_filter()
    db = get_db()
    emps = db.execute(
        "SELECT id, hire_date FROM employees WHERE status='재직'" +
        (" AND company_id=?" if cid else ""),
        ([cid] if cid else [])).fetchall()
    for e in emps:
        days = calc_annual_leave(e['hire_date'])
        db.execute(
            "INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,?,0) "
            "ON CONFLICT(employee_id,year) DO UPDATE SET total_days=excluded.total_days",
            (e['id'], year, days))
    db.commit()
    db.close()
    flash(f'{year}년 법정 연차가 재직 직원에게 자동 부여되었습니다.')
    return redirect(url_for('leave', year=year))

@app.route('/leave/balance/set', methods=['POST'])
@login_required
def leave_balance_set():
    f = request.form
    db = get_db()
    db.execute(
        "INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,?,0) "
        "ON CONFLICT(employee_id,year) DO UPDATE SET total_days=excluded.total_days",
        (f['employee_id'], f['year'], float(f['total_days'])))
    db.commit()
    db.close()
    return redirect(url_for('leave', year=f['year']))

@app.route('/leave/request/add', methods=['POST'])
@login_required
def leave_request_add():
    f = request.form
    if current_user.is_employee:
        emp_id = current_user.employee_id
    else:
        emp_id = f['employee_id']
    db = get_db()
    db.execute(
        "INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,?,?,?,?,?)",
        (emp_id, f.get('leave_type', '연차'), f['start_date'], f['end_date'],
         float(f.get('days', 1)), f.get('reason')))
    db.commit()
    db.close()
    flash('휴가 신청이 접수되었습니다.')
    return redirect(url_for('leave'))

@app.route('/leave/request/<int:rid>/approve', methods=['POST'])
@login_required
def leave_approve(rid):
    db = get_db()
    req = db.execute("SELECT * FROM leave_requests WHERE id=?", (rid,)).fetchone()
    if req:
        db.execute("UPDATE leave_requests SET status='승인' WHERE id=?", (rid,))
        db.execute(
            "INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,0,?) "
            "ON CONFLICT(employee_id,year) DO UPDATE SET used_days=used_days+excluded.used_days",
            (req['employee_id'], req['start_date'][:4], req['days']))
        db.commit()
    db.close()
    return redirect(url_for('leave'))

@app.route('/leave/request/<int:rid>/reject', methods=['POST'])
@login_required
def leave_reject(rid):
    db = get_db()
    db.execute("UPDATE leave_requests SET status='반려' WHERE id=?", (rid,))
    db.commit()
    db.close()
    return redirect(url_for('leave'))

# ── 보수 ──────────────────────────────────────────────────────────────────────
@app.route('/salary')
@login_required
def salary():
    cid = _cid_filter()
    eid = _eid_filter()
    year  = int(request.args.get('year',  date.today().year))
    month = int(request.args.get('month', date.today().month))
    view  = request.args.get('view', 'month')
    db = get_db()

    rows_q = (
        "SELECT s.*, e.name as emp_name, e.dept, e.position, e.emp_no, c.name as co_name "
        "FROM salary s JOIN employees e ON s.employee_id=e.id "
        "JOIN companies c ON e.company_id=c.id "
        "WHERE s.year=? AND s.month=?")
    rows_p = [year, month]
    if eid:
        rows_q += " AND s.employee_id=?"
        rows_p.append(eid)
    elif cid:
        rows_q += " AND e.company_id=?"
        rows_p.append(cid)
    rows = db.execute(rows_q + " ORDER BY c.name, e.name", rows_p).fetchall()

    emps_q = (
        "SELECT e.id,e.name,e.base_salary,c.name as co_name FROM employees e "
        "JOIN companies c ON e.company_id=c.id WHERE e.status='재직'")
    emps_p = []
    if eid:
        emps_q += " AND e.id=?"
        emps_p.append(eid)
    elif cid:
        emps_q += " AND e.company_id=?"
        emps_p.append(cid)
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    annual_rows = []
    if view == 'annual':
        ann_q = (
            "SELECT e.id, e.name, e.dept, c.name as co_name, "
            "SUM(s.base+s.overtime_pay+s.bonus+s.allowance) as gross, "
            "SUM(s.income_tax+s.health_ins+s.employ_ins+s.pension) as deductions, "
            "SUM(s.net_pay) as net_total, COUNT(s.id) as months "
            "FROM salary s JOIN employees e ON s.employee_id=e.id "
            "JOIN companies c ON e.company_id=c.id WHERE s.year=?")
        ann_p = [year]
        if eid:
            ann_q += " AND s.employee_id=?"
            ann_p.append(eid)
        elif cid:
            ann_q += " AND e.company_id=?"
            ann_p.append(cid)
        annual_rows = db.execute(
            ann_q + " GROUP BY e.id ORDER BY c.name, e.name", ann_p).fetchall()
    db.close()
    return render_template('salary.html', rows=rows, emps=emps, year=year, month=month,
        total=sum(r['net_pay'] for r in rows), view=view, annual_rows=annual_rows,
        companies=all_companies(), sel=selected_company())

@app.route('/salary/add', methods=['POST'])
@login_required
def salary_add():
    f = request.form
    i = lambda k: int(f.get(k) or 0)

    # 수당 상세 처리
    allowance_names   = f.getlist('allowance_name[]')
    allowance_amounts = f.getlist('allowance_amount[]')
    allowance_detail  = []
    total_allowance   = 0
    for name, amt_str in zip(allowance_names, allowance_amounts):
        if name and amt_str:
            amt = int(amt_str or 0)
            if amt:
                allowance_detail.append({'name': name, 'amount': amt})
                total_allowance += amt
    allowance_json = json.dumps(allowance_detail, ensure_ascii=False) if allowance_detail else None

    net = (i('base') + i('overtime_pay') + i('bonus') + total_allowance
           - i('income_tax') - i('health_ins') - i('employ_ins') - i('pension'))

    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO salary("
        "employee_id,year,month,base,overtime_pay,bonus,allowance,"
        "income_tax,health_ins,employ_ins,pension,net_pay,memo,"
        "allowance_detail,work_days,total_hours) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f['employee_id'], f['year'], f['month'],
         i('base'), i('overtime_pay'), i('bonus'), total_allowance,
         i('income_tax'), i('health_ins'), i('employ_ins'), i('pension'),
         net, f.get('memo'), allowance_json,
         int(f.get('work_days') or 0), float(f.get('total_hours') or 0)))
    db.commit()
    db.close()
    flash('급여가 등록되었습니다.')
    return redirect(url_for('salary', year=f['year'], month=f['month']))

@app.route('/salary/<int:sid>/delete', methods=['POST'])
@login_required
def salary_delete(sid):
    db = get_db()
    db.execute("DELETE FROM salary WHERE id=?", (sid,))
    db.commit()
    db.close()
    return redirect(url_for('salary'))

@app.route('/salary/<int:sid>/json')
@login_required
def salary_json(sid):
    db = get_db()
    row = db.execute(
        "SELECT s.*, e.name as emp_name, e.dept, e.position, e.emp_no, "
        "c.name as co_name, c.biz_no, c.address, c.phone as co_phone, c.ceo "
        "FROM salary s JOIN employees e ON s.employee_id=e.id "
        "JOIN companies c ON e.company_id=c.id WHERE s.id=?", (sid,)).fetchone()
    db.close()
    if not row:
        return ('', 404)
    d = dict(row)
    if d.get('allowance_detail'):
        try:
            d['allowance_items'] = json.loads(d['allowance_detail'])
        except Exception:
            d['allowance_items'] = []
    else:
        d['allowance_items'] = []
    return jsonify(d)

# ── 노무자문 ──────────────────────────────────────────────────────────────────
@app.route('/consultation')
@login_required
def consultation():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    cid = _cid_filter()
    status_f = request.args.get('status', '')
    db = get_db()
    q = "SELECT c.*, co.name as co_name FROM consultations c JOIN companies co ON c.company_id=co.id WHERE 1=1"
    params = []
    if cid:
        q += " AND c.company_id=?"
        params.append(cid)
    if status_f:
        q += " AND c.status=?"
        params.append(status_f)
    rows = db.execute(q + " ORDER BY c.created_at DESC", params).fetchall()
    db.close()
    return render_template('consultation.html', rows=rows, status_f=status_f,
        companies=all_companies(), sel=selected_company())

@app.route('/consultation/add', methods=['POST'])
@login_required
def consultation_add():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    co_id = current_user.company_id if not current_user.is_admin else f['company_id']
    db.execute(
        "INSERT INTO consultations(company_id,title,category,content,priority) VALUES(?,?,?,?,?)",
        (co_id, f['title'], f.get('category', '일반'), f.get('content'), f.get('priority', '보통')))
    db.commit()
    db.close()
    flash('자문의뢰가 등록되었습니다.')
    return redirect(url_for('consultation'))

@app.route('/consultation/<int:cid>/update', methods=['POST'])
@login_required
def consultation_update(cid):
    f = request.form
    resolved = date.today().isoformat() if f.get('status') == '완료' else None
    db = get_db()
    db.execute(
        "UPDATE consultations SET status=?,response=?,resolved_at=COALESCE(?,resolved_at) WHERE id=?",
        (f.get('status'), f.get('response'), resolved, cid))
    db.commit()
    db.close()
    return redirect(url_for('consultation'))

@app.route('/consultation/<int:cid>/json')
@login_required
def consultation_json(cid):
    db = get_db()
    row = db.execute("SELECT * FROM consultations WHERE id=?", (cid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 수당/공제 항목 마스터 ─────────────────────────────────────────────────────
@app.route('/salary/settings')
@login_required
def salary_settings():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    cid = _cid_filter()
    db  = get_db()
    aq = "SELECT * FROM allowance_master WHERE is_active=1"
    dq = "SELECT * FROM deduction_master WHERE is_active=1"
    ap, dp = [], []
    if cid:
        aq += " AND (company_id=? OR company_id IS NULL)"
        dq += " AND (company_id=? OR company_id IS NULL)"
        ap, dp = [cid], [cid]
    allowances  = db.execute(aq + " ORDER BY display_order, id", ap).fetchall()
    deductions  = db.execute(dq + " ORDER BY display_order, id", dp).fetchall()
    db.close()
    return render_template('salary_settings.html',
        allowances=allowances, deductions=deductions,
        companies=all_companies(), sel=selected_company())

@app.route('/salary/settings/allowance/add', methods=['POST'])
@login_required
def allowance_add():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    f   = request.form
    cid = _cid_filter()
    db  = get_db()
    db.execute(
        "INSERT INTO allowance_master(company_id,code,name,display_order,tax_type,pay_type,memo) "
        "VALUES(?,?,?,?,?,?,?)",
        (cid, f.get('code'), f['name'], int(f.get('display_order') or 0),
         f.get('tax_type', '전액과세'), f.get('pay_type', '고정'), f.get('memo')))
    db.commit(); db.close()
    flash(f"수당항목 '{f['name']}'이 등록되었습니다.")
    return redirect(url_for('salary_settings'))

@app.route('/salary/settings/allowance/<int:aid>/delete', methods=['POST'])
@login_required
def allowance_delete(aid):
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("UPDATE allowance_master SET is_active=0 WHERE id=?", (aid,))
    db.commit(); db.close()
    return redirect(url_for('salary_settings'))

@app.route('/salary/settings/deduction/add', methods=['POST'])
@login_required
def deduction_add():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    f   = request.form
    cid = _cid_filter()
    db  = get_db()
    db.execute(
        "INSERT INTO deduction_master(company_id,code,name,display_order,memo) VALUES(?,?,?,?,?)",
        (cid, f.get('code'), f['name'], int(f.get('display_order') or 0), f.get('memo')))
    db.commit(); db.close()
    flash(f"공제항목 '{f['name']}'이 등록되었습니다.")
    return redirect(url_for('salary_settings'))

@app.route('/salary/settings/deduction/<int:did>/delete', methods=['POST'])
@login_required
def deduction_delete(did):
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("UPDATE deduction_master SET is_active=0 WHERE id=?", (did,))
    db.commit(); db.close()
    return redirect(url_for('salary_settings'))

@app.route('/api/allowance_master')
@login_required
def api_allowance_master():
    cid = _cid_filter()
    db  = get_db()
    q   = "SELECT * FROM allowance_master WHERE is_active=1"
    p   = []
    if cid:
        q += " AND (company_id=? OR company_id IS NULL)"
        p  = [cid]
    rows = db.execute(q + " ORDER BY display_order, id", p).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── 퇴직금 ────────────────────────────────────────────────────────────────────
def _calc_severance(employee_id, retire_date_str=None):
    """퇴직금 = 평균임금×30×(근속일수/365) (근로자퇴직급여보장법 제4조)"""
    db  = get_db()
    emp = db.execute("SELECT hire_date, base_salary, name FROM employees WHERE id=?",
                     (employee_id,)).fetchone()
    if not emp or not emp['hire_date']:
        db.close()
        return None
    hire    = date.fromisoformat(emp['hire_date'])
    retire  = date.fromisoformat(retire_date_str) if retire_date_str else date.today()
    service = (retire - hire).days

    if service < 365:
        db.close()
        return {'eligible': False, 'service_days': service, 'emp_name': emp['name']}

    # 최근 3개월 임금 (salary 테이블)
    last3 = db.execute(
        "SELECT base+overtime_pay+bonus+allowance as total "
        "FROM salary WHERE employee_id=? ORDER BY year DESC, month DESC LIMIT 3",
        (employee_id,)).fetchall()

    if last3:
        three_wages = sum(r['total'] for r in last3)
        three_days  = len(last3) * 30
    else:
        three_wages = (emp['base_salary'] or 0) * 3
        three_days  = 90

    avg_daily    = three_wages / three_days if three_days else 0
    severance    = int(avg_daily * 30 * (service / 365))
    db.close()
    return {
        'eligible':        True,
        'emp_name':        emp['name'],
        'service_days':    service,
        'service_years':   round(service / 365, 2),
        'three_month_wages': int(three_wages),
        'three_month_days':  three_days,
        'avg_daily_wage':  round(avg_daily),
        'severance_pay':   severance,
    }

@app.route('/salary/severance')
@login_required
def salary_severance():
    if current_user.is_employee:
        return redirect(url_for('dashboard'))
    cid = _cid_filter()
    db  = get_db()
    emps_q = ("SELECT e.id, e.name, e.hire_date, e.dept, c.name as co_name "
              "FROM employees e JOIN companies c ON e.company_id=c.id "
              "WHERE e.status='재직'")
    emps_p = []
    if cid:
        emps_q += " AND e.company_id=?"
        emps_p  = [cid]
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    recs_q = ("SELECT sv.*, e.name as emp_name, c.name as co_name "
              "FROM severance_record sv JOIN employees e ON sv.employee_id=e.id "
              "JOIN companies c ON e.company_id=c.id WHERE 1=1")
    recs_p = []
    if cid:
        recs_q += " AND e.company_id=?"
        recs_p  = [cid]
    records = db.execute(recs_q + " ORDER BY sv.created_at DESC", recs_p).fetchall()
    db.close()
    return render_template('severance.html', emps=emps, records=records,
        companies=all_companies(), sel=selected_company())

@app.route('/salary/severance/calc', methods=['POST'])
@login_required
def severance_calc():
    f           = request.form
    employee_id = f['employee_id']
    retire_date = f.get('retire_date') or None
    result      = _calc_severance(employee_id, retire_date)
    if not result:
        flash('직원 정보가 없습니다.')
        return redirect(url_for('salary_severance'))
    if not result['eligible']:
        flash(f"{result['emp_name']}는 근속 {result['service_days']}일로 퇴직금 지급 요건(1년)에 미달합니다.")
        return redirect(url_for('salary_severance'))
    db = get_db()
    db.execute(
        "INSERT INTO severance_record"
        "(employee_id,retire_date,service_days,avg_daily_wage,"
        "three_month_wages,three_month_days,severance_pay,memo) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (employee_id, retire_date or date.today().isoformat(),
         result['service_days'], result['avg_daily_wage'],
         result['three_month_wages'], result['three_month_days'],
         result['severance_pay'], f.get('memo')))
    db.commit(); db.close()
    flash(f"{result['emp_name']} 퇴직금 {result['severance_pay']:,}원이 계산되었습니다.")
    return redirect(url_for('salary_severance'))

@app.route('/salary/severance/<int:rid>/delete', methods=['POST'])
@login_required
def severance_delete(rid):
    db = get_db()
    db.execute("DELETE FROM severance_record WHERE id=?", (rid,))
    db.commit(); db.close()
    return redirect(url_for('salary_severance'))

# ── 월별 캘린더 ────────────────────────────────────────────────────────────────
@app.route('/calendar')
@login_required
def calendar_view():
    cid = _cid_filter()
    eid = _eid_filter()
    year   = int(request.args.get('year',  date.today().year))
    month  = int(request.args.get('month', date.today().month))
    dept_f = request.args.get('dept', '')
    emp_f  = request.args.get('emp_id', '')

    db = get_db()
    ym = f"{year}-{month:02d}"

    # 출퇴근 데이터
    att_q = (
        "SELECT a.work_date, a.work_hours, a.overtime_hours, a.check_in, a.check_out, "
        "e.name as emp_name, e.dept "
        "FROM attendance a JOIN employees e ON a.employee_id=e.id "
        "JOIN companies c ON e.company_id=c.id "
        "WHERE a.work_date LIKE ?")
    att_p = [ym + '%']
    if eid:
        att_q += " AND a.employee_id=?"
        att_p.append(eid)
    elif emp_f:
        att_q += " AND a.employee_id=?"
        att_p.append(int(emp_f))
    elif dept_f and cid:
        att_q += " AND e.dept=? AND e.company_id=?"
        att_p.extend([dept_f, cid])
    elif cid:
        att_q += " AND e.company_id=?"
        att_p.append(cid)
    att_rows = db.execute(att_q, att_p).fetchall()

    # 연차 데이터 (승인된 것)
    leave_q = (
        "SELECT lr.start_date, lr.end_date, lr.leave_type, lr.days, "
        "e.name as emp_name "
        "FROM leave_requests lr JOIN employees e ON lr.employee_id=e.id "
        "JOIN companies c ON e.company_id=c.id "
        "WHERE lr.status='승인' AND (lr.start_date LIKE ? OR lr.end_date LIKE ?)")
    leave_p = [ym + '%', ym + '%']
    if eid:
        leave_q += " AND lr.employee_id=?"
        leave_p.append(eid)
    elif emp_f:
        leave_q += " AND lr.employee_id=?"
        leave_p.append(int(emp_f))
    elif dept_f and cid:
        leave_q += " AND e.dept=? AND e.company_id=?"
        leave_p.extend([dept_f, cid])
    elif cid:
        leave_q += " AND e.company_id=?"
        leave_p.append(cid)
    leave_rows = db.execute(leave_q, leave_p).fetchall()

    # 필터용 직원/부서 목록
    filter_emps  = []
    filter_depts = []
    if cid and not eid:
        filter_emps = db.execute(
            "SELECT id, name, dept FROM employees WHERE company_id=? AND status='재직' ORDER BY name",
            (cid,)).fetchall()
        depts = db.execute(
            "SELECT DISTINCT dept FROM employees WHERE company_id=? AND dept IS NOT NULL AND dept!='' ORDER BY dept",
            (cid,)).fetchall()
        filter_depts = [d['dept'] for d in depts]
    db.close()

    # 달력 그리드 구성 (월요일 시작)
    total_days   = cal_module.monthrange(year, month)[1]
    first_day    = date(year, month, 1)
    start_weekday = first_day.weekday()  # 월=0, 일=6

    # 출퇴근 딕셔너리 {date_str: [records]}
    att_by_date = {}
    for r in att_rows:
        att_by_date.setdefault(r['work_date'], []).append(dict(r))

    # 연차 딕셔너리 — 날짜 범위 전개
    leave_by_date = {}
    for r in leave_rows:
        try:
            s    = date.fromisoformat(r['start_date'])
            e_d  = date.fromisoformat(r['end_date'])
            import datetime as _dt
            cur  = s
            while cur <= e_d:
                ds = cur.isoformat()
                if ds[:7] == ym:
                    leave_by_date.setdefault(ds, []).append(dict(r))
                cur += _dt.timedelta(days=1)
        except Exception:
            pass

    # prev/next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render_template('calendar.html',
        year=year, month=month,
        total_days=total_days, start_weekday=start_weekday,
        att_by_date=att_by_date, leave_by_date=leave_by_date,
        filter_emps=filter_emps, filter_depts=filter_depts,
        dept_f=dept_f, emp_f=emp_f,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        companies=all_companies(), sel=selected_company())

# ── 공지사항 ──────────────────────────────────────────────────────────────────
@app.route('/notices')
@login_required
def notices():
    cid = _cid_filter()
    db = get_db()
    q = "SELECT n.*, c.name as co_name FROM notices n LEFT JOIN companies c ON n.company_id=c.id WHERE 1=1"
    p = []
    if cid:
        q += " AND (n.company_id=? OR n.company_id IS NULL)"
        p = [cid]
    rows = db.execute(q + " ORDER BY n.is_pinned DESC, n.created_at DESC LIMIT 50", p).fetchall()
    db.close()
    return render_template('notices.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/notices/add', methods=['POST'])
@login_required
def notice_add():
    if not (current_user.is_admin or current_user.is_company):
        return redirect(url_for('notices'))
    f = request.form
    cid = _cid_filter()
    db = get_db()
    db.execute(
        "INSERT INTO notices(company_id,title,content,category,is_pinned,created_by) VALUES(?,?,?,?,?,?)",
        (cid or f.get('company_id') or None, f['title'], f.get('content'),
         f.get('category','일반'), 1 if f.get('is_pinned') else 0, current_user.name))
    db.commit(); db.close()
    flash('공지사항이 등록되었습니다.')
    return redirect(url_for('notices'))

@app.route('/notices/<int:nid>/delete', methods=['POST'])
@login_required
def notice_delete(nid):
    if not current_user.is_admin:
        return redirect(url_for('notices'))
    db = get_db()
    db.execute("DELETE FROM notices WHERE id=?", (nid,))
    db.commit(); db.close()
    return redirect(url_for('notices'))

# ── 출장관리 ──────────────────────────────────────────────────────────────────
@app.route('/trip')
@login_required
def trip():
    cid = _cid_filter()
    eid = _eid_filter()
    db = get_db()
    emps_q = "SELECT e.id, e.name, e.dept, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
    emps_p = []
    if cid:
        emps_q += " AND e.company_id=?"; emps_p = [cid]
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    q = ("SELECT t.*, e.name as emp_name, c.name as co_name "
         "FROM trip_requests t JOIN employees e ON t.employee_id=e.id "
         "JOIN companies c ON e.company_id=c.id WHERE 1=1")
    p = []
    if eid:
        q += " AND t.employee_id=?"; p = [eid]
    elif cid:
        q += " AND e.company_id=?"; p = [cid]
    rows = db.execute(q + " ORDER BY t.created_at DESC LIMIT 100", p).fetchall()
    db.close()
    return render_template('trip.html', rows=rows, emps=emps, companies=all_companies(), sel=selected_company())

@app.route('/trip/add', methods=['POST'])
@login_required
def trip_add():
    f = request.form
    eid = f.get('employee_id') or (_eid_filter())
    if not eid:
        flash('직원을 선택하세요.'); return redirect(url_for('trip'))
    start = f['start_date']; end = f['end_date']
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except Exception:
        days = 1
    db = get_db()
    db.execute(
        "INSERT INTO trip_requests(employee_id,destination,purpose,start_date,end_date,days,transport,budget,memo) VALUES(?,?,?,?,?,?,?,?,?)",
        (eid, f['destination'], f.get('purpose'), start, end, days,
         f.get('transport','자가용'), int(f.get('budget') or 0), f.get('memo')))
    db.commit(); db.close()
    flash('출장신청이 등록되었습니다.')
    return redirect(url_for('trip'))

@app.route('/trip/<int:tid>/status', methods=['POST'])
@login_required
def trip_status(tid):
    status = request.form.get('status','승인')
    db = get_db()
    db.execute("UPDATE trip_requests SET status=? WHERE id=?", (status, tid))
    db.commit(); db.close()
    return redirect(url_for('trip'))

@app.route('/trip/<int:tid>/delete', methods=['POST'])
@login_required
def trip_delete(tid):
    db = get_db()
    db.execute("DELETE FROM trip_requests WHERE id=?", (tid,))
    db.commit(); db.close()
    return redirect(url_for('trip'))

# ── 복리후생 ──────────────────────────────────────────────────────────────────
@app.route('/welfare')
@login_required
def welfare():
    cid = _cid_filter()
    eid = _eid_filter()
    db = get_db()
    emps_q = "SELECT e.id, e.name, e.dept, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
    emps_p = []
    if cid:
        emps_q += " AND e.company_id=?"; emps_p = [cid]
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    q = ("SELECT w.*, e.name as emp_name, c.name as co_name "
         "FROM welfare_events w JOIN employees e ON w.employee_id=e.id "
         "JOIN companies c ON e.company_id=c.id WHERE 1=1")
    p = []
    if eid:
        q += " AND w.employee_id=?"; p = [eid]
    elif cid:
        q += " AND e.company_id=?"; p = [cid]
    rows = db.execute(q + " ORDER BY w.created_at DESC LIMIT 100", p).fetchall()
    db.close()
    return render_template('welfare.html', rows=rows, emps=emps, companies=all_companies(), sel=selected_company())

@app.route('/welfare/add', methods=['POST'])
@login_required
def welfare_add():
    f = request.form
    eid = f.get('employee_id') or _eid_filter()
    if not eid:
        flash('직원을 선택하세요.'); return redirect(url_for('welfare'))
    db = get_db()
    db.execute(
        "INSERT INTO welfare_events(employee_id,event_type,event_date,amount,memo) VALUES(?,?,?,?,?)",
        (eid, f['event_type'], f['event_date'], int(f.get('amount') or 0), f.get('memo')))
    db.commit(); db.close()
    flash('복리후생 내역이 등록되었습니다.')
    return redirect(url_for('welfare'))

@app.route('/welfare/<int:wid>/delete', methods=['POST'])
@login_required
def welfare_delete(wid):
    db = get_db()
    db.execute("DELETE FROM welfare_events WHERE id=?", (wid,))
    db.commit(); db.close()
    return redirect(url_for('welfare'))

# ── 교육관리 ──────────────────────────────────────────────────────────────────
@app.route('/education')
@login_required
def education():
    cid = _cid_filter()
    eid = _eid_filter()
    db = get_db()
    emps_q = "SELECT e.id, e.name, e.dept, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
    emps_p = []
    if cid:
        emps_q += " AND e.company_id=?"; emps_p = [cid]
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    q = ("SELECT ed.*, e.name as emp_name, c.name as co_name "
         "FROM education_requests ed JOIN employees e ON ed.employee_id=e.id "
         "JOIN companies c ON e.company_id=c.id WHERE 1=1")
    p = []
    if eid:
        q += " AND ed.employee_id=?"; p = [eid]
    elif cid:
        q += " AND e.company_id=?"; p = [cid]
    rows = db.execute(q + " ORDER BY ed.created_at DESC LIMIT 100", p).fetchall()
    db.close()
    return render_template('education.html', rows=rows, emps=emps, companies=all_companies(), sel=selected_company())

@app.route('/education/add', methods=['POST'])
@login_required
def education_add():
    f = request.form
    eid = f.get('employee_id') or _eid_filter()
    if not eid:
        flash('직원을 선택하세요.'); return redirect(url_for('education'))
    db = get_db()
    db.execute(
        "INSERT INTO education_requests(employee_id,title,category,institution,start_date,end_date,cost,memo) VALUES(?,?,?,?,?,?,?,?)",
        (eid, f['title'], f.get('category','직무교육'), f.get('institution'),
         f.get('start_date'), f.get('end_date'), int(f.get('cost') or 0), f.get('memo')))
    db.commit(); db.close()
    flash('교육신청이 등록되었습니다.')
    return redirect(url_for('education'))

@app.route('/education/<int:eid2>/status', methods=['POST'])
@login_required
def education_status(eid2):
    db = get_db()
    db.execute("UPDATE education_requests SET status=? WHERE id=?", (request.form.get('status','승인'), eid2))
    db.commit(); db.close()
    return redirect(url_for('education'))

@app.route('/education/<int:eid2>/delete', methods=['POST'])
@login_required
def education_delete(eid2):
    db = get_db()
    db.execute("DELETE FROM education_requests WHERE id=?", (eid2,))
    db.commit(); db.close()
    return redirect(url_for('education'))

# ── 성과관리 ──────────────────────────────────────────────────────────────────
@app.route('/performance')
@login_required
def performance():
    cid = _cid_filter()
    eid = _eid_filter()
    year = int(request.args.get('year', date.today().year))
    db = get_db()
    emps_q = "SELECT e.id, e.name, e.dept, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
    emps_p = []
    if cid:
        emps_q += " AND e.company_id=?"; emps_p = [cid]
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    q = ("SELECT pg.*, e.name as emp_name, c.name as co_name "
         "FROM performance_goals pg JOIN employees e ON pg.employee_id=e.id "
         "JOIN companies c ON e.company_id=c.id WHERE pg.year=?")
    p = [year]
    if eid:
        q += " AND pg.employee_id=?"; p.append(eid)
    elif cid:
        q += " AND e.company_id=?"; p.append(cid)
    rows = db.execute(q + " ORDER BY e.name, pg.id", p).fetchall()
    db.close()
    return render_template('performance.html', rows=rows, emps=emps, year=year,
        companies=all_companies(), sel=selected_company())

@app.route('/performance/add', methods=['POST'])
@login_required
def performance_add():
    f = request.form
    eid = f.get('employee_id') or _eid_filter()
    if not eid:
        flash('직원을 선택하세요.'); return redirect(url_for('performance'))
    db = get_db()
    db.execute(
        "INSERT INTO performance_goals(employee_id,year,goal,category,weight,memo) VALUES(?,?,?,?,?,?)",
        (eid, f.get('year', date.today().year), f['goal'],
         f.get('category','업무'), int(f.get('weight') or 100), f.get('memo')))
    db.commit(); db.close()
    flash('목표가 등록되었습니다.')
    return redirect(url_for('performance'))

@app.route('/performance/<int:pid>/score', methods=['POST'])
@login_required
def performance_score(pid):
    db = get_db()
    db.execute("UPDATE performance_goals SET score=?,status=? WHERE id=?",
               (int(request.form.get('score') or 0), request.form.get('status','완료'), pid))
    db.commit(); db.close()
    return redirect(url_for('performance'))

@app.route('/performance/<int:pid>/delete', methods=['POST'])
@login_required
def performance_delete(pid):
    db = get_db()
    db.execute("DELETE FROM performance_goals WHERE id=?", (pid,))
    db.commit(); db.close()
    return redirect(url_for('performance'))

# ── 고충관리 ──────────────────────────────────────────────────────────────────
@app.route('/grievance')
@login_required
def grievance():
    cid = _cid_filter()
    eid = _eid_filter()
    db = get_db()
    emps_q = "SELECT e.id, e.name, e.dept, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
    emps_p = []
    if cid:
        emps_q += " AND e.company_id=?"; emps_p = [cid]
    emps = db.execute(emps_q + " ORDER BY c.name, e.name", emps_p).fetchall()

    q = ("SELECT gr.*, e.name as emp_name, c.name as co_name "
         "FROM grievance_requests gr JOIN employees e ON gr.employee_id=e.id "
         "JOIN companies c ON e.company_id=c.id WHERE 1=1")
    p = []
    if eid:
        q += " AND gr.employee_id=?"; p = [eid]
    elif cid:
        q += " AND e.company_id=?"; p = [cid]
    rows = db.execute(q + " ORDER BY gr.created_at DESC LIMIT 100", p).fetchall()
    db.close()
    return render_template('grievance.html', rows=rows, emps=emps, companies=all_companies(), sel=selected_company())

@app.route('/grievance/add', methods=['POST'])
@login_required
def grievance_add():
    f = request.form
    eid = f.get('employee_id') or _eid_filter()
    if not eid:
        flash('직원을 선택하세요.'); return redirect(url_for('grievance'))
    db = get_db()
    db.execute(
        "INSERT INTO grievance_requests(employee_id,category,title,content,is_anonymous) VALUES(?,?,?,?,?)",
        (eid, f.get('category','일반고충'), f['title'], f.get('content'),
         1 if f.get('is_anonymous') else 0))
    db.commit(); db.close()
    flash('고충신청이 접수되었습니다.')
    return redirect(url_for('grievance'))

@app.route('/grievance/<int:gid>/respond', methods=['POST'])
@login_required
def grievance_respond(gid):
    db = get_db()
    db.execute("UPDATE grievance_requests SET response=?,status=? WHERE id=?",
               (request.form.get('response'), request.form.get('status','처리중'), gid))
    db.commit(); db.close()
    return redirect(url_for('grievance'))

@app.route('/grievance/<int:gid>/delete', methods=['POST'])
@login_required
def grievance_delete(gid):
    db = get_db()
    db.execute("DELETE FROM grievance_requests WHERE id=?", (gid,))
    db.commit(); db.close()
    return redirect(url_for('grievance'))

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  HR Management System  http://127.0.0.1:5050")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5050, debug=False)
