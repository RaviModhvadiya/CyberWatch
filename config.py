import json
import os
import secrets

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# domain constants live in a data file instead of code
with open(os.path.join(BASE_DIR, "app", "data", "defaults.json"), encoding="utf-8") as handle:
    DEFAULTS = json.load(handle)


def env_int(name, fallback):
    # read an integer setting from the environment
    return int(os.getenv(name) or fallback)


def database_uri():
    # use the configured database or fall back to a local sqlite file
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return "sqlite:///" + os.path.join(BASE_DIR, "instance", "cyberwatch.db").replace("\\", "/")


class Config:
    # flask core
    APP_NAME = os.getenv("APP_NAME") or "CyberWatch"
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    HOST = os.getenv("HOST") or "127.0.0.1"
    PORT = env_int("PORT", 5000)
    DEBUG = os.getenv("DEBUG", "0") == "1"
    SQLALCHEMY_DATABASE_URI = database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = env_int("MAX_UPLOAD_MB", 25) * 1024 * 1024
    ALLOWED_EXTENSIONS = {e.strip().lower() for e in (os.getenv("ALLOWED_EXTENSIONS") or "log,txt,csv").split(",")}

    # detection and dashboard tuning
    FAILED_STATUS = env_int("FAILED_STATUS", 401)
    SUCCESS_MIN = env_int("SUCCESS_MIN", 200)
    SUCCESS_MAX = env_int("SUCCESS_MAX", 299)
    HIGH_RISK_ALERTS = env_int("HIGH_RISK_ALERTS", 5)
    SCORE_SCALE = env_int("SCORE_SCALE", 400)
    TOP_IP_LIMIT = env_int("TOP_IP_LIMIT", 8)
    TREND_DAYS = env_int("TREND_DAYS", 14)
    CONTEXT_ROWS = env_int("CONTEXT_ROWS", 8)
    REFRESH_SECONDS = env_int("REFRESH_SECONDS", 30)

    # paging, accounts and reports
    PAGE_SIZE = env_int("PAGE_SIZE", 25)
    MIN_PASSWORD_LENGTH = env_int("MIN_PASSWORD_LENGTH", 8)
    REPORT_MAX_ROWS = env_int("REPORT_MAX_ROWS", 5000)
    PDF_MAX_ROWS = env_int("PDF_MAX_ROWS", 300)
