from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import os, shutil, uuid

from database import get_db
from models import AlipayConfig, User, AuditLog
from auth import require_roles

router = APIRouter(prefix="/system/alipay", tags=["支付宝配置"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))
CERT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cert")


def _save_cert(upload: UploadFile, prefix: str) -> Optional[str]:
    if not upload or not upload.filename:
        return None
    ext = upload.filename.rsplit(".", 1)[-1] if "." in upload.filename else "crt"
    fname = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    fpath = os.path.join(CERT_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return f"cert/{fname}"


@router.get("", response_class=HTMLResponse)
async def config_list(request: Request, user: User = Depends(require_roles("admin")),
                      db: Session = Depends(get_db)):
    configs = db.query(AlipayConfig).order_by(AlipayConfig.is_active.desc(), AlipayConfig.id).all()
    return templates.TemplateResponse("alipay/config_list.html", {
        "request": request, "user": user, "configs": configs,
    })


@router.post("/activate/{config_id}")
async def activate_config(config_id: int, request: Request,
                          user: User = Depends(require_roles("admin")),
                          db: Session = Depends(get_db)):
    db.query(AlipayConfig).update({AlipayConfig.is_active: 0})
    cfg = db.query(AlipayConfig).filter(AlipayConfig.id == config_id).first()
    if cfg:
        cfg.is_active = 1
        db.add(AuditLog(
            user_id=user.id, type="system", action="switch_alipay_config",
            comment=f"切换支付宝配置为: {cfg.config_name} (ID:{cfg.id})",
            ip_address=request.client.host,
        ))
        db.commit()
    return RedirectResponse(url="/system/alipay", status_code=303)


@router.get("/add", response_class=HTMLResponse)
async def add_page(request: Request, user: User = Depends(require_roles("admin"))):
    return templates.TemplateResponse("alipay/config_form.html", {
        "request": request, "user": user, "config": None, "is_edit": False,
    })


@router.post("/add")
async def add_config(
    request: Request, user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
    config_name: str = Form(...),
    app_id: str = Form(...),
    private_key: str = Form(...),
    server_url: str = Form("https://openapi.alipay.com/gateway.do"),
    remark: str = Form(""),
    root_cert_sn: str = Form(""),
    app_cert_file: UploadFile = File(default=None),
    alipay_cert_file: UploadFile = File(default=None),
    root_cert_file: UploadFile = File(default=None),
):
    app_cert_path = _save_cert(app_cert_file, "appCert")
    alipay_cert_path = _save_cert(alipay_cert_file, "alipayCert")
    root_cert_path = _save_cert(root_cert_file, "rootCert")

    cfg = AlipayConfig(
        config_name=config_name,
        app_id=app_id.strip(),
        private_key=private_key.strip(),
        server_url=server_url.strip(),
        app_cert_path=app_cert_path or "",
        alipay_public_cert_path=alipay_cert_path or "",
        root_cert_path=root_cert_path or "",
        root_cert_sn=root_cert_sn.strip() or None,
        remark=remark,
        is_active=0,
    )
    db.add(cfg)
    db.add(AuditLog(
        user_id=user.id, type="system", action="add_alipay_config",
        comment=f"新增支付宝配置: {config_name}",
        ip_address=request.client.host,
    ))
    db.commit()
    return RedirectResponse(url="/system/alipay", status_code=303)


@router.get("/{config_id}/edit", response_class=HTMLResponse)
async def edit_page(config_id: int, request: Request,
                    user: User = Depends(require_roles("admin")),
                    db: Session = Depends(get_db)):
    cfg = db.query(AlipayConfig).filter(AlipayConfig.id == config_id).first()
    if not cfg:
        return RedirectResponse(url="/system/alipay", status_code=303)
    return templates.TemplateResponse("alipay/config_form.html", {
        "request": request, "user": user, "config": cfg, "is_edit": True,
    })


@router.post("/{config_id}/edit")
async def edit_config(
    config_id: int, request: Request,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
    config_name: str = Form(...),
    app_id: str = Form(...),
    private_key: str = Form(""),
    server_url: str = Form("https://openapi.alipay.com/gateway.do"),
    remark: str = Form(""),
    root_cert_sn: str = Form(""),
    app_cert_file: UploadFile = File(default=None),
    alipay_cert_file: UploadFile = File(default=None),
    root_cert_file: UploadFile = File(default=None),
):
    cfg = db.query(AlipayConfig).filter(AlipayConfig.id == config_id).first()
    if not cfg:
        return JSONResponse({"error": "配置不存在"}, status_code=404)

    cfg.config_name = config_name
    cfg.app_id = app_id.strip()
    cfg.server_url = server_url.strip()
    cfg.remark = remark

    if private_key.strip():
        cfg.private_key = private_key.strip()

    if root_cert_sn.strip():
        cfg.root_cert_sn = root_cert_sn.strip()

    new_app_cert = _save_cert(app_cert_file, "appCert")
    if new_app_cert:
        cfg.app_cert_path = new_app_cert

    new_alipay_cert = _save_cert(alipay_cert_file, "alipayCert")
    if new_alipay_cert:
        cfg.alipay_public_cert_path = new_alipay_cert

    new_root_cert = _save_cert(root_cert_file, "rootCert")
    if new_root_cert:
        cfg.root_cert_path = new_root_cert

    db.add(AuditLog(
        user_id=user.id, type="system", action="edit_alipay_config",
        comment=f"编辑支付宝配置: {config_name} (ID:{config_id})",
        ip_address=request.client.host,
    ))
    db.commit()
    return RedirectResponse(url="/system/alipay", status_code=303)


@router.post("/{config_id}/delete")
async def delete_config(config_id: int, request: Request,
                        user: User = Depends(require_roles("admin")),
                        db: Session = Depends(get_db)):
    cfg = db.query(AlipayConfig).filter(AlipayConfig.id == config_id).first()
    if not cfg:
        return JSONResponse({"error": "配置不存在"}, status_code=404)
    if cfg.is_active:
        return JSONResponse({"error": "不能删除当前激活的配置"}, status_code=400)

    name = cfg.config_name
    db.delete(cfg)
    db.add(AuditLog(
        user_id=user.id, type="system", action="delete_alipay_config",
        comment=f"删除支付宝配置: {name} (ID:{config_id})",
        ip_address=request.client.host,
    ))
    db.commit()
    return RedirectResponse(url="/system/alipay", status_code=303)


@router.post("/test/{config_id}")
async def test_config(config_id: int, request: Request,
                      user: User = Depends(require_roles("admin")),
                      db: Session = Depends(get_db)):
    import alipay_service
    result = alipay_service.query_balance(db, config_id)
    return JSONResponse(result)
