from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Optional
import os, uuid, shutil
from datetime import datetime

from database import get_db
from models import Expense, User, Supplier, Attachment, AuditLog
from auth import require_login, require_roles
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS

router = APIRouter(prefix="/expenses", tags=["报销管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def expense_list(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db),
    page: int = Query(1, ge=1), status: Optional[str] = None, keyword: Optional[str] = None
):
    per_page = 20
    q = db.query(Expense).options(joinedload(Expense.user), joinedload(Expense.supplier))

    if user.role == "employee":
        q = q.filter(Expense.user_id == user.id)

    if status:
        q = q.filter(Expense.status == status)
    if keyword:
        q = q.filter(or_(Expense.description.like(f"%{keyword}%")))

    total = q.count()
    expenses = q.order_by(Expense.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse("expenses/list.html", {
        "request": request, "user": user, "expenses": expenses,
        "page": page, "total": total, "per_page": per_page,
        "status_filter": status, "keyword": keyword,
        "total_pages": (total + per_page - 1) // per_page,
    })


@router.get("/add", response_class=HTMLResponse)
async def expense_add_page(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).filter(Supplier.status == 1).all()
    users = db.query(User).filter(User.status == 1).all()
    return templates.TemplateResponse("expenses/add.html", {
        "request": request, "user": user, "suppliers": suppliers, "users": users,
    })


@router.post("/add")
async def expense_add(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db),
    type: str = Form("employee"), amount: float = Form(...), description: str = Form(""),
    supplier_id: Optional[int] = Form(None), files: list[UploadFile] = File(default=[])
):
    expense = Expense(
        type=type, user_id=user.id, supplier_id=supplier_id if type == "supplier" else None,
        amount=amount, description=description, status="pending"
    )
    db.add(expense)
    db.flush()

    for f in files:
        if f.filename:
            ext = f.filename.rsplit(".", 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                fname = f"{uuid.uuid4().hex}.{ext}"
                fpath = os.path.join(UPLOAD_DIR, fname)
                with open(fpath, "wb") as buf:
                    shutil.copyfileobj(f.file, buf)
                db.add(Attachment(expense_id=expense.id, file_path=f"uploads/{fname}"))

    db.add(AuditLog(expense_id=expense.id, user_id=user.id, type="expense", action="create",
                    ip_address=request.client.host))
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)


@router.post("/{expense_id}/approve")
async def expense_approve(
    expense_id: int, request: Request, user: User = Depends(require_roles("admin", "finance")),
    db: Session = Depends(get_db), comment: str = Form("")
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        return JSONResponse({"error": "未找到"}, status_code=404)
    expense.status = "approved"
    db.add(AuditLog(expense_id=expense.id, user_id=user.id, type="expense", action="approve",
                    comment=comment, ip_address=request.client.host))
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)


@router.post("/{expense_id}/reject")
async def expense_reject(
    expense_id: int, request: Request, user: User = Depends(require_roles("admin", "finance")),
    db: Session = Depends(get_db), comment: str = Form("")
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        return JSONResponse({"error": "未找到"}, status_code=404)
    expense.status = "rejected"
    db.add(AuditLog(expense_id=expense.id, user_id=user.id, type="expense", action="reject",
                    comment=comment, ip_address=request.client.host))
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)


@router.post("/{expense_id}/pay")
async def expense_pay(
    expense_id: int, request: Request, user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.status == "approved").first()
    if not expense:
        return JSONResponse({"error": "未找到或状态不正确"}, status_code=400)
    expense.status = "paid"
    db.add(AuditLog(expense_id=expense.id, user_id=user.id, type="expense", action="payment",
                    ip_address=request.client.host))
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)


@router.get("/stats", response_class=HTMLResponse)
async def expense_stats(request: Request, user: User = Depends(require_roles("admin", "finance")),
                        db: Session = Depends(get_db)):
    from sqlalchemy import extract
    now = datetime.now()
    monthly_stats = db.query(
        extract("month", Expense.created_at).label("month"),
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count")
    ).filter(
        extract("year", Expense.created_at) == now.year
    ).group_by("month").all()

    status_stats = db.query(
        Expense.status, func.count(Expense.id).label("count"),
        func.sum(Expense.amount).label("total")
    ).group_by(Expense.status).all()

    return templates.TemplateResponse("expenses/stats.html", {
        "request": request, "user": user,
        "monthly_stats": monthly_stats, "status_stats": status_stats,
    })
