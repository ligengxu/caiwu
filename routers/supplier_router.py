from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import os

from database import get_db
from models import Supplier, SupplierPayment, SupplierPaymentItem, SupplierProduct, User, AuditLog
from auth import require_login, require_roles

router = APIRouter(prefix="/suppliers", tags=["供应商管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def supplier_list(request: Request, user: User = Depends(require_login),
                        db: Session = Depends(get_db), page: int = Query(1, ge=1)):
    per_page = 20
    q = db.query(Supplier)
    total = q.count()
    suppliers = q.order_by(Supplier.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("suppliers/list.html", {
        "request": request, "user": user, "suppliers": suppliers,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@router.get("/add", response_class=HTMLResponse)
async def supplier_add_page(request: Request, user: User = Depends(require_roles("admin", "finance"))):
    return templates.TemplateResponse("suppliers/add.html", {"request": request, "user": user})


@router.post("/add")
async def supplier_add(
    request: Request, user: User = Depends(require_roles("admin", "finance")),
    db: Session = Depends(get_db), name: str = Form(...),
    alipay_account: str = Form(""), alipay_real_name: str = Form("")
):
    if db.query(Supplier).filter(Supplier.name == name).first():
        return JSONResponse({"error": "供应商已存在"}, status_code=400)
    supplier = Supplier(name=name, alipay_account=alipay_account or None,
                        alipay_real_name=alipay_real_name or None, created_by=user.id)
    db.add(supplier)
    db.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


@router.get("/{supplier_id}/edit", response_class=HTMLResponse)
async def supplier_edit_page(supplier_id: int, request: Request,
                             user: User = Depends(require_roles("admin", "finance")),
                             db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return RedirectResponse(url="/suppliers", status_code=303)
    return templates.TemplateResponse("suppliers/edit.html", {
        "request": request, "user": user, "supplier": supplier,
    })


@router.post("/{supplier_id}/edit")
async def supplier_edit(
    supplier_id: int, request: Request, user: User = Depends(require_roles("admin", "finance")),
    db: Session = Depends(get_db), name: str = Form(...),
    alipay_account: str = Form(""), alipay_real_name: str = Form(""), status: int = Form(1)
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return JSONResponse({"error": "供应商不存在"}, status_code=404)
    supplier.name = name
    supplier.alipay_account = alipay_account or None
    supplier.alipay_real_name = alipay_real_name or None
    supplier.status = status
    db.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


@router.get("/payments", response_class=HTMLResponse)
async def supplier_payment_list(request: Request, user: User = Depends(require_login),
                                db: Session = Depends(get_db), page: int = Query(1, ge=1)):
    per_page = 20
    q = db.query(SupplierPayment)
    total = q.count()
    payments = q.order_by(SupplierPayment.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("suppliers/payments.html", {
        "request": request, "user": user, "payments": payments,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })
