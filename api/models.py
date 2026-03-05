# ---- SQLAlchemy Models ---------------------------------------------------
# Database schema for Project Mushroom Cloud.
# Uses SQLAlchemy 2.0 declarative style with JSONB for flexible data.

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


# ---- Cases ---------------------------------------------------------------

class Case(Base):
    __tablename__ = "cases"

    id = Column(String(64), primary_key=True)
    name = Column(String(512), nullable=False, index=True)
    description = Column(Text, default="")
    case_type = Column(String(64), default="criminal")
    case_category = Column(String(128), default="")
    case_subcategory = Column(String(128), default="")
    client_name = Column(String(256), default="")
    jurisdiction = Column(String(256), default="")
    phase = Column(String(32), default="active", index=True)
    sub_phase = Column(String(128), default="")
    status = Column(String(32), default="active")  # backward compat
    pinned = Column(Boolean, default=False)
    purged = Column(Boolean, default=False)
    purged_at = Column(DateTime(timezone=True), nullable=True)
    purged_file_count = Column(Integer, default=0)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    assigned_to = Column(JSONB, default=list)  # List[str] of user_ids
    docket_number = Column(String(128), default="")
    charges = Column(Text, default="")  # criminal cases only
    court_name = Column(String(256), default="")
    date_of_incident = Column(String(32), default="")  # ISO date string
    opposing_counsel = Column(String(256), default="")
    jurisdiction_type = Column(String(16), default="")  # "state" or "federal"
    county = Column(String(128), default="")
    district = Column(String(128), default="")
    metadata_extra = Column(JSONB, default=dict)  # Catch-all for misc metadata
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_updated = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    preparations = relationship("Preparation", back_populates="case", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="case", cascade="all, delete-orphan")
    file_metadata = relationship("FileMetadata", back_populates="case", cascade="all, delete-orphan")
    module_notes = relationship("ModuleNote", back_populates="case", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cases_phase_status", "phase", "status"),
    )

    def to_metadata_dict(self) -> dict:
        """Convert to the dict format that CaseManager expects."""
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "case_type": self.case_type or "criminal",
            "case_category": self.case_category or "",
            "case_subcategory": self.case_subcategory or "",
            "client_name": self.client_name or "",
            "jurisdiction": self.jurisdiction or "",
            "phase": self.phase or "active",
            "sub_phase": self.sub_phase or "",
            "status": self.status or "active",
            "pinned": self.pinned or False,
            "assigned_to": self.assigned_to or [],
            "docket_number": self.docket_number or "",
            "charges": self.charges or "",
            "court_name": self.court_name or "",
            "date_of_incident": self.date_of_incident or "",
            "opposing_counsel": self.opposing_counsel or "",
            "jurisdiction_type": self.jurisdiction_type or "",
            "county": self.county or "",
            "district": self.district or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "last_updated": self.last_updated.isoformat() if self.last_updated else "",
        }
        if self.purged:
            d["purged"] = True
            d["purged_at"] = self.purged_at.isoformat() if self.purged_at else ""
            d["purged_file_count"] = self.purged_file_count or 0
        if self.closed_at:
            d["closed_at"] = self.closed_at.isoformat()
        # Merge any extra metadata
        if self.metadata_extra:
            d.update(self.metadata_extra)
        return d

    @classmethod
    def from_metadata_dict(cls, d: dict) -> "Case":
        """Create a Case from a CaseManager-style metadata dict."""
        known_keys = {
            "id", "name", "description", "case_type", "case_category",
            "case_subcategory", "client_name", "jurisdiction", "phase",
            "sub_phase", "status", "pinned", "assigned_to", "created_at",
            "last_updated", "purged", "purged_at", "purged_file_count",
            "closed_at", "docket_number", "charges", "court_name",
            "date_of_incident", "opposing_counsel", "jurisdiction_type",
            "county", "district",
        }
        extra = {k: v for k, v in d.items() if k not in known_keys}

        return cls(
            id=d.get("id", _new_uuid()),
            name=d.get("name", "Untitled"),
            description=d.get("description", ""),
            case_type=d.get("case_type", "criminal"),
            case_category=d.get("case_category", ""),
            case_subcategory=d.get("case_subcategory", ""),
            client_name=d.get("client_name", ""),
            jurisdiction=d.get("jurisdiction", ""),
            phase=d.get("phase", d.get("status", "active")),
            sub_phase=d.get("sub_phase", ""),
            status=d.get("status", "active"),
            pinned=d.get("pinned", False),
            assigned_to=d.get("assigned_to", []),
            docket_number=d.get("docket_number", ""),
            charges=d.get("charges", ""),
            court_name=d.get("court_name", ""),
            date_of_incident=d.get("date_of_incident", ""),
            opposing_counsel=d.get("opposing_counsel", ""),
            jurisdiction_type=d.get("jurisdiction_type", ""),
            county=d.get("county", ""),
            district=d.get("district", ""),
            metadata_extra=extra if extra else {},
        )


# ---- Preparations --------------------------------------------------------

class Preparation(Base):
    __tablename__ = "preparations"

    id = Column(String(64), primary_key=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(256), default="")
    prep_type = Column(String(64), nullable=False, default="trial")
    state = Column(JSONB, nullable=True)  # The full prep state dict
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    last_updated = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    case = relationship("Case", back_populates="preparations")
    snapshots = relationship("Snapshot", back_populates="preparation", cascade="all, delete-orphan")
    module_notes = relationship("ModuleNote", back_populates="preparation", cascade="all, delete-orphan")

    def to_index_dict(self) -> dict:
        """Convert to the dict format in preparations.json."""
        return {
            "id": self.id,
            "type": self.prep_type,
            "name": self.name or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "last_updated": self.last_updated.isoformat() if self.last_updated else "",
        }


# ---- Snapshots -----------------------------------------------------------

class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(String(64), primary_key=True, default=_new_uuid)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    prep_id = Column(String(64), ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(JSONB, nullable=True)
    snapshot_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    case = relationship("Case", back_populates="snapshots")
    preparation = relationship("Preparation", back_populates="snapshots")


# ---- Activity Logs -------------------------------------------------------

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(128), nullable=False)
    description = Column(Text, default="")
    user_id = Column(String(64), default="")
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)

    case = relationship("Case", back_populates="activity_logs")

    __table_args__ = (
        Index("ix_activity_case_timestamp", "case_id", "timestamp"),
    )


# ---- File Metadata -------------------------------------------------------

class FileMetadata(Base):
    __tablename__ = "file_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    disk_path = Column(Text, nullable=False)
    file_size = Column(Integer, default=0)
    tags = Column(JSONB, default=list)  # List[str]
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    case = relationship("Case", back_populates="file_metadata")

    __table_args__ = (
        UniqueConstraint("case_id", "filename", name="uq_case_file"),
    )


# ---- Module Notes --------------------------------------------------------

class ModuleNote(Base):
    __tablename__ = "module_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    prep_id = Column(String(64), ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False)
    module_name = Column(String(128), nullable=False)
    content = Column(Text, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    case = relationship("Case", back_populates="module_notes")
    preparation = relationship("Preparation", back_populates="module_notes")

    __table_args__ = (
        UniqueConstraint("case_id", "prep_id", "module_name", name="uq_module_note"),
        Index("ix_module_notes_case_prep", "case_id", "prep_id"),
    )


# ---- Clients (CRM) -------------------------------------------------------

class Client(Base):
    __tablename__ = "clients"

    id = Column(String(64), primary_key=True, default=_new_uuid)
    name = Column(String(256), nullable=False, index=True)
    client_type = Column(String(64), default="prospective")  # active, prospective, former, declined
    contact_info = Column(JSONB, default=dict)  # phone, email, address, etc.
    intake_data = Column(JSONB, default=dict)  # intake form responses
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    case_links = relationship("CaseClient", back_populates="client", cascade="all, delete-orphan")


class CaseClient(Base):
    __tablename__ = "case_clients"

    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    client_id = Column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True)
    linked_at = Column(DateTime(timezone=True), default=_utcnow)

    client = relationship("Client", back_populates="case_links")


# ---- Users ---------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=_new_uuid)
    clerk_id = Column(String(256), unique=True, nullable=True, index=True)
    name = Column(String(256), nullable=False)
    initials = Column(String(8), default="")
    email = Column(String(256), default="", index=True)
    role = Column(String(32), default="attorney")  # admin, attorney, paralegal
    is_active = Column(Boolean, default=True)
    pin_hash = Column(String(128), default="")  # SHA-256 hashed PIN for legacy auth
    google_email = Column(String(256), default="")
    google_sub = Column(String(256), default="")
    assigned_cases = Column(JSONB, default=list)  # List[str] of case_ids
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ---- Global Settings -----------------------------------------------------

class GlobalSetting(Base):
    __tablename__ = "global_settings"

    key = Column(String(256), primary_key=True)
    value = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ---- Case JSON Data (generic per-case key-value) -------------------------
# Replaces the generic load_json/save_json that stored arbitrary .json files
# in the case directory. This covers directives.json, journal.json,
# contact_log.json, etc.

class CaseJsonData(Base):
    __tablename__ = "case_json_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(256), nullable=False)  # e.g. "directives.json"
    data = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "filename", name="uq_case_json"),
        Index("ix_case_json_case_file", "case_id", "filename"),
    )


# ---- Prep JSON Data (generic per-prep key-value) -------------------------
# Replaces load_prep_json/save_prep_json for arbitrary per-prep JSON files.

class PrepJsonData(Base):
    __tablename__ = "prep_json_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    prep_id = Column(String(64), ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(256), nullable=False)
    data = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "prep_id", "filename", name="uq_prep_json"),
        Index("ix_prep_json_case_prep_file", "case_id", "prep_id", "filename"),
    )


# ---- Case Text Data (generic per-case text files) -----------------------

class CaseTextData(Base):
    __tablename__ = "case_text_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(256), nullable=False)
    content = Column(Text, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "filename", name="uq_case_text"),
    )


# ---- Prep Text Data (generic per-prep text files) -----------------------

class PrepTextData(Base):
    __tablename__ = "prep_text_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    prep_id = Column(String(64), ForeignKey("preparations.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(256), nullable=False)
    content = Column(Text, default="")
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "prep_id", "filename", name="uq_prep_text"),
    )
