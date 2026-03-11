from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
import os

from database import get_db
from models import (User, Expense, AdminPayment, SalaryPayment,
                    SupplierPayment, Announcement, Notification)
from auth import require_login

router = APIRouter(tags=["仪表盘"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    today = datetime.now().date()
    month_start = today.replace(day=1)

    pending_expenses = db.query(func.count(Expense.id)).filter(Expense.status == "pending").scalar() or 0
    pending_payments = db.query(func.count(AdminPayment.id)).filter(AdminPayment.status == "pending_review").scalar() or 0
    pending_salaries = db.query(func.count(SalaryPayment.id)).filter(SalaryPayment.status == "pending").scalar() or 0

    month_expense_total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.status == "paid", Expense.created_at >= month_start
    ).scalar()

    month_payment_total = db.query(func.coalesce(func.sum(AdminPayment.paid_amount), 0)).filter(
        AdminPayment.status.in_(["paid", "partial_paid"]), AdminPayment.created_at >= month_start
    ).scalar()

    month_salary_total = db.query(func.coalesce(func.sum(SalaryPayment.amount), 0)).filter(
        SalaryPayment.status == "paid", SalaryPayment.created_at >= month_start
    ).scalar()

    recent_expenses = db.query(Expense).order_by(Expense.created_at.desc()).limit(5).all()
    recent_payments = db.query(AdminPayment).order_by(AdminPayment.created_at.desc()).limit(5).all()

    announcements = db.query(Announcement).filter(Announcement.is_active == 1).order_by(Announcement.created_at.desc()).limit(3).all()

    unread_count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user.id, Notification.is_read == 0
    ).scalar() or 0

    user_count = db.query(func.count(User.id)).filter(User.status == 1).scalar() or 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "pending_expenses": pending_expenses,
        "pending_payments": pending_payments,
        "pending_salaries": pending_salaries,
        "month_expense_total": float(month_expense_total),
        "month_payment_total": float(month_payment_total),
        "month_salary_total": float(month_salary_total),
        "recent_expenses": recent_expenses,
        "recent_payments": recent_payments,
        "announcements": announcements,
        "unread_count": unread_count,
        "user_count": user_count,
    })
