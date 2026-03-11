from sqlalchemy import (
    Column, Integer, String, Text, Enum, DECIMAL, TIMESTAMP, Date,
    DateTime, ForeignKey, JSON, SmallInteger, Time, Boolean, func
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    real_name = Column(String(50), nullable=False)
    role = Column(Enum("admin", "finance", "cashier", "employee"), nullable=False)
    status = Column(SmallInteger, default=1)
    alipay_account = Column(String(100))
    alipay_real_name = Column(String(50))
    alipay_verified = Column(SmallInteger, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())
    department_id = Column(Integer, ForeignKey("departments.id"))
    phone = Column(String(20))
    payment_password = Column(String(255))
    payment_password_updated_at = Column(TIMESTAMP)

    department = relationship("Department", back_populates="users", foreign_keys=[department_id])
    expenses = relationship("Expense", back_populates="user", foreign_keys="Expense.user_id")
    salary_payments = relationship("SalaryPayment", back_populates="user", foreign_keys="SalaryPayment.user_id")


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    status = Column(SmallInteger, default=1)
    created_at = Column(TIMESTAMP, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    users = relationship("User", back_populates="department", foreign_keys="User.department_id")


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    alipay_account = Column(String(100))
    alipay_real_name = Column(String(50))
    alipay_verified = Column(SmallInteger, default=0)
    status = Column(SmallInteger, default=1)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

    creator = relationship("User", foreign_keys=[created_by])


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum("employee", "supplier"), nullable=False, default="employee")
    user_id = Column(Integer, ForeignKey("users.id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    amount = Column(DECIMAL(10, 2), nullable=False)
    description = Column(Text)
    status = Column(Enum("pending", "approved", "rejected", "paid"), default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="expenses", foreign_keys=[user_id])
    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    attachments = relationship("Attachment", back_populates="expense")


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    file_path = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    expense = relationship("Expense", back_populates="attachments")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False, default="create")
    action = Column(String(100), nullable=False)
    comment = Column(Text)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    device_type = Column(String(50))
    browser = Column(String(100))
    os = Column(String(100))
    location = Column(String(255))
    session_id = Column(String(128))
    risk_level = Column(Enum("low", "medium", "high", "critical"), default="low")
    request_uri = Column(String(500))
    request_method = Column(String(10))
    extra_data = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])


class AlipayVerification(Base):
    __tablename__ = "alipay_verifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum("employee", "supplier"), nullable=False)
    reference_id = Column(Integer, nullable=False)
    alipay_account = Column(String(100), nullable=False)
    alipay_real_name = Column(String(50))
    status = Column(Enum("pending", "approved", "rejected"), default="pending")
    verified_by = Column(Integer, ForeignKey("users.id"))
    verified_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now())


class AlipayConfig(Base):
    __tablename__ = "alipay_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_name = Column(String(100), nullable=False)
    app_id = Column(String(50), nullable=False)
    private_key = Column(Text, nullable=False)
    app_cert_path = Column(String(255))
    alipay_public_cert_path = Column(String(255))
    root_cert_path = Column(String(255))
    root_cert_sn = Column(String(255))
    cacert_path = Column(String(255))
    server_url = Column(String(255), nullable=False, default="https://openapi.alipay.com/gateway.do")
    is_active = Column(SmallInteger, default=0)
    remark = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AdminPayment(Base):
    __tablename__ = "admin_payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    payee_account = Column(String(100), nullable=False)
    payee_name = Column(String(50), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    paid_amount = Column(DECIMAL(10, 2), default=0)
    reason = Column(Text, nullable=False)
    voucher_path = Column(String(255))
    status = Column(Enum("pending_review", "approved", "rejected", "paid", "failed", "processing", "partial_paid", "deleted"), default="pending_review")
    payment_time_type = Column(Enum("immediate", "long_term", "scheduled"), default="immediate")
    scheduled_payment_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    reviewed_by = Column(Integer)
    reviewed_at = Column(TIMESTAMP)
    review_comment = Column(Text)
    paid_at = Column(TIMESTAMP)
    trade_no = Column(Text)
    error_message = Column(Text)
    is_offline = Column(SmallInteger, default=0)
    offline_payment_type = Column(Enum("cash", "bank", "corporate"))
    offline_remark = Column(Text)
    offline_voucher_path = Column(String(255))
    source_system = Column(String(50))
    source_order_id = Column(Integer)
    source_order_type = Column(String(50))

    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    creator = relationship("User", foreign_keys=[created_by])
    records = relationship("AdminPaymentRecord", back_populates="payment")


class AdminPaymentRecord(Base):
    __tablename__ = "admin_payment_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("admin_payments.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    payment_method = Column(Enum("alipay", "cash", "bank", "corporate"), default="alipay")
    trade_no = Column(String(100))
    remark = Column(Text)
    voucher_path = Column(String(255))
    created_by = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    deleted_at = Column(TIMESTAMP)

    payment = relationship("AdminPayment", back_populates="records")


class SalaryPayment(Base):
    __tablename__ = "salary_payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    payment_month = Column(Date, nullable=False)
    description = Column(Text)
    status = Column(Enum("pending", "admin_review", "approved", "paid", "rejected"), default="pending")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="salary_payments", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum("pending", "approved", "paid", "rejected"), default="pending")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    paid_by = Column(Integer, ForeignKey("users.id"))
    paid_at = Column(DateTime)
    alipay_order_id = Column(String(64))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    creator = relationship("User", foreign_keys=[user_id])
    items = relationship("SupplierPaymentItem", back_populates="payment")


class SupplierPaymentItem(Base):
    __tablename__ = "supplier_payment_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("supplier_payments.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("supplier_products.id"), nullable=False)
    quantity = Column(DECIMAL(10, 2), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    payment = relationship("SupplierPayment", back_populates="items")
    product = relationship("SupplierProduct")


class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    category = Column(Enum("fruit", "package", "other"), nullable=False)
    unit = Column(String(20), nullable=False)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AdvancePayment(Base):
    __tablename__ = "advance_payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    repayment_date = Column(Date, nullable=False)
    status = Column(Enum("pending", "approved", "rejected", "repaid"), nullable=False, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.now())
    approved_at = Column(TIMESTAMP)
    repaid_at = Column(TIMESTAMP)
    comment = Column(Text)
    recorded_by = Column(Integer)

    user = relationship("User", foreign_keys=[user_id])


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(Enum("info", "warning", "danger", "success"), default="info")
    is_active = Column(SmallInteger, default=1)
    created_by = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class ExpressCompany(Base):
    __tablename__ = "express_companies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(100), nullable=False)
    contact_person = Column(String(50), nullable=False)
    alipay_account = Column(String(100), nullable=False)
    alipay_real_name = Column(String(50), nullable=False)
    unit_price = Column(DECIMAL(10, 2), default=0)
    status = Column(Enum("active", "inactive"), default="active")
    remark = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class ExpressOrder(Base):
    __tablename__ = "express_orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    express_company_id = Column(Integer, ForeignKey("express_companies.id"), nullable=False)
    company_name = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    alipay_account = Column(String(100), nullable=False)
    alipay_real_name = Column(String(50), nullable=False)
    status = Column(Enum("pending", "paid", "failed"), default="pending")
    trade_no = Column(String(100))
    remark = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    paid_at = Column(TIMESTAMP)
    error_message = Column(Text)

    company = relationship("ExpressCompany", foreign_keys=[express_company_id])
    creator = relationship("User", foreign_keys=[created_by])


class DailyShipment(Base):
    __tablename__ = "daily_shipments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_name = Column(String(100), nullable=False)
    fruit_name = Column(String(50))
    weight = Column(DECIMAL(10, 2))
    quantity = Column(Integer, nullable=False)
    ship_date = Column(Date, nullable=False)
    unit_cost = Column(DECIMAL(10, 2), nullable=False)
    fruit_cost = Column(DECIMAL(10, 2))
    other_costs = Column(DECIMAL(10, 2))
    shipping_cost = Column(DECIMAL(10, 2), nullable=False)
    total_cost = Column(DECIMAL(10, 2), nullable=False)
    description = Column(Text)
    status = Column(Enum("pending", "paid"), default="pending")
    finance_confirmed = Column(SmallInteger, default=0)
    finance_confirmed_by = Column(Integer, ForeignKey("users.id"))
    finance_confirmed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200))
    content = Column(Text)
    type = Column(String(50), default="info")
    is_read = Column(SmallInteger, default=0)
    link = Column(String(500))
    created_at = Column(TIMESTAMP, server_default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False)
    setting_value = Column(Text)
    description = Column(Text)
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class WarehouseInbox(Base):
    __tablename__ = "warehouse_inbox"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_system = Column(String(50), nullable=False, default="fruit-admin")
    source_order_id = Column(Integer, nullable=False)
    source_order_type = Column(String(50), nullable=False)
    supplier_name_from_warehouse = Column(String(200), nullable=False)
    mapped_supplier_id = Column(Integer)
    amount = Column(DECIMAL(10, 2), nullable=False)
    unit_price = Column(DECIMAL(10, 4))
    quantity = Column(DECIMAL(10, 2))
    reason = Column(Text)
    remark = Column(Text)
    status = Column(Enum("pending", "approved", "rejected", "converted", "frozen"), default="pending")
    admin_payment_id = Column(Integer)
    reviewed_by = Column(Integer)
    reviewed_at = Column(TIMESTAMP)
    review_note = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())


class SupplierChain(Base):
    __tablename__ = "supplier_chain"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    alipay_account = Column(String(100), nullable=False)
    alipay_real_name = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    contract_no = Column(String(50), default="")
    party_a = Column(String(100), default="")
    party_b = Column(String(100), default="")
    category = Column(String(30), default="other")
    amount = Column(DECIMAL(12, 2), default=0)
    sign_date = Column(Date)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(20), default="draft")
    description = Column(Text)
    created_by = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    check_date = Column(Date, nullable=False)
    check_in = Column(Time)
    check_out = Column(Time)
    status = Column(String(20), default="normal")
    work_hours = Column(DECIMAL(4, 2), default=0)
    ip_address = Column(String(50))
    note = Column(String(200), default="")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
