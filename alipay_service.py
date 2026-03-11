"""
支付宝服务模块
- 余额查询: alipay.data.bill.balance.query
- 单笔转账: alipay.fund.trans.uni.transfer
- 使用 RSA2 签名 + 证书模式
"""
import os
import json
import time
import hashlib
import base64
import random
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from sqlalchemy.orm import Session
from models import AlipayConfig

BASE_DIR = os.path.dirname(__file__)
CERT_DIR = os.path.join(BASE_DIR, "cert")
CACERT_PATH = os.path.join(BASE_DIR, "cacert.pem")


def _load_alipay_config(db: Session, config_id: Optional[int] = None) -> Optional[dict]:
    if config_id:
        cfg = db.query(AlipayConfig).filter(AlipayConfig.id == config_id).first()
    else:
        cfg = db.query(AlipayConfig).filter(AlipayConfig.is_active == 1).first()
    if not cfg:
        return None
    return {
        "id": cfg.id,
        "config_name": cfg.config_name,
        "app_id": cfg.app_id,
        "private_key": cfg.private_key,
        "app_cert_path": cfg.app_cert_path,
        "alipay_public_cert_path": cfg.alipay_public_cert_path,
        "root_cert_path": cfg.root_cert_path,
        "root_cert_sn": cfg.root_cert_sn,
        "server_url": cfg.server_url or "https://openapi.alipay.com/gateway.do",
    }


def _get_cert_sn(cert_path: str) -> str:
    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())

    issuer_parts = []
    for attr in cert.issuer:
        issuer_parts.append(f"{attr.oid.dotted_string}={attr.value}")
    issuer_str_rfc = cert.issuer.rfc4514_string()

    issuer_attrs = cert.issuer.rdns
    issuer_parts = []
    for rdn in reversed(issuer_attrs):
        for attr in rdn:
            oid = attr.oid
            name_map = {
                "2.5.4.6": "C", "2.5.4.8": "ST", "2.5.4.7": "L",
                "2.5.4.10": "O", "2.5.4.11": "OU", "2.5.4.3": "CN",
            }
            key = name_map.get(oid.dotted_string, oid.dotted_string)
            issuer_parts.append(f"{key}={attr.value}")
    issuer_str = ",".join(issuer_parts)

    serial = str(cert.serial_number)
    return hashlib.md5((issuer_str + serial).encode()).hexdigest()


def _get_root_cert_sn(root_cert_path: str) -> str:
    with open(root_cert_path, "r") as f:
        content = f.read()

    certs = re.findall(
        r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
        content, re.DOTALL
    )

    sn_list = []
    for pem in certs:
        try:
            cert = x509.load_pem_x509_certificate(pem.encode())
            sig_alg = cert.signature_algorithm_oid.dotted_string
            # Only RSA certs: 1.2.840.113549.1.1.x
            if not sig_alg.startswith("1.2.840.113549.1.1"):
                continue

            issuer_attrs = cert.issuer.rdns
            parts = []
            for rdn in reversed(issuer_attrs):
                for attr in rdn:
                    oid = attr.oid
                    name_map = {
                        "2.5.4.6": "C", "2.5.4.8": "ST", "2.5.4.7": "L",
                        "2.5.4.10": "O", "2.5.4.11": "OU", "2.5.4.3": "CN",
                    }
                    key = name_map.get(oid.dotted_string, oid.dotted_string)
                    parts.append(f"{key}={attr.value}")
            issuer_str = ",".join(parts)
            serial = str(cert.serial_number)
            sn_list.append(hashlib.md5((issuer_str + serial).encode()).hexdigest())
        except Exception:
            continue

    return "_".join(sn_list)


def _rsa2_sign(content: str, private_key_str: str) -> str:
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        + "\n".join(
            private_key_str[i:i+64]
            for i in range(0, len(private_key_str), 64)
        )
        + "\n-----END RSA PRIVATE KEY-----"
    )
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    signature = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def _build_sign_content(params: dict) -> str:
    sorted_keys = sorted(params.keys())
    parts = []
    for k in sorted_keys:
        v = params[k]
        if v is not None and v != "" and k != "sign":
            parts.append(f"{k}={v}")
    return "&".join(parts)


def _call_alipay_api(config: dict, method: str, biz_content: dict) -> dict:
    app_cert_path = os.path.join(BASE_DIR, config["app_cert_path"])
    root_cert_path = os.path.join(BASE_DIR, config["root_cert_path"])

    app_cert_sn = _get_cert_sn(app_cert_path)

    if config.get("root_cert_sn"):
        root_cert_sn = config["root_cert_sn"]
    else:
        root_cert_sn = _get_root_cert_sn(root_cert_path)

    params = {
        "app_id": config["app_id"],
        "method": method,
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "app_cert_sn": app_cert_sn,
        "alipay_root_cert_sn": root_cert_sn,
        "biz_content": json.dumps(biz_content, ensure_ascii=False),
    }

    sign_content = _build_sign_content(params)
    params["sign"] = _rsa2_sign(sign_content, config["private_key"])

    verify_arg = CACERT_PATH if os.path.exists(CACERT_PATH) else False
    resp = requests.post(
        config["server_url"],
        data=params,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        verify=verify_arg,
        timeout=30,
    )
    return resp.json()


# ──────────────────────────────────────────────
# 公开 API
# ──────────────────────────────────────────────

def query_balance(db: Session, config_id: Optional[int] = None) -> dict:
    """查询支付宝账户余额"""
    config = _load_alipay_config(db, config_id)
    if not config:
        return {"success": False, "message": "未找到启用的支付宝配置"}

    try:
        data = _call_alipay_api(config, "alipay.data.bill.balance.query", {})
        resp_key = "alipay_data_bill_balance_query_response"
        if resp_key in data:
            r = data[resp_key]
            if str(r.get("code")) == "10000":
                return {
                    "success": True,
                    "config_name": config["config_name"],
                    "available_amount": r["available_amount"],
                    "total_amount": r["total_amount"],
                    "freeze_amount": r["freeze_amount"],
                }
            else:
                return {
                    "success": False,
                    "message": f"{r.get('msg', '')} - {r.get('sub_msg', '')}",
                    "code": r.get("sub_code", r.get("code")),
                }
        return {"success": False, "message": "响应格式异常"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def transfer(
    db: Session,
    amount: float,
    alipay_account: str,
    real_name: str,
    title: str = "报销打款",
    config_id: Optional[int] = None,
) -> dict:
    """支付宝单笔转账"""
    config = _load_alipay_config(db, config_id)
    if not config:
        return {"success": False, "message": "未找到启用的支付宝配置"}

    out_biz_no = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))

    biz_content = {
        "out_biz_no": out_biz_no,
        "trans_amount": str(amount),
        "product_code": "TRANS_ACCOUNT_NO_PWD",
        "biz_scene": "DIRECT_TRANSFER",
        "order_title": title,
        "payee_info": {
            "identity": alipay_account,
            "identity_type": "ALIPAY_LOGON_ID",
            "name": real_name,
        },
    }

    try:
        data = _call_alipay_api(config, "alipay.fund.trans.uni.transfer", biz_content)
        resp_key = "alipay_fund_trans_uni_transfer_response"
        if resp_key in data:
            r = data[resp_key]
            if str(r.get("code")) == "10000":
                return {
                    "success": True,
                    "trade_no": r.get("order_id", ""),
                    "out_biz_no": r.get("out_biz_no", out_biz_no),
                    "pay_date": r.get("pay_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                }
            else:
                sub_code = r.get("sub_code", "")
                sub_msg = r.get("sub_msg", "")
                msg = r.get("msg", "转账失败")
                friendly = f"{msg} - {sub_msg}" if sub_msg else msg

                if sub_code == "isv.insufficient-isv-permissions":
                    friendly = "应用权限不足，请确认已签约「单笔转账到支付宝账户」"
                elif sub_code == "isv.invalid-signature":
                    friendly = "签名验证失败，请检查应用私钥"

                return {
                    "success": False,
                    "message": friendly,
                    "error_code": sub_code or r.get("code", "UNKNOWN"),
                    "full_response": json.dumps(r, ensure_ascii=False),
                }
        return {"success": False, "message": "响应格式异常", "raw": json.dumps(data, ensure_ascii=False)}
    except Exception as e:
        return {"success": False, "message": str(e), "error_code": "SYSTEM_ERROR"}
