from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
import os

from database import get_db
from models import ExpressOrder, ExpressCompany, User
from auth import require_login, require_roles

router = APIRouter(prefix="/express", tags=["快递管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def express_list(request: Request, user: User = Depends(require_login),
                       db: Session = Depends(get_db), page: int = Query(1, ge=1)):
    per_page = 20
    q = db.query(ExpressOrder).options(joinedload(ExpressOrder.company), joinedload(ExpressOrder.creator))
    total = q.count()
    orders = q.order_by(ExpressOrder.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return templates.TemplateResponse("express/list.html", {
        "request": request, "user": user, "orders": orders,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@router.get("/companies", response_class=HTMLResponse)
async def company_list(request: Request, user: User = Depends(require_roles("admin", "finance")),
                       db: Session = Depends(get_db)):
    companies = db.query(ExpressCompany).all()
    return templates.TemplateResponse("express/companies.html", {
        "request": request, "user": user, "companies": companies,
    })
