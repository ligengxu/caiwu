import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from config import APP_NAME, APP_VERSION, SECRET_KEY
from auth import LoginRequiredException, PermissionDeniedException
from routers import auth_router, dashboard_router, expense_router, user_router
from routers import supplier_router, salary_router, admin_payment_router
from routers import advance_router, express_router, shipment_router
from routers import system_router, audit_router, warehouse_router

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.mount("/uploads", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "uploads")), name="uploads")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(expense_router.router)
app.include_router(user_router.router)
app.include_router(supplier_router.router)
app.include_router(salary_router.router)
app.include_router(admin_payment_router.router)
app.include_router(advance_router.router)
app.include_router(express_router.router)
app.include_router(shipment_router.router)
app.include_router(system_router.router)
app.include_router(audit_router.router)
app.include_router(warehouse_router.router)


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.exception_handler(LoginRequiredException)
async def login_required_handler(request: Request, exc: LoginRequiredException):
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(PermissionDeniedException)
async def permission_denied_handler(request: Request, exc: PermissionDeniedException):
    return HTMLResponse(
        content='<div style="text-align:center;padding:100px;font-family:sans-serif">'
                '<h1 style="color:#dc3545">403 权限不足</h1>'
                '<p>您没有权限访问此页面</p>'
                '<a href="/dashboard" style="color:#4361ee">返回首页</a></div>',
        status_code=403
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9090, reload=True)
