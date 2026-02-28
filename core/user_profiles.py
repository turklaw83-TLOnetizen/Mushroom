"""
AllRise Beta — User Profiles & Role-Based Access
=================================================
Manage firm staff profiles with role-based case access control.

Roles:
    admin     — Full access to all cases and user management
    attorney  — Access to assigned cases only
    paralegal — Access to assigned cases, limited admin features

Storage: data/users/profiles.json
"""

import os
import json
import uuid
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_USERS_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "users")
_PROFILES_FILE = os.path.join(_USERS_DIR, "profiles.json")

ROLES = ["admin", "attorney", "paralegal"]
ROLE_LABELS = {"admin": "Admin", "attorney": "Attorney", "paralegal": "Paralegal"}


def _ensure_dir():
    os.makedirs(_USERS_DIR, exist_ok=True)


def _hash_pin(pin: str) -> str:
    """One-way hash a PIN for storage."""
    if not pin:
        return ""
    return hashlib.sha256(pin.encode()).hexdigest()


# ===================================================================
#  SEED DATA — run on first use
# ===================================================================

def _seed_defaults() -> List[Dict]:
    """Create the initial 2 attorney profiles."""
    return [
        {
            "id": "djt-49a",
            "name": "Daniel Joseph Turklay",
            "initials": "DJT",
            "email": "",
            "google_email": "",
            "google_sub": "",
            "role": "admin",
            "pin_hash": "",
            "assigned_cases": [],
            "active": True,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
        },
        {
            "id": "crj-82b",
            "name": "Cody Ryan Johnson",
            "initials": "CRJ",
            "email": "",
            "google_email": "",
            "google_sub": "",
            "role": "admin",
            "pin_hash": "",
            "assigned_cases": [],
            "active": True,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
        },
    ]


# ===================================================================
#  USER MANAGER
# ===================================================================

class UserManager:
    """Manages firm staff profiles and case access control."""

    def __init__(self):
        _ensure_dir()
        self._profiles: List[Dict] = self._load()

    # -- Persistence ------------------------------------------------
    def _load(self) -> List[Dict]:
        if os.path.exists(_PROFILES_FILE):
            try:
                with open(_PROFILES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception:
                pass
        # First run — seed default profiles
        defaults = _seed_defaults()
        self._save_raw(defaults)
        return defaults

    def _save(self):
        self._save_raw(self._profiles)

    def _save_raw(self, data: List[Dict]):
        try:
            _ensure_dir()
            with open(_PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # -- CRUD -------------------------------------------------------
    def list_users(self, include_inactive: bool = False) -> List[Dict]:
        """List all user profiles (active by default)."""
        if include_inactive:
            return list(self._profiles)
        return [u for u in self._profiles if u.get("active", True)]

    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get a single user by ID."""
        for u in self._profiles:
            if u["id"] == user_id:
                return u
        return None

    def create_user(
        self,
        name: str,
        role: str = "attorney",
        initials: str = "",
        email: str = "",
        pin: str = "",
        google_email: str = "",
    ) -> Dict:
        """Create a new user profile. Returns the profile dict."""
        if role not in ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {ROLES}")

        # Generate a short, non-guessable ID
        short_id = str(uuid.uuid4())[:3]
        user_id = f"{initials.lower() or name[:3].lower()}-{short_id}"

        profile = {
            "id": user_id,
            "name": name,
            "initials": initials or "".join(w[0].upper() for w in name.split() if w),
            "email": email,
            "google_email": google_email,
            "google_sub": "",
            "role": role,
            "pin_hash": _hash_pin(pin),
            "assigned_cases": [],
            "active": True,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
        }
        self._profiles.append(profile)
        self._save()
        return profile

    def update_user(self, user_id: str, updates: Dict) -> bool:
        """Update fields on a user. Returns True if found."""
        user = self.get_user(user_id)
        if not user:
            return False

        # Handle PIN separately (hash it)
        if "pin" in updates:
            updates["pin_hash"] = _hash_pin(updates.pop("pin"))

        # Prevent changing immutable fields
        for key in ("id", "created_at"):
            updates.pop(key, None)

        user.update(updates)
        self._save()
        return True

    def deactivate_user(self, user_id: str) -> bool:
        """Soft-delete a user. Returns True if found."""
        return self.update_user(user_id, {"active": False})

    def reactivate_user(self, user_id: str) -> bool:
        """Re-enable a deactivated user."""
        return self.update_user(user_id, {"active": True})

    # -- Authentication ---------------------------------------------
    def authenticate(self, user_id: str, pin: str = "") -> bool:
        """
        Verify a user's PIN. Returns True if:
        - User exists and is active
        - PIN matches (or user has no PIN set)
        """
        user = self.get_user(user_id)
        if not user or not user.get("active", True):
            return False

        stored_hash = user.get("pin_hash", "")
        if not stored_hash:
            # No PIN set — allow access
            return True

        return _hash_pin(pin) == stored_hash

    def record_login(self, user_id: str):
        """Update last_login timestamp."""
        user = self.get_user(user_id)
        if user:
            user["last_login"] = datetime.now().isoformat()
            self._save()

    # -- Google Account Linking -------------------------------------
    def find_by_google_email(self, email: str) -> Optional[Dict]:
        """Find an active user by their linked Google email (case-insensitive)."""
        email_lower = (email or "").lower().strip()
        if not email_lower:
            return None
        for u in self._profiles:
            if not u.get("active", True):
                continue
            g_email = (u.get("google_email") or "").lower().strip()
            if g_email and g_email == email_lower:
                return u
        return None

    def link_google_account(self, user_id: str, email: str, sub: str = "") -> bool:
        """Link a Google account to an existing user profile."""
        user = self.get_user(user_id)
        if not user:
            return False
        user["google_email"] = email
        user["google_sub"] = sub or ""
        self._save()
        return True

    # -- Case Assignment --------------------------------------------
    def assign_case(self, user_id: str, case_id: str) -> bool:
        """Assign a case to a user. Returns True if successful."""
        user = self.get_user(user_id)
        if not user:
            return False
        cases = user.get("assigned_cases", [])
        if case_id not in cases:
            cases.append(case_id)
            user["assigned_cases"] = cases
            self._save()
        return True

    def unassign_case(self, user_id: str, case_id: str) -> bool:
        """Remove a case assignment. Returns True if found."""
        user = self.get_user(user_id)
        if not user:
            return False
        cases = user.get("assigned_cases", [])
        if case_id in cases:
            cases.remove(case_id)
            user["assigned_cases"] = cases
            self._save()
            return True
        return False

    def get_cases_for_user(self, user_id: str) -> Optional[List[str]]:
        """
        Get case IDs accessible to a user.
        Returns None for admin (meaning ALL cases).
        Returns list of assigned case IDs for attorney/paralegal.
        """
        user = self.get_user(user_id)
        if not user:
            return []
        if user.get("role") == "admin":
            return None  # None = no filter, show all
        return list(user.get("assigned_cases", []))

    def get_users_for_case(self, case_id: str) -> List[Dict]:
        """Get all active users assigned to a specific case."""
        result = []
        for u in self._profiles:
            if not u.get("active", True):
                continue
            if u.get("role") == "admin":
                result.append(u)
            elif case_id in u.get("assigned_cases", []):
                result.append(u)
        return result

    def is_admin(self, user_id: str) -> bool:
        """Check if a user has admin role."""
        user = self.get_user(user_id)
        return user is not None and user.get("role") == "admin"

    # -- Role Helpers -----------------------------------------------
    def get_role_label(self, user_id: str) -> str:
        """Get display label for a user's role."""
        user = self.get_user(user_id)
        if not user:
            return "Unknown"
        return ROLE_LABELS.get(user.get("role", ""), user.get("role", ""))

    def get_display_name(self, user_id: str) -> str:
        """Get display name (initials + name) for a user."""
        user = self.get_user(user_id)
        if not user:
            return "Unknown User"
        return f"{user.get('initials', '')} — {user.get('name', '')}"

    # -- Stats ------------------------------------------------------
    def get_team_stats(self) -> Dict:
        """Basic stats about the team."""
        active = [u for u in self._profiles if u.get("active", True)]
        return {
            "total": len(self._profiles),
            "active": len(active),
            "admins": sum(1 for u in active if u.get("role") == "admin"),
            "attorneys": sum(1 for u in active if u.get("role") == "attorney"),
            "paralegals": sum(1 for u in active if u.get("role") == "paralegal"),
        }
