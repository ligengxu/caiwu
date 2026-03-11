from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import os

from database import get_db
from models import AuditLog, User
from auth import require_roles

router = APIRouter(prefix="/audit", tags=["审计日志"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def audit_list(request: Request, user: User = Depends(require_roles("admin")),
                     db: Session = Depends(get_db), page: int = Query(1, ge=1),
                     type: Optional[str] = None, action: Optional[str] = None):
    per_page = 30
    q = db.query(AuditLog).options(joinedload(AuditLog.user))
    if type:
        q = q.filter(AuditLog.type == type)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("audit/list.html", {
        "request": request, "user": user, "logs": logs,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "type_filter": type, "action_filter": action,
    })
