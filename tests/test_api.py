import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
from app import app

S = {"name": "Али", "phone": "+998901234567", "group": "IELTS", "monthly_fee": 1000}


def test_flow():
    with TestClient(app) as c:
        sid = c.post("/students", json=S).json()["id"]
        assert c.get("/students").json()[0]["group"] == "IELTS"
        d = c.get("/debtors?month=2026-10").json()
        assert d[0]["debt"] == 1000
        c.post("/payments", json={"student_id": sid, "amount": 400, "paid_at": "2026-10-05"})
        c.post("/payments", json={"student_id": sid, "amount": 100, "paid_at": "2026-09-30"})  # другой месяц
        assert c.get("/debtors?month=2026-10").json()[0]["debt"] == 600
        c.post("/payments", json={"student_id": sid, "amount": 600, "paid_at": "2026-10-20"})
        assert c.get("/debtors?month=2026-10").json() == []
        assert len(c.get(f"/students/{sid}/payments").json()) == 3
        assert c.put(f"/students/{sid}", json={**S, "monthly_fee": 2000}).json()["monthly_fee"] == 2000
        assert c.delete(f"/students/{sid}").status_code == 204
        assert c.get(f"/students/{sid}").status_code == 404


def test_validation():
    with TestClient(app) as c:
        assert c.get("/debtors?month=2026-13").status_code == 422
        assert c.post("/payments", json={"student_id": 999, "amount": 5}).status_code == 404
        assert c.post("/payments", json={"student_id": 1, "amount": -5}).status_code == 422
