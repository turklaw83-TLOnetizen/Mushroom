# ---- Users Router --------------------------------------------------------
# Authentication and user management endpoints.
#
# Fix #14: Input length validation on all request models

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.auth import (
    _create_jwt,
    get_current_user,
    hash_pin,
    require_role,
)
from api.deps import get_user_manager
from api.schemas import SHORT_TEXT_MAX, PaginatedResponse, paginate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


# ---- Schemas -------------------------------------------------------------

class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=SHORT_TEXT_MAX)
    pin: str = Field(default="", max_length=20)


class UserResponse(BaseModel):
    id: str
    name: str = ""
    initials: str = ""
    role: str = "attorney"
    email: str = ""
    active: bool = True

    model_config = {"extra": "allow"}


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=SHORT_TEXT_MAX)
    role: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=SHORT_TEXT_MAX)
    initials: Optional[str] = Field(default=None, max_length=10)


class TeamStatsResponse(BaseModel):
    total_users: int = 0
    active_users: int = 0
    admins: int = 0
    attorneys: int = 0
    paralegals: int = 0

    model_config = {"extra": "allow"}


# ---- Endpoints -----------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """
    Authenticate via PIN (legacy/development auth).
    Returns a JWT token for subsequent requests.
    """
    um = get_user_manager()
    user = um.get_user(body.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.get("active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User deactivated")

    if not um.authenticate(body.user_id, body.pin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")

    um.record_login(body.user_id)

    token = _create_jwt(
        user_id=body.user_id,
        role=user.get("role", "attorney"),
        name=user.get("name", ""),
    )

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user.get("id", body.user_id),
            name=user.get("name", ""),
            initials=user.get("initials", ""),
            role=user.get("role", "attorney"),
            email=user.get("email", ""),
            active=user.get("active", True),
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    um = get_user_manager()
    profile = um.get_user(user["id"])
    if profile:
        profile.pop("pin_hash", None)
        return profile
    return user


@router.get("", response_model=PaginatedResponse)
def list_users(
    include_inactive: bool = False,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    user: dict = Depends(require_role("admin")),
):
    """List all users (admin only, paginated)."""
    um = get_user_manager()
    users = um.list_users(include_inactive=include_inactive)
    for u in users:
        u.pop("pin_hash", None)
    return paginate(users, page, per_page)


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    user: dict = Depends(require_role("admin")),
):
    """Update a user's profile (admin only)."""
    um = get_user_manager()
    target = um.get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    um.update_user(user_id, updates)
    return {"status": "updated", "user_id": user_id}


@router.get("/team-stats", response_model=TeamStatsResponse)
def team_stats(user: dict = Depends(require_role("admin"))):
    """Get team statistics."""
    um = get_user_manager()
    return um.get_team_stats()
