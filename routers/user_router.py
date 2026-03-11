from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import os

from database import get_db
from models import User, Department, AuditLog
from auth import require_login, require_roles, get_password_hash

router = APIRouter(prefix="/users", tags=["用户管理"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("", response_class=HTMLResponse)
async def user_list(request: Request, user: User = Depends(require_roles("admin")),
                    db: Session = Depends(get_db), page: int = Query(1, ge=1)):
    per_page = 20
    q = db.query(User).options(joinedload(User.department))
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    departments = db.query(Department).filter(Department.status == 1).all()
    return templates.TemplateResponse("users/list.html", {
        "request": request, "user": user, "users": users,
        "departments": departments,
        "page": page, "total": total, "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@router.get("/add", response_class=HTMLResponse)
async def user_add_page(request: Request, user: User = Depends(require_roles("admin")),
                        db: Session = Depends(get_db)):
    departments = db.query(Department).filter(Department.status == 1).all()
    return templates.TemplateResponse("users/add.html", {
        "request": request, "user": user, "departments": departments,
    })


@router.post("/add")
async def user_add(
    request: Request, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db),
    username: str = Form(...), password: str = Form(...), real_name: str = Form(...),
    role: str = Form(...), phone: str = Form(""), department_id: Optional[int] = Form(None),
    alipay_account: str = Form(""), alipay_real_name: str = Form("")
):
    if db.query(User).filter(User.username == username).first():
        return JSONResponse({"error": "用户名已存在"}, status_code=400)

    new_user = User(
        username=username, password=get_password_hash(password),
        real_name=real_name, role=role, phone=phone,
        department_id=department_id or None,
        alipay_account=alipay_account or None,
        alipay_real_name=alipay_real_name or None,
    )
    db.add(new_user)
    db.add(AuditLog(user_id=user.id, type="user", action="create_user",
                    comment=f"创建用户: {username}", ip_address=request.client.host))
    db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def user_edit_page(user_id: int, request: Request, user: User = Depends(require_roles("admin")),
                         db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/users", status_code=303)
    departments = db.query(Department).filter(Department.status == 1).all()
    return templates.TemplateResponse("users/edit.html", {
        "request": request, "user": user, "target": target, "departments": departments,
    })


@router.post("/{user_id}/edit")
async def user_edit(
    user_id: int, request: Request, user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db), real_name: str = Form(...), role: str = Form(...),
    phone: str = Form(""), department_id: Optional[int] = Form(None),
    alipay_account: str = Form(""), alipay_real_name: str = Form(""),
    password: str = Form(""), status: int = Form(1)
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "用户不存在"}, status_code=404)

    target.real_name = real_name
    target.role = role
    target.phone = phone
    target.department_id = department_id or None
    target.alipay_account = alipay_account or None
    target.alipay_real_name = alipay_real_name or None
    target.status = status
    if password:
        target.password = get_password_hash(password)

    db.add(AuditLog(user_id=user.id, type="user", action="update_user",
                    comment=f"编辑用户: {target.username}", ip_address=request.client.host))
    db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    return templates.TemplateResponse("users/profile.html", {"request": request, "user": user})


@router.post("/profile")
async def update_profile(
    request: Request, user: User = Depends(require_login), db: Session = Depends(get_db),
    phone: str = Form(""), alipay_account: str = Form(""), alipay_real_name: str = Form(""),
    old_password: str = Form(""), new_password: str = Form("")
):
    user.phone = phone
    user.alipay_account = alipay_account or None
    user.alipay_real_name = alipay_real_name or None
    if old_password and new_password:
        from auth import verify_password
        if not verify_password(old_password, user.password):
            return templates.TemplateResponse("users/profile.html", {
                "request": request, "user": user, "error": "原密码错误"
            })
        user.password = get_password_hash(new_password)
    db.commit()
    return RedirectResponse(url="/users/profile", status_code=303)
