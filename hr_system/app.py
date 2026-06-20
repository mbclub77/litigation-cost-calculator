#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, init_db, calc_annual_leave
from datetime import date
import os, traceback, logging

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
        self.id      = row['id']
        self.username= row['username']
        self.role    = row['role']
        self.company_id = row['company_id']
        self.name    = row['name'] or row['username']
    @property
    def is_admin(self): return self.role == 'admin'

@login_manager.user_loader
def load_user(uid):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return User(row) if row else None

@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    logging.error(tb)
    return f"<pre style='color:red;padding:20px'><b>오류:</b>\n{tb}</pre>", 500

@app.before_request
def setup():
    init_db()
    if current_user.is_authenticated and not current_user.is_admin:
        session['company_id'] = current_user.company_id

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def _cid_filter():
    if current_user.is_authenticated and not current_user.is_admin:
        return current_user.company_id
    return session.get('company_id')

def selected_company():
    cid = _cid_filter()
    if not cid: return None
    db = get_db(); c = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone(); db.close()
    return c

def all_companies():
    db = get_db()
    if current_user.is_authenticated and not current_user.is_admin:
        rows = db.execute("SELECT * FROM companies WHERE id=?", (current_user.company_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM companies ORDER BY name").fetchall()
    db.close()
    return rows

# ── 로그인 / 로그아웃 ─────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login_page():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username=?", (request.form.get('username','').strip(),)).fetchone()
        db.close()
        if row and check_password_hash(row['password_hash'], request.form.get('password','')):
            user = User(row)
            login_user(user, remember=True)
            if not user.is_admin: session['company_id'] = user.company_id
            return redirect(url_for('dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); session.clear()
    return redirect(url_for('login_page'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old, new = request.form.get('old_password',''), request.form.get('new_password','')
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (current_user.id,)).fetchone()
    if row and check_password_hash(row['password_hash'], old) and new:
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), current_user.id))
        db.commit(); flash('비밀번호가 변경되었습니다.')
    else:
        flash('현재 비밀번호가 올바르지 않습니다.')
    db.close()
    return redirect(url_for('dashboard'))

# ── 계정 관리 (관리자 전용) ───────────────────────────────────────────────────
@app.route('/users')
@login_required
def users():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    db = get_db()
    rows = db.execute("SELECT u.*, c.name as co_name FROM users u LEFT JOIN companies c ON u.company_id=c.id ORDER BY u.role DESC, u.username").fetchall()
    db.close()
    return render_template('users.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/users/add', methods=['POST'])
@login_required
def user_add():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    f = request.form
    db = get_db()
    try:
        db.execute("INSERT INTO users(username,password_hash,role,company_id,name) VALUES(?,?,?,?,?)",
            (f['username'], generate_password_hash(f['password']),
             f.get('role','company'), f.get('company_id') or None, f.get('name','')))
        db.commit(); flash('계정이 생성되었습니다.')
    except Exception as e: flash(f'오류: {e}')
    db.close()
    return redirect(url_for('users'))

@app.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
def user_delete(uid):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    db = get_db()
    db.execute("DELETE FROM users WHERE id=? AND username!='admin'", (uid,))
    db.commit(); db.close()
    return redirect(url_for('users'))

@app.route('/users/<int:uid>/reset_pw', methods=['POST'])
@login_required
def user_reset_pw(uid):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    pw = request.form.get('password','')
    if pw:
        db = get_db()
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(pw), uid))
        db.commit(); db.close(); flash('비밀번호가 변경되었습니다.')
    return redirect(url_for('users'))

# ── 회사 선택 ─────────────────────────────────────────────────────────────────
@app.route('/select_company/<int:cid>')
@login_required
def select_company(cid):
    if current_user.is_admin: session['company_id'] = cid if cid else None
    return redirect(request.referrer or url_for('dashboard'))

# ── 대시보드 ──────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    cid = _cid_filter()
    db = get_db()
    total_co  = db.execute("SELECT COUNT(*) FROM companies" + (" WHERE id=?" if cid else ""), ([cid] if cid else [])).fetchone()[0]
    total_emp = db.execute("SELECT COUNT(*) FROM employees e WHERE e.status='재직'" + (" AND e.company_id=?" if cid else ""), ([cid] if cid else [])).fetchone()[0]
    this_month = date.today().strftime('%Y-%m')
    consult_cnt = db.execute("SELECT COUNT(*) FROM consultations WHERE created_at LIKE ?" + (" AND company_id=?" if cid else ""), ([this_month+'%', cid] if cid else [this_month+'%'])).fetchone()[0]
    recent = db.execute(
        "SELECT c.*, co.name as co_name FROM consultations c JOIN companies co ON c.company_id=co.id" +
        (" WHERE c.company_id=?" if cid else "") + " ORDER BY c.created_at DESC LIMIT 6",
        ([cid] if cid else [])).fetchall()
    co_stats = db.execute(
        "SELECT co.id, co.name, COUNT(e.id) as cnt FROM companies co "
        "LEFT JOIN employees e ON e.company_id=co.id AND e.status='재직'" +
        (" WHERE co.id=?" if cid else "") + " GROUP BY co.id ORDER BY cnt DESC",
        ([cid] if cid else [])).fetchall()
    db.close()
    return render_template('dashboard.html', total_co=total_co, total_emp=total_emp,
        consult_cnt=consult_cnt, recent=recent, co_stats=co_stats,
        companies=all_companies(), sel=selected_company())

# ── 회사 관리 ─────────────────────────────────────────────────────────────────
@app.route('/companies')
@login_required
def companies():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    db = get_db()
    rows = db.execute("SELECT c.*, (SELECT COUNT(*) FROM employees WHERE company_id=c.id AND status='재직') as emp_cnt FROM companies c ORDER BY c.name").fetchall()
    db.close()
    return render_template('companies.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/companies/add', methods=['POST'])
@login_required
def company_add():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    f = request.form; db = get_db()
    db.execute("INSERT INTO companies(name,biz_no,ceo,address,phone,industry,contract_date,memo) VALUES(?,?,?,?,?,?,?,?)",
        (f['name'],f.get('biz_no'),f.get('ceo'),f.get('address'),f.get('phone'),f.get('industry'),f.get('contract_date'),f.get('memo')))
    db.commit(); db.close(); flash('회사가 등록되었습니다.')
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/edit', methods=['POST'])
@login_required
def company_edit(cid):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    f = request.form; db = get_db()
    db.execute("UPDATE companies SET name=?,biz_no=?,ceo=?,address=?,phone=?,industry=?,contract_date=?,memo=? WHERE id=?",
        (f['name'],f.get('biz_no'),f.get('ceo'),f.get('address'),f.get('phone'),f.get('industry'),f.get('contract_date'),f.get('memo'),cid))
    db.commit(); db.close(); flash('수정되었습니다.')
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/delete', methods=['POST'])
@login_required
def company_delete(cid):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    db = get_db(); db.execute("DELETE FROM companies WHERE id=?", (cid,)); db.commit(); db.close()
    if session.get('company_id') == cid: session.pop('company_id', None)
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/json')
@login_required
def company_json(cid):
    db = get_db(); row = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone(); db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 인사정보 ──────────────────────────────────────────────────────────────────
@app.route('/employees')
@login_required
def employees():
    cid = _cid_filter(); db = get_db()
    if cid:
        rows = db.execute("SELECT e.*, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.company_id=? ORDER BY e.name", (cid,)).fetchall()
    else:
        rows = db.execute("SELECT e.*, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id ORDER BY c.name, e.name").fetchall()
    db.close()
    return render_template('employees.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/employees/add', methods=['POST'])
@login_required
def employee_add():
    f = request.form; db = get_db()
    co_id = current_user.company_id if not current_user.is_admin else f['company_id']
    db.execute("INSERT INTO employees(company_id,name,emp_no,dept,position,hire_date,birth_date,phone,email,emp_type,status,base_salary,memo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (co_id,f['name'],f.get('emp_no'),f.get('dept'),f.get('position'),f.get('hire_date'),f.get('birth_date'),f.get('phone'),f.get('email'),f.get('emp_type','정규직'),f.get('status','재직'),int(f.get('base_salary') or 0),f.get('memo')))
    db.commit(); db.close(); flash('직원이 등록되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/edit', methods=['POST'])
@login_required
def employee_edit(eid):
    f = request.form; db = get_db()
    db.execute("UPDATE employees SET name=?,emp_no=?,dept=?,position=?,hire_date=?,birth_date=?,phone=?,email=?,emp_type=?,status=?,base_salary=?,memo=? WHERE id=?",
        (f['name'],f.get('emp_no'),f.get('dept'),f.get('position'),f.get('hire_date'),f.get('birth_date'),f.get('phone'),f.get('email'),f.get('emp_type'),f.get('status'),int(f.get('base_salary') or 0),f.get('memo'),eid))
    db.commit(); db.close(); flash('수정되었습니다.')
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
            db.commit(); db.close()
            flash('사진이 등록되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/delete', methods=['POST'])
@login_required
def employee_delete(eid):
    db = get_db(); db.execute("DELETE FROM employees WHERE id=?", (eid,)); db.commit(); db.close()
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/json')
@login_required
def employee_json(eid):
    db = get_db(); row = db.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone(); db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 출퇴근 ────────────────────────────────────────────────────────────────────
@app.route('/attendance')
@login_required
def attendance():
    cid = _cid_filter()
    year  = int(request.args.get('year',  date.today().year))
    month = int(request.args.get('month', date.today().month))
    mode  = request.args.get('mode', 'month')

    ym = f"{year}-{month:02d}"; db = get_db()
    q = ("SELECT a.*, e.name as emp_name, e.dept, c.name as co_name "
         "FROM attendance a JOIN employees e ON a.employee_id=e.id "
         "JOIN companies c ON e.company_id=c.id WHERE a.work_date LIKE ?")
    params = [ym+'%']
    if cid: q += " AND e.company_id=?"; params.append(cid)
    rows = db.execute(q + " ORDER BY a.work_date, e.name", params).fetchall()

    emps = db.execute(
        "SELECT e.id, e.name, c.name as co_name FROM employees e "
        "JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
        + (" AND e.company_id=?" if cid else "") + " ORDER BY c.name, e.name",
        ([cid] if cid else [])).fetchall()

    # Year-mode summaries
    year_monthly, year_emps = [], []
    if mode == 'year':
        ybase = ("FROM attendance a JOIN employees e ON a.employee_id=e.id "
                 "JOIN companies c ON e.company_id=c.id WHERE a.work_date LIKE ?")
        yp = [str(year)+'%']
        if cid: ybase += " AND e.company_id=?"; yp.append(cid)
        year_monthly = db.execute(
            f"SELECT strftime('%m', a.work_date) as mon, COUNT(*) as days, "
            f"SUM(a.work_hours) as total_h, SUM(a.overtime_hours) as total_ot {ybase} "
            f"GROUP BY mon ORDER BY mon", yp).fetchall()
        year_emps = db.execute(
            f"SELECT e.name, e.dept, c.name as co_name, COUNT(*) as days, "
            f"SUM(a.work_hours) as total_h, SUM(a.overtime_hours) as total_ot {ybase} "
            f"GROUP BY e.id ORDER BY c.name, e.name", yp).fetchall()

    db.close()
    return render_template('attendance.html', rows=rows, emps=emps, year=year, month=month,
        mode=mode, year_monthly=year_monthly, year_emps=year_emps,
        companies=all_companies(), sel=selected_company())

@app.route('/attendance/add', methods=['POST'])
@login_required
def attendance_add():
    f = request.form; ci = f.get('check_in',''); co_t = f.get('check_out',''); wh = ot = 0
    if ci and co_t:
        from datetime import datetime
        t1, t2 = datetime.strptime(ci,'%H:%M'), datetime.strptime(co_t,'%H:%M')
        total = (t2-t1).seconds/3600; wh = min(total,8); ot = max(0,total-8)
    db = get_db()
    db.execute("INSERT OR REPLACE INTO attendance(employee_id,work_date,check_in,check_out,work_hours,overtime_hours,memo) VALUES(?,?,?,?,?,?,?)",
        (f['employee_id'],f['work_date'],ci,co_t,round(wh,2),round(ot,2),f.get('memo')))
    db.commit(); db.close(); flash('출퇴근이 기록되었습니다.')
    return redirect(url_for('attendance', year=f['work_date'][:4], month=int(f['work_date'][5:7])))

@app.route('/attendance/<int:aid>/delete', methods=['POST'])
@login_required
def attendance_delete(aid):
    db = get_db(); db.execute("DELETE FROM attendance WHERE id=?", (aid,)); db.commit(); db.close()
    return redirect(url_for('attendance'))

# ── 연차 ──────────────────────────────────────────────────────────────────────
@app.route('/leave')
@login_required
def leave():
    cid = _cid_filter(); year = int(request.args.get('year', date.today().year)); db = get_db()
    emps = db.execute(
        "SELECT e.id,e.name,e.dept,e.hire_date,c.name as co_name,"
        "COALESCE(lb.total_days,0) as total_days,COALESCE(lb.used_days,0) as used_days "
        "FROM employees e JOIN companies c ON e.company_id=c.id "
        "LEFT JOIN leave_balance lb ON lb.employee_id=e.id AND lb.year=? "
        "WHERE e.status='재직'" + (" AND e.company_id=?" if cid else "") + " ORDER BY c.name, e.name",
        ([year, cid] if cid else [year])).fetchall()
    reqs = db.execute(
        "SELECT lr.*, e.name as emp_name, c.name as co_name FROM leave_requests lr "
        "JOIN employees e ON lr.employee_id=e.id JOIN companies c ON e.company_id=c.id "
        "WHERE lr.start_date LIKE ?" + (" AND e.company_id=?" if cid else "") + " ORDER BY lr.created_at DESC",
        ([str(year)+'%', cid] if cid else [str(year)+'%'])).fetchall()
    db.close()
    return render_template('leave.html', emps=emps, reqs=reqs, year=year,
        companies=all_companies(), sel=selected_company(), calc_annual_leave=calc_annual_leave)

@app.route('/leave/auto_assign', methods=['POST'])
@login_required
def leave_auto_assign():
    year = int(request.form.get('year', date.today().year))
    cid = _cid_filter(); db = get_db()
    emps = db.execute(
        "SELECT id, hire_date FROM employees WHERE status='재직'"
        + (" AND company_id=?" if cid else ""), ([cid] if cid else [])).fetchall()
    for e in emps:
        days = calc_annual_leave(e['hire_date'])
        db.execute(
            "INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,?,0) "
            "ON CONFLICT(employee_id,year) DO UPDATE SET total_days=excluded.total_days",
            (e['id'], year, days))
    db.commit(); db.close()
    flash(f'{year}년 법정 연차가 재직 직원에게 자동 부여되었습니다.')
    return redirect(url_for('leave', year=year))

@app.route('/leave/balance/set', methods=['POST'])
@login_required
def leave_balance_set():
    f = request.form; db = get_db()
    db.execute("INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,?,0) ON CONFLICT(employee_id,year) DO UPDATE SET total_days=excluded.total_days",
        (f['employee_id'], f['year'], float(f['total_days'])))
    db.commit(); db.close()
    return redirect(url_for('leave', year=f['year']))

@app.route('/leave/request/add', methods=['POST'])
@login_required
def leave_request_add():
    f = request.form; db = get_db()
    db.execute("INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,?,?,?,?,?)",
        (f['employee_id'],f.get('leave_type','연차'),f['start_date'],f['end_date'],float(f.get('days',1)),f.get('reason')))
    db.commit(); db.close(); flash('연차 신청이 접수되었습니다.')
    return redirect(url_for('leave'))

@app.route('/leave/request/<int:rid>/approve', methods=['POST'])
@login_required
def leave_approve(rid):
    db = get_db(); req = db.execute("SELECT * FROM leave_requests WHERE id=?", (rid,)).fetchone()
    if req:
        db.execute("UPDATE leave_requests SET status='승인' WHERE id=?", (rid,))
        db.execute("INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,0,?) ON CONFLICT(employee_id,year) DO UPDATE SET used_days=used_days+excluded.used_days",
            (req['employee_id'], req['start_date'][:4], req['days']))
        db.commit()
    db.close(); return redirect(url_for('leave'))

@app.route('/leave/request/<int:rid>/reject', methods=['POST'])
@login_required
def leave_reject(rid):
    db = get_db(); db.execute("UPDATE leave_requests SET status='반려' WHERE id=?", (rid,)); db.commit(); db.close()
    return redirect(url_for('leave'))

# ── 보수 ──────────────────────────────────────────────────────────────────────
@app.route('/salary')
@login_required
def salary():
    cid = _cid_filter()
    year  = int(request.args.get('year',  date.today().year))
    month = int(request.args.get('month', date.today().month))
    view  = request.args.get('view', 'month')
    db = get_db()
    rows = db.execute(
        "SELECT s.*, e.name as emp_name, e.dept, e.position, e.emp_no, c.name as co_name "
        "FROM salary s JOIN employees e ON s.employee_id=e.id "
        "JOIN companies c ON e.company_id=c.id "
        "WHERE s.year=? AND s.month=?" + (" AND e.company_id=?" if cid else "") + " ORDER BY c.name, e.name",
        ([year,month,cid] if cid else [year,month])).fetchall()
    emps = db.execute(
        "SELECT e.id,e.name,e.base_salary,c.name as co_name FROM employees e "
        "JOIN companies c ON e.company_id=c.id WHERE e.status='재직'"
        + (" AND e.company_id=?" if cid else "") + " ORDER BY c.name, e.name",
        ([cid] if cid else [])).fetchall()
    annual_rows = []
    if view == 'annual':
        annual_rows = db.execute(
            "SELECT e.id, e.name, e.dept, c.name as co_name, "
            "SUM(s.base+s.overtime_pay+s.bonus+s.allowance) as gross, "
            "SUM(s.income_tax+s.health_ins+s.employ_ins+s.pension) as deductions, "
            "SUM(s.net_pay) as net_total, COUNT(s.id) as months "
            "FROM salary s JOIN employees e ON s.employee_id=e.id "
            "JOIN companies c ON e.company_id=c.id WHERE s.year=?"
            + (" AND e.company_id=?" if cid else "") +
            " GROUP BY e.id ORDER BY c.name, e.name",
            ([year, cid] if cid else [year])).fetchall()
    db.close()
    return render_template('salary.html', rows=rows, emps=emps, year=year, month=month,
        total=sum(r['net_pay'] for r in rows), view=view, annual_rows=annual_rows,
        companies=all_companies(), sel=selected_company())

@app.route('/salary/add', methods=['POST'])
@login_required
def salary_add():
    f = request.form; i = lambda k: int(f.get(k) or 0)
    net = i('base')+i('overtime_pay')+i('bonus')+i('allowance')-i('income_tax')-i('health_ins')-i('employ_ins')-i('pension')
    db = get_db()
    db.execute("INSERT OR REPLACE INTO salary(employee_id,year,month,base,overtime_pay,bonus,allowance,income_tax,health_ins,employ_ins,pension,net_pay,memo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f['employee_id'],f['year'],f['month'],i('base'),i('overtime_pay'),i('bonus'),i('allowance'),i('income_tax'),i('health_ins'),i('employ_ins'),i('pension'),net,f.get('memo')))
    db.commit(); db.close(); flash('급여가 등록되었습니다.')
    return redirect(url_for('salary', year=f['year'], month=f['month']))

@app.route('/salary/<int:sid>/delete', methods=['POST'])
@login_required
def salary_delete(sid):
    db = get_db(); db.execute("DELETE FROM salary WHERE id=?", (sid,)); db.commit(); db.close()
    return redirect(url_for('salary'))

@app.route('/salary/<int:sid>/json')
@login_required
def salary_json(sid):
    db = get_db()
    row = db.execute(
        "SELECT s.*, e.name as emp_name, e.dept, e.position, e.emp_no, "
        "c.name as co_name, c.biz_no, c.address, c.phone as co_phone "
        "FROM salary s JOIN employees e ON s.employee_id=e.id "
        "JOIN companies c ON e.company_id=c.id WHERE s.id=?", (sid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 노무자문 ──────────────────────────────────────────────────────────────────
@app.route('/consultation')
@login_required
def consultation():
    cid = _cid_filter(); status_f = request.args.get('status',''); db = get_db()
    q = "SELECT c.*, co.name as co_name FROM consultations c JOIN companies co ON c.company_id=co.id WHERE 1=1"
    params = []
    if cid: q += " AND c.company_id=?"; params.append(cid)
    if status_f: q += " AND c.status=?"; params.append(status_f)
    rows = db.execute(q + " ORDER BY c.created_at DESC", params).fetchall()
    db.close()
    return render_template('consultation.html', rows=rows, status_f=status_f, companies=all_companies(), sel=selected_company())

@app.route('/consultation/add', methods=['POST'])
@login_required
def consultation_add():
    f = request.form; db = get_db()
    co_id = current_user.company_id if not current_user.is_admin else f['company_id']
    db.execute("INSERT INTO consultations(company_id,title,category,content,priority) VALUES(?,?,?,?,?)",
        (co_id,f['title'],f.get('category','일반'),f.get('content'),f.get('priority','보통')))
    db.commit(); db.close(); flash('자문의뢰가 등록되었습니다.')
    return redirect(url_for('consultation'))

@app.route('/consultation/<int:cid>/update', methods=['POST'])
@login_required
def consultation_update(cid):
    f = request.form; resolved = date.today().isoformat() if f.get('status')=='완료' else None; db = get_db()
    db.execute("UPDATE consultations SET status=?,response=?,resolved_at=COALESCE(?,resolved_at) WHERE id=?",
        (f.get('status'),f.get('response'),resolved,cid))
    db.commit(); db.close()
    return redirect(url_for('consultation'))

@app.route('/consultation/<int:cid>/json')
@login_required
def consultation_json(cid):
    db = get_db(); row = db.execute("SELECT * FROM consultations WHERE id=?", (cid,)).fetchone(); db.close()
    return jsonify(dict(row)) if row else ('', 404)

if __name__ == '__main__':
    init_db()
    print("="*50); print("  HR Management System  http://127.0.0.1:5050"); print("="*50)
    app.run(host='0.0.0.0', port=5050, debug=False)
