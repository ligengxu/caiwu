from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import os

from database import get_db
from models import WarehouseInbox, User
from auth import require_login, require_roles

router = APIRouter(prefix="/warehouse", tags=["仓库收件"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def warehouse_list(request: Request, user: User = Depends(require_login),
                         db: Session = Depends(get_db), page: int = Query(1, ge=1),
                         status: Optional[str] = None):
    per_page = 20
    q = db.query(WarehouseInbox)
    if status:
        q = q.filter(WarehouseInbox.status == status)
    total = q.count()
    items = q.order_by(WarehouseInbox.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("warehouse/list.html", {
        "request": request, "user": user, "items": items,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page, "status_filter": status,
    })


@router.post("/{item_id}/review")
async def warehouse_review(item_id: int, request: Request,
                           user: User = Depends(require_roles("admin", "finance")),
                           db: Session = Depends(get_db),
                           action: str = Form(...), note: str = Form("")):
    item = db.query(WarehouseInbox).filter(WarehouseInbox.id == item_id).first()
    if item:
        item.status = "approved" if action == "approve" else "rejected"
        item.reviewed_by = user.id
        item.review_note = note
        from datetime import datetime, timezone
        item.reviewed_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url="/warehouse", status_code=303)
