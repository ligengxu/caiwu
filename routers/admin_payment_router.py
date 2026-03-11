from fastapi import APIRouter, Depends, Request, Form, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import os, uuid, shutil

from database import get_db
from models import AdminPayment, AdminPaymentRecord, Supplier, User, AuditLog
from auth import require_login, require_roles
from config import UPLOAD_DIR

router = APIRouter(prefix="/payments", tags=["付款管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def payment_list(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db),
    page: int = Query(1, ge=1), status: Optional[str] = None
):
    per_page = 20
    q = db.query(AdminPayment).options(joinedload(AdminPayment.supplier), joinedload(AdminPayment.creator))

    if user.role == "employee":
        q = q.filter(AdminPayment.created_by == user.id)
    if status:
        q = q.filter(AdminPayment.status == status)

    total = q.count()
    payments = q.order_by(AdminPayment.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("payments/list.html", {
        "request": request, "user": user, "payments": payments,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page, "status_filter": status,
    })


@router.get("/add", response_class=HTMLResponse)
async def payment_add_page(request: Request, user: User = Depends(require_login),
                           db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).filter(Supplier.status == 1).all()
    return templates.TemplateResponse("payments/add.html", {
        "request": request, "user": user, "suppliers": suppliers,
    })


@router.post("/add")
async def payment_add(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db),
    payee_account: str = Form(...), payee_name: str = Form(...), amount: float = Form(...),
    reason: str = Form(...), supplier_id: Optional[int] = Form(None),
    payment_time_type: str = Form("immediate"), scheduled_payment_date: Optional[str] = Form(None),
    voucher: UploadFile = File(default=None)
):
    voucher_path = None
    if voucher and voucher.filename:
        ext = voucher.filename.rsplit(".", 1)[-1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)
        with open(fpath, "wb") as buf:
            shutil.copyfileobj(voucher.file, buf)
        voucher_path = f"uploads/{fname}"

    from datetime import date as date_type
    payment = AdminPayment(
        supplier_id=supplier_id or None, payee_account=payee_account, payee_name=payee_name,
        amount=amount, reason=reason, voucher_path=voucher_path,
        payment_time_type=payment_time_type,
        scheduled_payment_date=date_type.fromisoformat(scheduled_payment_date) if scheduled_payment_date else None,
        created_by=user.id, status="pending_review"
    )
    db.add(payment)
    db.commit()
    return RedirectResponse(url="/payments", status_code=303)


@router.post("/{payment_id}/review")
async def payment_review(
    payment_id: int, request: Request, user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db), action: str = Form(...), comment: str = Form("")
):
    payment = db.query(AdminPayment).filter(AdminPayment.id == payment_id).first()
    if not payment:
        return JSONResponse({"error": "未找到"}, status_code=404)

    if action == "approve":
        payment.status = "approved"
    elif action == "reject":
        payment.status = "rejected"
    payment.reviewed_by = user.id
    payment.review_comment = comment
    from datetime import datetime, timezone
    payment.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return RedirectResponse(url="/payments", status_code=303)


@router.post("/{payment_id}/pay")
async def payment_pay(
    payment_id: int, request: Request,
    user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db), pay_amount: float = Form(...),
    payment_method: str = Form("alipay"), trade_no: str = Form(""), remark: str = Form("")
):
    payment = db.query(AdminPayment).filter(
        AdminPayment.id == payment_id, AdminPayment.status.in_(["approved", "partial_paid"])
    ).first()
    if not payment:
        return JSONResponse({"error": "未找到或状态不正确"}, status_code=400)

    record = AdminPaymentRecord(
        payment_id=payment.id, amount=pay_amount, payment_method=payment_method,
        trade_no=trade_no or None, remark=remark or None, created_by=user.id
    )
    db.add(record)

    payment.paid_amount = float(payment.paid_amount or 0) + pay_amount
    if payment.paid_amount >= float(payment.amount):
        payment.status = "paid"
    else:
        payment.status = "partial_paid"
    from datetime import datetime, timezone
    payment.paid_at = datetime.now(timezone.utc)
    db.commit()
    return RedirectResponse(url="/payments", status_code=303)


@router.get("/{payment_id}", response_class=HTMLResponse)
async def payment_detail(payment_id: int, request: Request, user: User = Depends(require_login),
                         db: Session = Depends(get_db)):
    payment = db.query(AdminPayment).options(
        joinedload(AdminPayment.supplier), joinedload(AdminPayment.creator),
        joinedload(AdminPayment.records)
    ).filter(AdminPayment.id == payment_id).first()
    if not payment:
        return RedirectResponse(url="/payments", status_code=303)
    return templates.TemplateResponse("payments/detail.html", {
        "request": request, "user": user, "payment": payment,
    })
