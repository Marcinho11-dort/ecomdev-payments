import os
import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE = Path(__file__).parent


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(os.getenv("DB_PATH", str(BASE / "payments.db")))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def run(sql, args=(), one=False, many=False):
    c = conn()
    try:
        cur = c.execute(sql, args)
        c.commit()
        if one:
            r = cur.fetchone()
            return dict(r) if r else None
        if many:
            return [dict(r) for r in cur.fetchall()]
        return cur.lastrowid
    finally:
        c.close()


@asynccontextmanager
async def lifespan(_):
    run("""CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, phone TEXT NOT NULL, group_name TEXT NOT NULL,
        monthly_fee INTEGER NOT NULL CHECK (monthly_fee >= 0))""")
    run("""CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        amount INTEGER NOT NULL CHECK (amount > 0),
        paid_at TEXT NOT NULL)""")
    run("CREATE INDEX IF NOT EXISTS idx_pay ON payments(student_id, paid_at)")
    yield


app = FastAPI(title="Учёт оплат", lifespan=lifespan)


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=3, max_length=30)
    group: str = Field(min_length=1, max_length=100)
    monthly_fee: int = Field(ge=0, description="Месячная сумма, целое число")


class PaymentIn(BaseModel):
    student_id: int
    amount: int = Field(gt=0)
    paid_at: date | None = None  # по умолчанию сегодня


def student_out(r):
    return {"id": r["id"], "name": r["name"], "phone": r["phone"],
            "group": r["group_name"], "monthly_fee": r["monthly_fee"]}


def get_student_or_404(sid):
    r = run("SELECT * FROM students WHERE id=?", (sid,), one=True)
    if not r:
        raise HTTPException(404, "Ученик не найден")
    return r


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE / "static" / "index.html")


# ---- Ученики ----
@app.post("/students", status_code=201)
def create_student(s: StudentIn):
    sid = run("INSERT INTO students(name,phone,group_name,monthly_fee) VALUES(?,?,?,?)",
              (s.name.strip(), s.phone.strip(), s.group.strip(), s.monthly_fee))
    return student_out(get_student_or_404(sid))


@app.get("/students")
def list_students():
    return [student_out(r) for r in run("SELECT * FROM students ORDER BY name", many=True)]


@app.get("/students/{sid}")
def get_student(sid: int):
    return student_out(get_student_or_404(sid))


@app.put("/students/{sid}")
def update_student(sid: int, s: StudentIn):
    get_student_or_404(sid)
    run("UPDATE students SET name=?,phone=?,group_name=?,monthly_fee=? WHERE id=?",
        (s.name.strip(), s.phone.strip(), s.group.strip(), s.monthly_fee, sid))
    return student_out(get_student_or_404(sid))


@app.delete("/students/{sid}", status_code=204)
def delete_student(sid: int):
    get_student_or_404(sid)
    run("DELETE FROM students WHERE id=?", (sid,))  # оплаты удаляются каскадом


# ---- Оплаты ----
@app.post("/payments", status_code=201)
def add_payment(p: PaymentIn):
    get_student_or_404(p.student_id)
    d = (p.paid_at or date.today()).isoformat()
    pid = run("INSERT INTO payments(student_id,amount,paid_at) VALUES(?,?,?)",
              (p.student_id, p.amount, d))
    return {"id": pid, "student_id": p.student_id, "amount": p.amount, "paid_at": d}


@app.get("/students/{sid}/payments")
def student_payments(sid: int):
    get_student_or_404(sid)
    return run("SELECT id,student_id,amount,paid_at FROM payments "
               "WHERE student_id=? ORDER BY paid_at DESC, id DESC", (sid,), many=True)


# ---- Должники ----
@app.get("/debtors")
def debtors(month: str = Query(..., description="YYYY-MM")):
    m = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", month)
    if not m:
        raise HTTPException(422, "month должен быть в формате YYYY-MM")
    y, mo = int(m[1]), int(m[2])
    start = f"{y:04d}-{mo:02d}-01"
    end = f"{y + (mo == 12):04d}-{mo % 12 + 1:02d}-01"
    rows = run("""
        SELECT s.id, s.name, s.phone, s.group_name, s.monthly_fee,
               COALESCE(SUM(p.amount), 0) AS paid
        FROM students s
        LEFT JOIN payments p ON p.student_id = s.id AND p.paid_at >= ? AND p.paid_at < ?
        GROUP BY s.id
        HAVING paid < s.monthly_fee
        ORDER BY (s.monthly_fee - paid) DESC, s.name""", (start, end), many=True)
    return [{"id": r["id"], "name": r["name"], "phone": r["phone"], "group": r["group_name"],
             "monthly_fee": r["monthly_fee"], "paid": r["paid"],
             "debt": r["monthly_fee"] - r["paid"]} for r in rows]
