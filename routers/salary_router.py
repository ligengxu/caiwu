from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import os
from datetime import date

from database import get_db
from models import SalaryPayment, User, AuditLog
from auth import require_login, require_roles

router = APIRouter(prefix="/salary", tags=["工资管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def salary_list(request: Request, user: User = Depends(require_login),
                      db: Session = Depends(get_db), page: int = Query(1, ge=1),
                      status: Optional[str] = None):
    per_page = 20
    q = db.query(SalaryPayment).options(joinedload(SalaryPayment.user), joinedload(SalaryPayment.creator))

    if user.role == "employee":
        q = q.filter(SalaryPayment.user_id == user.id)
    if status:
        q = q.filter(SalaryPayment.status == status)

    total = q.count()
    salaries = q.order_by(SalaryPayment.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("salary/list.html", {
        "request": request, "user": user, "salaries": salaries,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page, "status_filter": status,
    })


@router.get("/add", response_class=HTMLResponse)
async def salary_add_page(request: Request, user: User = Depends(require_roles("admin", "finance")),
                          db: Session = Depends(get_db)):
    users = db.query(User).filter(User.status == 1).all()
    return templates.TemplateResponse("salary/add.html", {
        "request": request, "user": user, "users": users,
    })


@router.post("/add")
async def salary_add(
    request: Request, user: User = Depends(require_roles("admin", "finance")),
    db: Session = Depends(get_db), user_id: int = Form(...), amount: float = Form(...),
    payment_month: str = Form(...), description: str = Form("")
):
    salary = SalaryPayment(
        user_id=user_id, amount=amount,
        payment_month=date.fromisoformat(payment_month + "-01") if len(payment_month) == 7 else date.fromisoformat(payment_month),
        description=description, created_by=user.id, status="pending"
    )
    db.add(salary)
    db.commit()
    return RedirectResponse(url="/salary", status_code=303)


@router.post("/{salary_id}/approve")
async def salary_approve(salary_id: int, request: Request,
                         user: User = Depends(require_roles("admin")),
                         db: Session = Depends(get_db)):
    salary = db.query(SalaryPayment).filter(SalaryPayment.id == salary_id).first()
    if salary:
        salary.status = "approved"
        db.commit()
    return RedirectResponse(url="/salary", status_code=303)


@router.post("/{salary_id}/reject")
async def salary_reject(salary_id: int, request: Request,
                        user: User = Depends(require_roles("admin")),
                        db: Session = Depends(get_db)):
    salary = db.query(SalaryPayment).filter(SalaryPayment.id == salary_id).first()
    if salary:
        salary.status = "rejected"
        db.commit()
    return RedirectResponse(url="/salary", status_code=303)


@router.post("/{salary_id}/pay")
async def salary_pay(salary_id: int, request: Request,
                     user: User = Depends(require_roles("admin", "finance", "cashier")),
                     db: Session = Depends(get_db)):
    salary = db.query(SalaryPayment).filter(SalaryPayment.id == salary_id, SalaryPayment.status == "approved").first()
    if salary:
        salary.status = "paid"
        db.commit()
    return RedirectResponse(url="/salary", status_code=303)
