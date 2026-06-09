import os

from flask import Blueprint, send_from_directory

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "auth.html")

@bp.get("/auth")
def auth_page():
    return send_from_directory(FRONTEND_DIR, "auth.html")

@bp.get("/apply")
def apply_page():
    return send_from_directory(FRONTEND_DIR, "apply.html")

@bp.get("/result")
def result_page():
    return send_from_directory(FRONTEND_DIR, "result.html")

@bp.get("/admin")
def admin_page():
    return send_from_directory(FRONTEND_DIR, "admin.html")
