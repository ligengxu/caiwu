from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from database import get_db
from models import SystemSetting, Department, Announcement, User
from auth import require_roles

router = APIRouter(prefix="/system", tags=["系统管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_roles("admin")),
                        db: Session = Depends(get_db)):
    settings = db.query(SystemSetting).all()
    return templates.TemplateResponse("system/settings.html", {
        "request": request, "user": user, "settings": settings,
    })


@router.get("/departments", response_class=HTMLResponse)
async def department_list(request: Request, user: User = Depends(require_roles("admin")),
                          db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    return templates.TemplateResponse("system/departments.html", {
        "request": request, "user": user, "departments": departments,
    })


@router.post("/departments/add")
async def department_add(request: Request, user: User = Depends(require_roles("admin")),
                         db: Session = Depends(get_db), name: str = Form(...)):
    dept = Department(name=name, created_by=user.id)
    db.add(dept)
    db.commit()
    return RedirectResponse(url="/system/departments", status_code=303)


@router.get("/announcements", response_class=HTMLResponse)
async def announcement_list(request: Request, user: User = Depends(require_roles("admin")),
                            db: Session = Depends(get_db)):
    announcements = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return templates.TemplateResponse("system/announcements.html", {
        "request": request, "user": user, "announcements": announcements,
    })


@router.post("/announcements/add")
async def announcement_add(request: Request, user: User = Depends(require_roles("admin")),
                           db: Session = Depends(get_db), title: str = Form(...),
                           content: str = Form(...), type: str = Form("info")):
    ann = Announcement(title=title, content=content, type=type, created_by=user.id)
    db.add(ann)
    db.commit()
    return RedirectResponse(url="/system/announcements", status_code=303)
