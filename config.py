import os
from urllib.parse import quote_plus

DB_HOST = os.getenv("DB_HOST", "36.134.229.82")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "expense_system3")
DB_USER = os.getenv("DB_USER", "mz24639")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Amz24639@")

AFTER_SALE_DB_HOST = os.getenv("AFTER_SALE_DB_HOST", "rm-7xv5u91376nf5oqp0ro.mysql.rds.aliyuncs.com")
AFTER_SALE_DB_NAME = os.getenv("AFTER_SALE_DB_NAME", "my_after_sale")
AFTER_SALE_DB_USER = os.getenv("AFTER_SALE_DB_USER", "root")
AFTER_SALE_DB_PASS = os.getenv("AFTER_SALE_DB_PASS", "Amz24639@")

WAREHOUSE_DB_HOST = os.getenv("WAREHOUSE_DB_HOST", "36.134.229.82")
WAREHOUSE_DB_NAME = os.getenv("WAREHOUSE_DB_NAME", "my_sk9")
WAREHOUSE_DB_USER = os.getenv("WAREHOUSE_DB_USER", "root")
WAREHOUSE_DB_PASS = os.getenv("WAREHOUSE_DB_PASS", "Amz24639.")

DATABASE_URL = f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

SECRET_KEY = os.getenv("SECRET_KEY", "caiwu-secret-key-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

APP_VERSION = "v3.0.0"
APP_NAME = "财务管理系统"

DELETE_CONFIRM_PASSWORD = "qwe52030"
SETTINGS_PASSWORD = "Amz24639."
