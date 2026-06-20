#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from db import get_db, init_db, calc_annual_leave
from datetime import date
import os, traceback, logging

logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error.log'),
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s %(message)s'
)

_BASE = os.path.dirname(os.path.abspath(__file__))

# templates 폴더가 있으면 그걸 쓰고, 없으면 현재 폴더에서 직접 찾음
def _find_folder(name, marker_file):
    sub = os.path.join(_BASE, name)
    if os.path.isfile(os.path.join(sub, marker_file)):
        return sub
    if os.path.isfile(os.path.join(_BASE, marker_file)):
        return _BASE
    return sub  # 기본값

_tmpl_dir   = _find_folder('templates', 'dashboard.html')
_static_dir = _find_folder('static',    'style.css')

app = Flask(__name__,
            template_folder=_tmpl_dir,
            static_folder=_static_dir)
app.secret_key = 'hr-system-secret-2024'

@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    logging.error(tb)
    return f"<pre style='color:red;padding:20px'><b>오류 발생:</b>\n{tb}</pre>", 500

@app.before_request
def setup():
    init_db()

def selected_company():
    cid = session.get('company_id')
    if not cid:
        return None
    db = get_db()
    c = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
    db.close()
    return c

def all_companies():
    db = get_db()
    rows = db.execute("SELECT * FROM companies ORDER BY name").fetchall()
    db.close()
    return rows

# ── 대시보드 ─────────────────────────────────────────────────────────────────
@app.route('/')
def dashboard():
    db = get_db()
    total_co = db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_emp = db.execute("SELECT COUNT(*) FROM employees WHERE status='재직'").fetchone()[0]
    this_month = date.today().strftime('%Y-%m')
    consult_cnt = db.execute(
        "SELECT COUNT(*) FROM consultations WHERE created_at LIKE ?", (this_month+'%',)
    ).fetchone()[0]
    recent = db.execute(
        "SELECT c.*, co.name as co_name FROM consultations c "
        "JOIN companies co ON c.company_id=co.id ORDER BY c.created_at DESC LIMIT 6"
    ).fetchall()
    co_stats = db.execute(
        "SELECT co.name, COUNT(e.id) as cnt FROM companies co "
        "LEFT JOIN employees e ON e.company_id=co.id AND e.status='재직' "
        "GROUP BY co.id ORDER BY cnt DESC"
    ).fetchall()
    db.close()
    return render_template('dashboard.html',
        total_co=total_co, total_emp=total_emp, consult_cnt=consult_cnt,
        recent=recent, co_stats=co_stats,
        companies=all_companies(), sel=selected_company())

# ── 회사 선택 ─────────────────────────────────────────────────────────────────
@app.route('/select_company/<int:cid>')
def select_company(cid):
    session['company_id'] = cid
    return redirect(request.referrer or url_for('dashboard'))

# ── 회사 관리 ─────────────────────────────────────────────────────────────────
@app.route('/companies')
def companies():
    db = get_db()
    rows = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM employees WHERE company_id=c.id AND status='재직') as emp_cnt "
        "FROM companies c ORDER BY c.name"
    ).fetchall()
    db.close()
    return render_template('companies.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/companies/add', methods=['POST'])
def company_add():
    f = request.form
    db = get_db()
    db.execute(
        "INSERT INTO companies(name,biz_no,ceo,address,phone,industry,contract_date,memo) VALUES(?,?,?,?,?,?,?,?)",
        (f['name'],f.get('biz_no'),f.get('ceo'),f.get('address'),f.get('phone'),
         f.get('industry'),f.get('contract_date'),f.get('memo'))
    )
    db.commit(); db.close()
    flash('회사가 등록되었습니다.')
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/edit', methods=['POST'])
def company_edit(cid):
    f = request.form
    db = get_db()
    db.execute(
        "UPDATE companies SET name=?,biz_no=?,ceo=?,address=?,phone=?,industry=?,contract_date=?,memo=? WHERE id=?",
        (f['name'],f.get('biz_no'),f.get('ceo'),f.get('address'),f.get('phone'),
         f.get('industry'),f.get('contract_date'),f.get('memo'),cid)
    )
    db.commit(); db.close()
    flash('수정되었습니다.')
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/delete', methods=['POST'])
def company_delete(cid):
    db = get_db()
    db.execute("DELETE FROM companies WHERE id=?", (cid,))
    db.commit(); db.close()
    if session.get('company_id') == cid:
        session.pop('company_id', None)
    return redirect(url_for('companies'))

@app.route('/companies/<int:cid>/json')
def company_json(cid):
    db = get_db()
    row = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 인사정보 관리 ─────────────────────────────────────────────────────────────
@app.route('/employees')
def employees():
    cid = session.get('company_id')
    db = get_db()
    if cid:
        rows = db.execute("SELECT e.*, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id WHERE e.company_id=? ORDER BY e.name", (cid,)).fetchall()
    else:
        rows = db.execute("SELECT e.*, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id ORDER BY c.name, e.name").fetchall()
    db.close()
    return render_template('employees.html', rows=rows, companies=all_companies(), sel=selected_company())

@app.route('/employees/add', methods=['POST'])
def employee_add():
    f = request.form
    db = get_db()
    db.execute(
        "INSERT INTO employees(company_id,name,emp_no,dept,position,hire_date,birth_date,phone,email,emp_type,status,base_salary,memo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f['company_id'],f['name'],f.get('emp_no'),f.get('dept'),f.get('position'),
         f.get('hire_date'),f.get('birth_date'),f.get('phone'),f.get('email'),
         f.get('emp_type','정규직'),f.get('status','재직'),
         int(f.get('base_salary') or 0),f.get('memo'))
    )
    db.commit(); db.close()
    flash('직원이 등록되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/edit', methods=['POST'])
def employee_edit(eid):
    f = request.form
    db = get_db()
    db.execute(
        "UPDATE employees SET name=?,emp_no=?,dept=?,position=?,hire_date=?,birth_date=?,phone=?,email=?,emp_type=?,status=?,base_salary=?,memo=? WHERE id=?",
        (f['name'],f.get('emp_no'),f.get('dept'),f.get('position'),f.get('hire_date'),
         f.get('birth_date'),f.get('phone'),f.get('email'),f.get('emp_type'),
         f.get('status'),int(f.get('base_salary') or 0),f.get('memo'),eid)
    )
    db.commit(); db.close()
    flash('수정되었습니다.')
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/delete', methods=['POST'])
def employee_delete(eid):
    db = get_db()
    db.execute("DELETE FROM employees WHERE id=?", (eid,))
    db.commit(); db.close()
    return redirect(url_for('employees'))

@app.route('/employees/<int:eid>/json')
def employee_json(eid):
    db = get_db()
    row = db.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 출퇴근 관리 ──────────────────────────────────────────────────────────────
@app.route('/attendance')
def attendance():
    cid = session.get('company_id')
    year = request.args.get('year', date.today().year)
    month = request.args.get('month', date.today().month)
    ym = f"{year}-{int(month):02d}"
    db = get_db()
    q = """SELECT a.*, e.name as emp_name, e.dept, c.name as co_name
           FROM attendance a
           JOIN employees e ON a.employee_id=e.id
           JOIN companies c ON e.company_id=c.id
           WHERE a.work_date LIKE ?"""
    params = [ym+'%']
    if cid:
        q += " AND e.company_id=?"
        params.append(cid)
    q += " ORDER BY a.work_date DESC, e.name"
    rows = db.execute(q, params).fetchall()
    emps = db.execute(
        "SELECT e.id, e.name, c.name as co_name FROM employees e JOIN companies c ON e.company_id=c.id" +
        (" WHERE e.company_id=?" if cid else "") + " AND e.status='재직' ORDER BY c.name, e.name",
        (cid,) if cid else ()
    ).fetchall()
    db.close()
    return render_template('attendance.html', rows=rows, emps=emps,
        year=int(year), month=int(month),
        companies=all_companies(), sel=selected_company())

@app.route('/attendance/add', methods=['POST'])
def attendance_add():
    f = request.form
    ci = f.get('check_in','')
    co = f.get('check_out','')
    wh = ot = 0
    if ci and co:
        from datetime import datetime
        t1 = datetime.strptime(ci,'%H:%M')
        t2 = datetime.strptime(co,'%H:%M')
        total = (t2-t1).seconds/3600
        wh = min(total, 8)
        ot = max(0, total-8)
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO attendance(employee_id,work_date,check_in,check_out,work_hours,overtime_hours,memo) VALUES(?,?,?,?,?,?,?)",
        (f['employee_id'],f['work_date'],ci,co,round(wh,2),round(ot,2),f.get('memo'))
    )
    db.commit(); db.close()
    flash('출퇴근이 기록되었습니다.')
    return redirect(url_for('attendance', year=f['work_date'][:4], month=int(f['work_date'][5:7])))

@app.route('/attendance/<int:aid>/delete', methods=['POST'])
def attendance_delete(aid):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE id=?", (aid,))
    db.commit(); db.close()
    return redirect(url_for('attendance'))

# ── 연차 관리 ─────────────────────────────────────────────────────────────────
@app.route('/leave')
def leave():
    cid = session.get('company_id')
    year = int(request.args.get('year', date.today().year))
    db = get_db()
    q = """SELECT e.id, e.name, e.dept, e.hire_date, c.name as co_name,
           COALESCE(lb.total_days,0) as total_days,
           COALESCE(lb.used_days,0) as used_days
           FROM employees e
           JOIN companies c ON e.company_id=c.id
           LEFT JOIN leave_balance lb ON lb.employee_id=e.id AND lb.year=?
           WHERE e.status='재직'"""
    params = [year]
    if cid:
        q += " AND e.company_id=?"
        params.append(cid)
    q += " ORDER BY c.name, e.name"
    emps = db.execute(q, params).fetchall()
    reqs = db.execute(
        """SELECT lr.*, e.name as emp_name, c.name as co_name
           FROM leave_requests lr
           JOIN employees e ON lr.employee_id=e.id
           JOIN companies c ON e.company_id=c.id
           WHERE lr.start_date LIKE ?""" +
        (" AND e.company_id=?" if cid else "") +
        " ORDER BY lr.created_at DESC",
        ([str(year)+'%', cid] if cid else [str(year)+'%'])
    ).fetchall()
    db.close()
    return render_template('leave.html', emps=emps, reqs=reqs, year=year,
        companies=all_companies(), sel=selected_company(),
        calc_annual_leave=calc_annual_leave)

@app.route('/leave/balance/set', methods=['POST'])
def leave_balance_set():
    f = request.form
    db = get_db()
    db.execute(
        "INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,?,?) "
        "ON CONFLICT(employee_id,year) DO UPDATE SET total_days=excluded.total_days",
        (f['employee_id'], f['year'], float(f['total_days']), 0)
    )
    db.commit(); db.close()
    return redirect(url_for('leave', year=f['year']))

@app.route('/leave/request/add', methods=['POST'])
def leave_request_add():
    f = request.form
    days = float(f.get('days', 1))
    db = get_db()
    db.execute(
        "INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,?,?,?,?,?)",
        (f['employee_id'], f.get('leave_type','연차'), f['start_date'], f['end_date'], days, f.get('reason'))
    )
    db.commit(); db.close()
    flash('연차 신청이 접수되었습니다.')
    return redirect(url_for('leave'))

@app.route('/leave/request/<int:rid>/approve', methods=['POST'])
def leave_approve(rid):
    db = get_db()
    req = db.execute("SELECT * FROM leave_requests WHERE id=?", (rid,)).fetchone()
    if req:
        db.execute("UPDATE leave_requests SET status='승인' WHERE id=?", (rid,))
        db.execute(
            "INSERT INTO leave_balance(employee_id,year,total_days,used_days) VALUES(?,?,0,?) "
            "ON CONFLICT(employee_id,year) DO UPDATE SET used_days=used_days+excluded.used_days",
            (req['employee_id'], req['start_date'][:4], req['days'])
        )
        db.commit()
    db.close()
    return redirect(url_for('leave'))

@app.route('/leave/request/<int:rid>/reject', methods=['POST'])
def leave_reject(rid):
    db = get_db()
    db.execute("UPDATE leave_requests SET status='반려' WHERE id=?", (rid,))
    db.commit(); db.close()
    return redirect(url_for('leave'))

# ── 보수 관리 ─────────────────────────────────────────────────────────────────
@app.route('/salary')
def salary():
    cid = session.get('company_id')
    year = int(request.args.get('year', date.today().year))
    month = int(request.args.get('month', date.today().month))
    db = get_db()
    q = """SELECT s.*, e.name as emp_name, e.dept, c.name as co_name
           FROM salary s
           JOIN employees e ON s.employee_id=e.id
           JOIN companies c ON e.company_id=c.id
           WHERE s.year=? AND s.month=?"""
    params = [year, month]
    if cid:
        q += " AND e.company_id=?"
        params.append(cid)
    q += " ORDER BY c.name, e.name"
    rows = db.execute(q, params).fetchall()
    emps = db.execute(
        "SELECT e.id, e.name, e.base_salary, c.name as co_name FROM employees e "
        "JOIN companies c ON e.company_id=c.id WHERE e.status='재직'" +
        (" AND e.company_id=?" if cid else "") + " ORDER BY c.name, e.name",
        (cid,) if cid else ()
    ).fetchall()
    total = sum(r['net_pay'] for r in rows)
    db.close()
    return render_template('salary.html', rows=rows, emps=emps,
        year=year, month=month, total=total,
        companies=all_companies(), sel=selected_company())

@app.route('/salary/add', methods=['POST'])
def salary_add():
    f = request.form
    def i(k): return int(f.get(k) or 0)
    gross = i('base') + i('overtime_pay') + i('bonus') + i('allowance')
    deduct = i('income_tax') + i('health_ins') + i('employ_ins') + i('pension')
    net = gross - deduct
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO salary(employee_id,year,month,base,overtime_pay,bonus,allowance,"
        "income_tax,health_ins,employ_ins,pension,net_pay,memo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f['employee_id'],f['year'],f['month'],i('base'),i('overtime_pay'),i('bonus'),i('allowance'),
         i('income_tax'),i('health_ins'),i('employ_ins'),i('pension'),net,f.get('memo'))
    )
    db.commit(); db.close()
    flash('급여가 등록되었습니다.')
    return redirect(url_for('salary', year=f['year'], month=f['month']))

@app.route('/salary/<int:sid>/delete', methods=['POST'])
def salary_delete(sid):
    db = get_db()
    db.execute("DELETE FROM salary WHERE id=?", (sid,))
    db.commit(); db.close()
    return redirect(url_for('salary'))

@app.route('/salary/<int:sid>/json')
def salary_json(sid):
    db = get_db()
    row = db.execute("SELECT * FROM salary WHERE id=?", (sid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

# ── 노무자문의뢰 ──────────────────────────────────────────────────────────────
@app.route('/consultation')
def consultation():
    cid = session.get('company_id')
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
    q += " ORDER BY c.created_at DESC"
    rows = db.execute(q, params).fetchall()
    db.close()
    return render_template('consultation.html', rows=rows, status_f=status_f,
        companies=all_companies(), sel=selected_company())

@app.route('/consultation/add', methods=['POST'])
def consultation_add():
    f = request.form
    db = get_db()
    db.execute(
        "INSERT INTO consultations(company_id,title,category,content,priority) VALUES(?,?,?,?,?)",
        (f['company_id'],f['title'],f.get('category','일반'),f.get('content'),f.get('priority','보통'))
    )
    db.commit(); db.close()
    flash('자문의뢰가 등록되었습니다.')
    return redirect(url_for('consultation'))

@app.route('/consultation/<int:cid>/update', methods=['POST'])
def consultation_update(cid):
    f = request.form
    resolved = date.today().isoformat() if f.get('status') == '완료' else None
    db = get_db()
    db.execute(
        "UPDATE consultations SET status=?,response=?,resolved_at=COALESCE(?,resolved_at) WHERE id=?",
        (f.get('status'), f.get('response'), resolved, cid)
    )
    db.commit(); db.close()
    return redirect(url_for('consultation'))

@app.route('/consultation/<int:cid>/json')
def consultation_json(cid):
    db = get_db()
    row = db.execute("SELECT * FROM consultations WHERE id=?", (cid,)).fetchone()
    db.close()
    return jsonify(dict(row)) if row else ('', 404)

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  HR Management System")
    print("  http://127.0.0.1:5050")
    print("  Ctrl+C to stop")
    print("=" * 50)
    app.run(host='127.0.0.1', port=5050, debug=False)
