from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import os
from datetime import date

from database import get_db
from models import AdvancePayment, User
from auth import require_login, require_roles

router = APIRouter(prefix="/advances", tags=["预支管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def advance_list(request: Request, user: User = Depends(require_login),
                       db: Session = Depends(get_db), page: int = Query(1, ge=1)):
    per_page = 20
    q = db.query(AdvancePayment).options(joinedload(AdvancePayment.user))
    if user.role == "employee":
        q = q.filter(AdvancePayment.user_id == user.id)
    total = q.count()
    advances = q.order_by(AdvancePayment.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("advances/list.html", {
        "request": request, "user": user, "advances": advances,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@router.get("/add", response_class=HTMLResponse)
async def advance_add_page(request: Request, user: User = Depends(require_login)):
    return templates.TemplateResponse("advances/add.html", {"request": request, "user": user})


@router.post("/add")
async def advance_add(request: Request, user: User = Depends(require_login),
                      db: Session = Depends(get_db), amount: float = Form(...),
                      repayment_date: str = Form(...), comment: str = Form("")):
    advance = AdvancePayment(
        user_id=user.id, amount=amount,
        repayment_date=date.fromisoformat(repayment_date),
        comment=comment, status="pending"
    )
    db.add(advance)
    db.commit()
    return RedirectResponse(url="/advances", status_code=303)


@router.post("/{advance_id}/approve")
async def advance_approve(advance_id: int, user: User = Depends(require_roles("admin", "finance")),
                          db: Session = Depends(get_db)):
    adv = db.query(AdvancePayment).filter(AdvancePayment.id == advance_id).first()
    if adv:
        adv.status = "approved"
        db.commit()
    return RedirectResponse(url="/advances", status_code=303)


@router.post("/{advance_id}/reject")
async def advance_reject(advance_id: int, user: User = Depends(require_roles("admin", "finance")),
                         db: Session = Depends(get_db)):
    adv = db.query(AdvancePayment).filter(AdvancePayment.id == advance_id).first()
    if adv:
        adv.status = "rejected"
        db.commit()
    return RedirectResponse(url="/advances", status_code=303)
