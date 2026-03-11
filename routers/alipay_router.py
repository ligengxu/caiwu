from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timezone
import os

from database import get_db
from models import (User, Expense, AdminPayment, AdminPaymentRecord,
                    SalaryPayment, AlipayConfig, AuditLog)
from auth import require_login, require_roles
from config import DELETE_CONFIRM_PASSWORD
import alipay_service

router = APIRouter(tags=["支付宝"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


# ──────────── 余额查询 API ────────────

@router.get("/api/alipay/balance")
async def api_alipay_balance(
    request: Request, user: User = Depends(require_login),
    db: Session = Depends(get_db), config_id: Optional[int] = None
):
    result = alipay_service.query_balance(db, config_id)
    return JSONResponse(result)


# ──────────── 账单查询页面 ────────────

@router.get("/alipay/bills", response_class=HTMLResponse)
async def alipay_bills_page(
    request: Request, user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db)
):
    configs = db.query(AlipayConfig).all()
    return templates.TemplateResponse("alipay/bills.html", {
        "request": request, "user": user, "configs": configs,
    })


# ──────────── 报销打款（审批后支付宝转账） ────────────

@router.post("/expenses/{expense_id}/alipay_pay")
async def expense_alipay_pay(
    expense_id: int, request: Request,
    user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db),
    password: str = Form(...),
    config_id: Optional[int] = Form(None),
):
    if password != DELETE_CONFIRM_PASSWORD:
        return JSONResponse({"success": False, "message": "支付密码错误"}, status_code=400)

    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.status == "approved"
    ).first()
    if not expense:
        return JSONResponse({"success": False, "message": "报销单不存在或状态不正确"}, status_code=400)

    pay_user = expense.user
    if not pay_user or not pay_user.alipay_account or not pay_user.alipay_real_name:
        return JSONResponse({"success": False, "message": "报销人未设置支付宝账号或真实姓名"}, status_code=400)

    result = alipay_service.transfer(
        db=db,
        amount=float(expense.amount),
        alipay_account=pay_user.alipay_account,
        real_name=pay_user.alipay_real_name,
        title=f"报销打款-{expense.description or ''}",
        config_id=config_id,
    )

    if result["success"]:
        expense.status = "paid"
        db.add(AuditLog(
            expense_id=expense.id, user_id=user.id, type="expense",
            action="alipay_payment",
            comment=f"支付宝打款成功，流水号: {result['trade_no']}",
            ip_address=request.client.host,
        ))
        db.commit()
        return JSONResponse({"success": True, "trade_no": result["trade_no"], "message": "打款成功"})
    else:
        db.add(AuditLog(
            expense_id=expense.id, user_id=user.id, type="expense",
            action="alipay_payment_failed",
            comment=f"支付宝打款失败: {result['message']}",
            ip_address=request.client.host,
        ))
        db.commit()
        return JSONResponse({"success": False, "message": result["message"]}, status_code=400)


# ──────────── 付款管理 - 支付宝转账 ────────────

@router.post("/payments/{payment_id}/alipay_pay")
async def payment_alipay_pay(
    payment_id: int, request: Request,
    user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db),
    password: str = Form(...),
    pay_amount: Optional[float] = Form(None),
    config_id: Optional[int] = Form(None),
):
    if password != DELETE_CONFIRM_PASSWORD:
        return JSONResponse({"success": False, "message": "支付密码错误"}, status_code=400)

    payment = db.query(AdminPayment).filter(
        AdminPayment.id == payment_id,
        AdminPayment.status.in_(["approved", "partial_paid"])
    ).first()
    if not payment:
        return JSONResponse({"success": False, "message": "付款单不存在或状态不正确"}, status_code=400)

    amount = pay_amount or float(payment.amount) - float(payment.paid_amount or 0)
    if amount <= 0:
        return JSONResponse({"success": False, "message": "付款金额必须大于0"}, status_code=400)

    result = alipay_service.transfer(
        db=db,
        amount=amount,
        alipay_account=payment.payee_account,
        real_name=payment.payee_name,
        title=f"付款-{payment.reason[:20] if payment.reason else ''}",
        config_id=config_id,
    )

    if result["success"]:
        record = AdminPaymentRecord(
            payment_id=payment.id, amount=amount, payment_method="alipay",
            trade_no=result["trade_no"], remark="支付宝自动转账",
            created_by=user.id,
        )
        db.add(record)

        payment.paid_amount = float(payment.paid_amount or 0) + amount
        payment.trade_no = result["trade_no"]
        if payment.paid_amount >= float(payment.amount):
            payment.status = "paid"
        else:
            payment.status = "partial_paid"
        payment.paid_at = datetime.now(timezone.utc)

        db.add(AuditLog(
            user_id=user.id, type="payment", action="alipay_payment",
            comment=f"支付宝打款 ¥{amount}，流水号: {result['trade_no']}",
            ip_address=request.client.host,
        ))
        db.commit()
        return JSONResponse({"success": True, "trade_no": result["trade_no"], "message": f"打款 ¥{amount} 成功"})
    else:
        db.add(AuditLog(
            user_id=user.id, type="payment", action="alipay_payment_failed",
            comment=f"支付宝打款失败: {result['message']}",
            ip_address=request.client.host,
        ))
        db.commit()
        return JSONResponse({"success": False, "message": result["message"]}, status_code=400)


# ──────────── 工资 - 支付宝打款 ────────────

@router.post("/salary/{salary_id}/alipay_pay")
async def salary_alipay_pay(
    salary_id: int, request: Request,
    user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db),
    password: str = Form(...),
    config_id: Optional[int] = Form(None),
):
    if password != DELETE_CONFIRM_PASSWORD:
        return JSONResponse({"success": False, "message": "支付密码错误"}, status_code=400)

    salary = db.query(SalaryPayment).filter(
        SalaryPayment.id == salary_id, SalaryPayment.status == "approved"
    ).first()
    if not salary:
        return JSONResponse({"success": False, "message": "工资单不存在或状态不正确"}, status_code=400)

    target_user = db.query(User).filter(User.id == salary.user_id).first()
    if not target_user or not target_user.alipay_account or not target_user.alipay_real_name:
        return JSONResponse({"success": False, "message": "员工未设置支付宝账号"}, status_code=400)

    result = alipay_service.transfer(
        db=db,
        amount=float(salary.amount),
        alipay_account=target_user.alipay_account,
        real_name=target_user.alipay_real_name,
        title=f"工资发放-{salary.payment_month}",
        config_id=config_id,
    )

    if result["success"]:
        salary.status = "paid"
        db.add(AuditLog(
            user_id=user.id, type="salary", action="alipay_payment",
            comment=f"工资支付宝打款成功，流水号: {result['trade_no']}",
            ip_address=request.client.host,
        ))
        db.commit()
        return JSONResponse({"success": True, "trade_no": result["trade_no"], "message": "工资打款成功"})
    else:
        return JSONResponse({"success": False, "message": result["message"]}, status_code=400)


# ──────────── 最近打款记录 API ────────────

@router.get("/api/alipay/recent_bills")
async def api_recent_bills(
    request: Request, user: User = Depends(require_roles("admin", "finance", "cashier")),
    db: Session = Depends(get_db), limit: int = Query(50, le=200)
):
    logs = db.query(AuditLog).filter(
        AuditLog.action.in_(["alipay_payment", "alipay_payment_failed"])
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()

    bills = []
    for log in logs:
        type_label = "报销" if log.type == "expense" else ("付款" if log.type == "payment" else "工资")
        type_color = "primary" if log.type == "expense" else ("warning" if log.type == "payment" else "success")
        is_success = log.action == "alipay_payment"

        trade_no = ""
        payee = ""
        amount = ""
        if log.comment:
            import re
            tn = re.search(r"流水号:\s*(\S+)", log.comment)
            if tn:
                trade_no = tn.group(1)
            am = re.search(r"¥([\d.]+)", log.comment)
            if am:
                amount = am.group(1)

        bills.append({
            "id": log.id,
            "type_label": type_label + ("" if is_success else " (失败)"),
            "type_color": type_color if is_success else "danger",
            "payee": payee or "-",
            "amount": amount or "-",
            "trade_no": trade_no,
            "operator": log.user.real_name if log.user else "-",
            "time": log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "",
        })

    return JSONResponse({"bills": bills})
