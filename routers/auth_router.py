from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from database import get_db
from models import User, AuditLog
from auth import verify_password, get_password_hash, create_access_token, get_current_user_optional

router = APIRouter(tags=["认证"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    from auth import _extract_user
    user = _extract_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username, User.status == 1).first()
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "用户名或密码错误"
        })

    token = create_access_token(data={"sub": str(user.id), "role": user.role, "name": user.real_name})

    log = AuditLog(
        user_id=user.id, type="auth", action="login",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        request_uri="/login", request_method="POST"
    )
    db.add(log)
    db.commit()

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=86400)
    return response


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    from auth import _extract_user
    user = _extract_user(request, db)
    if user:
        log = AuditLog(user_id=user.id, type="auth", action="logout", ip_address=request.client.host)
        db.add(log)
        db.commit()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
