from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models as m
from .db import get_db
from .graphs import GraphFilters
from .security import decode_token, has_permission

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> m.ResearchUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Perlu login.")
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak valid atau kedaluwarsa.")
    user = db.get(m.ResearchUser, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Akun tidak aktif.")
    return user


def require(perm: str) -> Callable[..., m.ResearchUser]:
    def dep(user: m.ResearchUser = Depends(current_user)) -> m.ResearchUser:
        if not has_permission(user.role, perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Peran '{user.role}' tidak memiliki izin '{perm}'.")
        return user
    return dep


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _split(v: str | None) -> list[str]:
    return [x for x in (v or "").split(",") if x]


def _dt(d: date | None, end: bool = False) -> datetime | None:
    if d is None:
        return None
    return datetime.combine(d, time.max if end else time.min, tzinfo=timezone.utc)


def graph_filters(layer: str = Query("aktor", pattern="^(aktor|konten|bipartit)$"),
                  platforms: str | None = None, categories: str | None = None, interaction_types: str | None = None,
                  evidence_statuses: str | None = None, start: date | None = None, end: date | None = None,
                  min_weight: float = Query(1.0, ge=0), include_similarity: bool = True) -> GraphFilters:
    return GraphFilters(layer=layer, platforms=_split(platforms), categories=_split(categories),
                        interaction_types=_split(interaction_types), evidence_statuses=_split(evidence_statuses),
                        start=_dt(start), end=_dt(end, True), min_weight=min_weight, include_similarity=include_similarity)
