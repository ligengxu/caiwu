# 财务管理系统 (caiwu)

基于 Python + FastAPI 重构的财务管理系统 v3.0.0

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy
- **前端**: Jinja2 + Bootstrap 5.3 + Bootstrap Icons
- **数据库**: MySQL (expense_system3)
- **认证**: JWT (HttpOnly Cookie)

## 功能模块

- 仪表盘 - 数据概览
- 报销管理 - 员工/供应商报销申请、审批、付款
- 付款管理 - 对外付款审核、支付、记录
- 工资管理 - 工资发放审批
- 预支管理 - 员工预支申请
- 供应商管理 - 供应商信息、付款
- 发货管理 - 每日发货成本统计
- 快递管理 - 快递公司、订单
- 仓库收件 - 仓库系统对接
- 用户管理 - 角色权限 (管理员/财务/出纳/员工)
- 审计日志 - 操作记录追踪
- 系统设置 - 部门、公告管理

## 部署

```bash
pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 9090
```

## Systemd 服务

```bash
systemctl start caiwu
systemctl status caiwu
```
