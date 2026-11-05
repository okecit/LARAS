from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from ..db import get_db
from ..deps import client_ip, current_user, require
from ..security import ROLE_LABELS, create_token, hash_password, permissions_for, verify_password
from ..services import audit

router = APIRouter(prefix="/api", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def user_out(u: m.ResearchUser) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role,
            "role_label": ROLE_LABELS.get(u.role, u.role), "permissions": permissions_for(u.role), "is_active": u.is_active,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalars(select(m.ResearchUser).where(m.ResearchUser.username == body.username.strip().lower())).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        audit(db, None, "login_gagal", "user", body.username[:64], ip=client_ip(request))
        db.commit()
        raise HTTPException(401, "Nama pengguna atau kata sandi salah.")
    user.last_login_at = datetime.now(timezone.utc)
    audit(db, user, "login", "user", user.id, ip=client_ip(request))
    db.commit()
    return {"access_token": create_token(user.id, user.username, user.role), "token_type": "bearer", "user": user_out(user)}


@router.get("/auth/me")
def me(user: m.ResearchUser = Depends(current_user)):
    return user_out(user)


@router.get("/auth/demo-accounts")
def demo_accounts():
    """Daftar akun demo (hanya mode DEMO) — membantu evaluasi peran tanpa membuka kata sandi."""
    if settings.data_mode != "DEMO":
        return []
    return [{"username": u, "role": r, "role_label": ROLE_LABELS[r]} for u, r in
            [("ketua", "peneliti_utama"), ("peneliti", "peneliti"), ("peninjau", "peninjau"), ("pengamat", "pengamat"), ("admin", "admin")]]


class UserIn(BaseModel):
    username: str
    display_name: str
    role: str
    password: str


class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.get("/users")
def list_users(db: Session = Depends(get_db), _=Depends(require("manage_users"))):
    return [user_out(u) for u in db.scalars(select(m.ResearchUser).order_by(m.ResearchUser.id))]


@router.post("/users")
def create_user(body: UserIn, request: Request, db: Session = Depends(get_db), admin=Depends(require("manage_users"))):
    if body.role not in ROLE_LABELS:
        raise HTTPException(422, "Peran tidak valid.")
    if len(body.password) < 10:
        raise HTTPException(422, "Kata sandi minimal 10 karakter.")
    uname = body.username.strip().lower()
    if db.scalars(select(m.ResearchUser).where(m.ResearchUser.username == uname)).first():
        raise HTTPException(409, "Nama pengguna sudah dipakai.")
    u = m.ResearchUser(username=uname, display_name=body.display_name, role=body.role, password_hash=hash_password(body.password))
    db.add(u)
    db.flush()
    audit(db, admin, "buat_pengguna", "user", u.id, {"role": body.role}, client_ip(request))
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, request: Request, db: Session = Depends(get_db), admin=Depends(require("manage_users"))):
    u = db.get(m.ResearchUser, user_id)
    if not u:
        raise HTTPException(404, "Pengguna tidak ditemukan.")
    changes = {}
    if body.role is not None:
        if body.role not in ROLE_LABELS:
            raise HTTPException(422, "Peran tidak valid.")
        u.role = changes["role"] = body.role
    if body.is_active is not None:
        if u.id == admin.id and not body.is_active:
            raise HTTPException(422, "Tidak dapat menonaktifkan akun sendiri.")
        u.is_active = changes["is_active"] = body.is_active
    if body.password:
        if len(body.password) < 10:
            raise HTTPException(422, "Kata sandi minimal 10 karakter.")
        u.password_hash = hash_password(body.password)
        changes["password"] = "diubah"
    audit(db, admin, "ubah_pengguna", "user", u.id, changes, client_ip(request))
    db.commit()
    return user_out(u)
