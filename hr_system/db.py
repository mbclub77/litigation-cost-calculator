#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3, os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hr.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        biz_no TEXT,
        ceo TEXT,
        address TEXT,
        phone TEXT,
        industry TEXT,
        emp_count INTEGER DEFAULT 0,
        contract_date TEXT,
        memo TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        name TEXT NOT NULL,
        emp_no TEXT,
        dept TEXT,
        position TEXT,
        hire_date TEXT,
        birth_date TEXT,
        phone TEXT,
        email TEXT,
        emp_type TEXT DEFAULT '정규직',
        status TEXT DEFAULT '재직',
        base_salary INTEGER DEFAULT 0,
        memo TEXT
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        work_date TEXT NOT NULL,
        check_in TEXT,
        check_out TEXT,
        work_hours REAL DEFAULT 0,
        overtime_hours REAL DEFAULT 0,
        memo TEXT
    );
    CREATE TABLE IF NOT EXISTS leave_balance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        year INTEGER NOT NULL,
        total_days REAL DEFAULT 0,
        used_days REAL DEFAULT 0,
        UNIQUE(employee_id, year)
    );
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        leave_type TEXT DEFAULT '연차',
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        days REAL DEFAULT 1,
        reason TEXT,
        status TEXT DEFAULT '대기',
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS salary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        base INTEGER DEFAULT 0,
        overtime_pay INTEGER DEFAULT 0,
        bonus INTEGER DEFAULT 0,
        allowance INTEGER DEFAULT 0,
        income_tax INTEGER DEFAULT 0,
        health_ins INTEGER DEFAULT 0,
        employ_ins INTEGER DEFAULT 0,
        pension INTEGER DEFAULT 0,
        net_pay INTEGER DEFAULT 0,
        memo TEXT,
        UNIQUE(employee_id, year, month)
    );
    CREATE TABLE IF NOT EXISTS consultations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        title TEXT NOT NULL,
        category TEXT DEFAULT '일반',
        content TEXT,
        priority TEXT DEFAULT '보통',
        status TEXT DEFAULT '접수',
        response TEXT,
        created_at TEXT DEFAULT (date('now','localtime')),
        resolved_at TEXT
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'company',
        company_id INTEGER,
        name TEXT DEFAULT '',
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS allowance_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id),
        code TEXT,
        name TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        tax_type TEXT DEFAULT '전액과세',
        pay_type TEXT DEFAULT '고정',
        memo TEXT,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS deduction_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id),
        code TEXT,
        name TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        memo TEXT,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS severance_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        retire_date TEXT,
        service_days INTEGER DEFAULT 0,
        avg_daily_wage REAL DEFAULT 0,
        three_month_wages INTEGER DEFAULT 0,
        three_month_days INTEGER DEFAULT 0,
        severance_pay INTEGER DEFAULT 0,
        memo TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id),
        title TEXT NOT NULL,
        content TEXT,
        category TEXT DEFAULT '일반',
        is_pinned INTEGER DEFAULT 0,
        created_by TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS trip_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        destination TEXT NOT NULL,
        purpose TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        days INTEGER DEFAULT 1,
        transport TEXT DEFAULT '자가용',
        budget INTEGER DEFAULT 0,
        status TEXT DEFAULT '대기',
        memo TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS welfare_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        event_type TEXT NOT NULL,
        event_date TEXT NOT NULL,
        amount INTEGER DEFAULT 0,
        status TEXT DEFAULT '대기',
        memo TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS education_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        title TEXT NOT NULL,
        category TEXT DEFAULT '직무교육',
        institution TEXT,
        start_date TEXT,
        end_date TEXT,
        cost INTEGER DEFAULT 0,
        status TEXT DEFAULT '대기',
        memo TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS performance_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        year INTEGER NOT NULL,
        goal TEXT NOT NULL,
        category TEXT DEFAULT '업무',
        weight INTEGER DEFAULT 100,
        score INTEGER DEFAULT 0,
        status TEXT DEFAULT '진행중',
        memo TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS grievance_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(id),
        category TEXT DEFAULT '일반고충',
        title TEXT NOT NULL,
        content TEXT,
        is_anonymous INTEGER DEFAULT 0,
        status TEXT DEFAULT '접수',
        response TEXT,
        created_at TEXT DEFAULT (date('now','localtime'))
    );
    """)
    conn.commit()

    # Migrations — each wrapped individually so one failure doesn't block others
    migrations = [
        "ALTER TABLE employees ADD COLUMN photo TEXT",
        "ALTER TABLE users ADD COLUMN employee_id INTEGER",
        "ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'",
        "ALTER TABLE salary ADD COLUMN allowance_detail TEXT",
        "ALTER TABLE salary ADD COLUMN work_days INTEGER DEFAULT 0",
        "ALTER TABLE salary ADD COLUMN total_hours REAL DEFAULT 0",
        "ALTER TABLE attendance ADD COLUMN late_minutes INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass

    # 최초 관리자 계정 생성 (admin / admin1234)
    if not conn.execute("SELECT id FROM users WHERE username='admin'").fetchone():
        from werkzeug.security import generate_password_hash
        conn.execute(
            "INSERT INTO users(username,password_hash,role,name) VALUES(?,?,?,?)",
            ('admin', generate_password_hash('admin1234'), 'admin', '관리자')
        )
        conn.commit()
    conn.close()

def calc_annual_leave(hire_date_str):
    try:
        hire = date.fromisoformat(hire_date_str)
    except Exception:
        return 15
    today = date.today()
    years = (today - hire).days // 365
    if years < 1:
        return min((today - hire).days // 30, 11)
    return min(15 + (years - 1) // 2, 25)

def calc_work_hours(total_h):
    """근로기준법 제54조 휴게시간 자동 공제
    total_h >= 8h -> 1h 휴게, >= 4h -> 30분 휴게, < 4h -> 휴게 없음
    Returns (regular_hours, overtime_hours, rest_hours)
    """
    if total_h >= 8:
        rest = 1.0
    elif total_h >= 4:
        rest = 0.5
    else:
        rest = 0.0
    actual = max(0, total_h - rest)
    regular = round(min(actual, 8), 2)
    overtime = round(max(0, actual - 8), 2)
    return regular, overtime, round(rest, 2)
