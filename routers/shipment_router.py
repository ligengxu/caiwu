from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import os
from datetime import date

from database import get_db
from models import DailyShipment, User
from auth import require_login, require_roles

router = APIRouter(prefix="/shipments", tags=["发货管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def shipment_list(request: Request, user: User = Depends(require_login),
                        db: Session = Depends(get_db), page: int = Query(1, ge=1),
                        ship_date: Optional[str] = None):
    per_page = 30
    q = db.query(DailyShipment)
    if ship_date:
        q = q.filter(DailyShipment.ship_date == date.fromisoformat(ship_date))
    total = q.count()
    shipments = q.order_by(DailyShipment.ship_date.desc(), DailyShipment.id.desc()).offset(
        (page - 1) * per_page).limit(per_page).all()

    total_cost = db.query(func.coalesce(func.sum(DailyShipment.total_cost), 0)).scalar()

    return templates.TemplateResponse("shipments/list.html", {
        "request": request, "user": user, "shipments": shipments,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "ship_date": ship_date, "total_cost": float(total_cost),
    })
