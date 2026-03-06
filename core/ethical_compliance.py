"""
AllRise Beta — Ethical Compliance Module
=======================================
Comprehensive ethics and compliance tools grounded in the
Tennessee Rules of Professional Conduct (TN RPC).

Features:
  1. Smart Conflict Check   (RPC 1.7, 1.9, 1.10, 1.18)
  2. Prospective Client Screening (RPC 1.18)
  3. Communication Gap Alerts     (RPC 1.4)
  4. Compliance Dashboard         (RPC 1.3)
  5. Trust Account Ledger         (RPC 1.15)
  6. Fee Agreement Tracker        (RPC 1.5)
  7. Evidence Preservation        (RPC 3.4)
  8. Withdrawal Checklist         (RPC 1.16)
  9. Supervision Tracker          (RPC 5.1, 5.3)
 10. Ethics Quick-Reference       (RPC 1.1)
 11. Reporting Obligations        (RPC 8.3)
"""

import os
import re
import json
import uuid
import logging
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, "data")

# ═══════════════════════════════════════════════════════════════════════
#  1.  SMART CONFLICT CHECK  (RPC 1.7 / 1.9 / 1.10)
# ═══════════════════════════════════════════════════════════════════════

# ── Nickname / Common-Variation Map ──────────────────────────────────
# Maps canonical names to all known short forms / variations.
# Built from US Census common first-name diminutives.

NICKNAME_MAP: Dict[str, List[str]] = {
    # ── Male names ──
    "alexander": ["alex", "al", "xander", "zander", "lex", "sander"],
    "andrew":    ["andy", "drew", "dru"],
    "anthony":   ["tony", "ant"],
    "benjamin":  ["ben", "benny", "benji"],
    "charles":   ["charlie", "chuck", "chas", "chip"],
    "christopher": ["chris", "topher", "kit"],
    "daniel":    ["dan", "danny"],
    "david":     ["dave", "davey", "davie"],
    "donald":    ["don", "donnie", "donny"],
    "douglas":   ["doug", "dougie"],
    "edward":    ["ed", "eddie", "eddy", "ted", "teddy", "ned"],
    "eugene":    ["gene"],
    "francis":   ["frank", "fran", "frankie"],
    "frederick": ["fred", "freddy", "freddie", "fritz"],
    "gabriel":   ["gabe", "gabby"],
    "george":    ["georgie"],
    "gerald":    ["gerry", "jerry"],
    "gregory":   ["greg", "gregg"],
    "harold":    ["harry", "hal"],
    "henry":     ["hank", "harry", "hal"],
    "howard":    ["howie"],
    "jacob":     ["jake", "jay"],
    "james":     ["jim", "jimmy", "jamie", "jas"],
    "jason":     ["jay", "jase"],
    "jeffrey":   ["jeff"],
    "jeremy":    ["jerry"],
    "jerome":    ["jerry"],
    "john":      ["johnny", "jon", "jack"],
    "jonathan":  ["jon", "johnny", "nate"],
    "joseph":    ["joe", "joey", "jo"],
    "joshua":    ["josh"],
    "kenneth":   ["ken", "kenny"],
    "lawrence":  ["larry", "lars"],
    "leonard":   ["leo", "len", "lenny"],
    "matthew":   ["matt", "matty"],
    "michael":   ["mike", "mikey", "mick", "mickey"],
    "nathan":    ["nate", "nat"],
    "nathaniel": ["nate", "nat", "nathan"],
    "nicholas":  ["nick", "nicky", "nico"],
    "patrick":   ["pat", "paddy", "rick"],
    "peter":     ["pete"],
    "philip":    ["phil"],
    "raymond":   ["ray"],
    "richard":   ["rick", "ricky", "rich", "dick", "dickey"],
    "robert":    ["bob", "bobby", "rob", "robby", "robbie", "bert"],
    "ronald":    ["ron", "ronnie", "ronny"],
    "samuel":    ["sam", "sammy"],
    "stephen":   ["steve", "stevie"],
    "steven":    ["steve", "stevie"],
    "theodore":  ["ted", "teddy", "theo"],
    "thomas":    ["tom", "tommy", "thom"],
    "timothy":   ["tim", "timmy"],
    "vincent":   ["vince", "vinny", "vin"],
    "walter":    ["walt", "wally"],
    "william":   ["will", "willy", "bill", "billy", "liam"],
    "zachary":   ["zach", "zack", "zak"],

    # ── Female names ──
    "abigail":     ["abby", "gail"],
    "alexandra":   ["alex", "lexi", "lexie", "sandra"],
    "amanda":      ["mandy", "mandi"],
    "barbara":     ["barb", "barbie", "babs"],
    "beatrice":    ["bea", "trixie"],
    "catherine":   ["cathy", "kate", "kathy", "cat", "kitty", "katie"],
    "caroline":    ["carrie", "carol"],
    "charlotte":   ["charlie", "lottie", "char"],
    "christina":   ["chris", "tina", "chrissie", "christy"],
    "cynthia":     ["cindy", "cindi"],
    "deborah":     ["debbie", "deb", "debra"],
    "dorothy":     ["dot", "dotty", "dottie"],
    "elizabeth":   ["liz", "lizzy", "beth", "betty", "eliza", "betsy", "liza", "libby", "ella"],
    "emily":       ["em", "emmy"],
    "evelyn":      ["evie", "eve", "lyn"],
    "florence":    ["flo", "florrie"],
    "frances":     ["fran", "frannie", "frankie"],
    "gabrielle":   ["gabby", "gabi", "elle"],
    "helen":       ["nell", "nellie", "lena"],
    "jacqueline":  ["jackie", "jacqui"],
    "jennifer":    ["jen", "jenny", "jenn"],
    "jessica":     ["jess", "jessie"],
    "josephine":   ["jo", "josie"],
    "judith":      ["judy", "judi"],
    "katherine":   ["kate", "kathy", "katie", "kat", "kay"],
    "kathryn":     ["kate", "kathy", "katie", "kat", "kay"],
    "kimberly":    ["kim", "kimmy"],
    "laura":       ["laurie"],
    "lillian":     ["lily", "lil", "lilli"],
    "madeline":    ["maddie", "maddy"],
    "margaret":    ["maggie", "meg", "marge", "margie", "peg", "peggy", "marg"],
    "mary":        ["marie", "molly", "polly", "mae"],
    "melissa":     ["mel", "missy", "lissa"],
    "mildred":     ["millie", "milly"],
    "miranda":     ["mandy", "randi"],
    "nancy":       ["nan", "nanny"],
    "natalie":     ["nat", "nattie"],
    "nicole":      ["nicky", "nikki", "cole"],
    "pamela":      ["pam", "pammy"],
    "patricia":    ["pat", "patty", "tricia", "trish"],
    "rebecca":     ["becky", "becca", "beck"],
    "rosemary":    ["rose", "rosie"],
    "samantha":    ["sam", "sammy"],
    "sandra":      ["sandy", "sandi"],
    "sarah":       ["sally", "sadie"],
    "stephanie":   ["steph", "stevie"],
    "susan":       ["sue", "susie", "suzy", "suzie"],
    "teresa":      ["terry", "terri", "tess", "tessa"],
    "theresa":     ["terry", "terri", "tess", "tessa"],
    "valerie":     ["val"],
    "victoria":    ["vicky", "vicki", "tori"],
    "virginia":    ["ginny", "ginger"],
    "vivian":      ["viv", "vivi"],
}

# Build a reverse lookup: nickname → set of canonical names
_REVERSE_NICKNAME: Dict[str, set] = {}
for _canonical, _nicks in NICKNAME_MAP.items():
    for _nick in _nicks:
        _REVERSE_NICKNAME.setdefault(_nick, set()).add(_canonical)
    # Also map canonical → itself
    _REVERSE_NICKNAME.setdefault(_canonical, set()).add(_canonical)


# ── Name Normalization ───────────────────────────────────────────────

_TITLES = [
    "mr.", "mrs.", "ms.", "dr.", "officer", "ofc.", "det.", "detective",
    "sgt.", "sergeant", "lt.", "lieutenant", "cpt.", "captain",
    "judge", "hon.", "honorable", "atty.", "attorney", "esq.",
    "jr.", "jr", "sr.", "sr", "iii", "ii", "iv", "ph.d.", "m.d.",
    "prof.", "professor", "rev.", "reverend", "gen.", "general",
    "col.", "colonel", "maj.", "major", "cpl.", "corporal",
]

def normalize_name(name: str) -> str:
    """Lowercase, strip titles/suffixes, collapse whitespace."""
    n = name.lower().strip()
    # Remove punctuation except hyphens and apostrophes in names
    n = re.sub(r"[,]", " ", n)
    for title in _TITLES:
        n = n.replace(title, "")
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _get_name_parts(name: str) -> Tuple[List[str], str]:
    """Split a normalized name into (first_parts, last_name).
    Assumes Western name order; last token is surname.
    Returns (all_parts_list, last_name)."""
    parts = name.split()
    if len(parts) == 0:
        return ([], "")
    return (parts, parts[-1])


def expand_name_variants(first_name: str) -> set:
    """Given a first name, return all known nickname variants (including itself)."""
    fn = first_name.lower().strip()
    variants = {fn}

    # Direct lookup: is this a canonical name?
    if fn in NICKNAME_MAP:
        variants.update(NICKNAME_MAP[fn])

    # Reverse lookup: is this a nickname?
    if fn in _REVERSE_NICKNAME:
        for canonical in _REVERSE_NICKNAME[fn]:
            variants.add(canonical)
            if canonical in NICKNAME_MAP:
                variants.update(NICKNAME_MAP[canonical])

    return variants


# ── Matching Functions ───────────────────────────────────────────────

def fuzzy_name_score(a: str, b: str) -> float:
    """Returns 0.0 – 1.0 similarity using SequenceMatcher (stdlib)."""
    return SequenceMatcher(None, a, b).ratio()


def initial_match(a: str, b: str) -> bool:
    """Check if one name uses initials that match the other.
    E.g., 'J. Smith' matches 'John Smith', 'James Smith', etc.
    """
    a_parts = a.split()
    b_parts = b.split()

    if len(a_parts) < 2 or len(b_parts) < 2:
        return False

    # Last names must be similar
    if fuzzy_name_score(a_parts[-1], b_parts[-1]) < 0.80:
        return False

    # Check if either first name is an initial (single letter or letter + period)
    a_first = a_parts[0].rstrip(".")
    b_first = b_parts[0].rstrip(".")

    if len(a_first) == 1 and len(b_first) > 1:
        return b_first.startswith(a_first)
    if len(b_first) == 1 and len(a_first) > 1:
        return a_first.startswith(b_first)

    return False


def nickname_match(a: str, b: str) -> bool:
    """Check if two names share a nickname/variant relationship.
    Compares first names after expanding all known variants.
    Last names must match (fuzzy ≥ 0.85).
    """
    a_parts = a.split()
    b_parts = b.split()

    if len(a_parts) < 2 or len(b_parts) < 2:
        return False

    # Last names must be similar
    if fuzzy_name_score(a_parts[-1], b_parts[-1]) < 0.85:
        return False

    a_first = a_parts[0]
    b_first = b_parts[0]

    if a_first == b_first:
        return False  # Not a *nickname* match — would be exact or partial

    a_variants = expand_name_variants(a_first)
    b_variants = expand_name_variants(b_first)

    # If any variant overlaps, it's a nickname match
    return bool(a_variants & b_variants)


def smart_name_match(a: str, b: str) -> Tuple[str, float, str]:
    """
    Master matching function. Tries all strategies in priority order.

    Returns: (match_type, confidence, explanation)
      match_type: "exact", "nickname", "fuzzy", "initial", "partial", or ""
      confidence: 0.0 – 1.0
      explanation: human-readable description of why the match was flagged
    """
    na = normalize_name(a)
    nb = normalize_name(b)

    if not na or not nb or len(na) < 3 or len(nb) < 3:
        return ("", 0.0, "")

    # 1. Exact match
    if na == nb:
        return ("exact", 1.0, f'Exact match after normalization: "{na}"')

    # 2. Nickname / variation match
    if nickname_match(na, nb):
        return ("nickname", 0.92, f'Name variation: "{a}" is a known variant of "{b}"')

    # 3. Fuzzy match (catches typos like "Jon" vs "John", "Smyth" vs "Smith")
    score = fuzzy_name_score(na, nb)
    if score >= 0.85:
        pct = int(score * 100)
        return ("fuzzy", score, f'{pct}% similar: "{a}" ≈ "{b}"')

    # 4. Initial match ("J. Smith" → "John Smith")
    if initial_match(na, nb):
        return ("initial", 0.75, f'Initial match: "{a}" could be "{b}"')

    # 5. Partial match — shared name parts (at least 2 parts in common)
    a_parts = set(na.split())
    b_parts = set(nb.split())
    if len(a_parts) >= 2 and len(b_parts) >= 2:
        shared = a_parts & b_parts
        if len(shared) >= 2:
            return ("partial", 0.65, f'Shared name parts: {", ".join(sorted(shared))}')

    # 6. Substring match for longer names
    if (len(na) >= 5 or len(nb) >= 5) and (na in nb or nb in na):
        return ("partial", 0.55, f'Substring match: "{min(a,b,key=len)}" within "{max(a,b,key=len)}"')

    # 7. Last-resort fuzzy for longer names
    if len(na) >= 8 and len(nb) >= 8 and score >= 0.75:
        pct = int(score * 100)
        return ("fuzzy", score, f'{pct}% similar (long name): "{a}" ≈ "{b}"')

    return ("", 0.0, "")


def severity_for_match(match_type: str) -> str:
    """Map match type to severity indicator."""
    return {
        "exact":    "🔴 HIGH",
        "nickname": "🔴 HIGH",
        "fuzzy":    "🟡 MEDIUM",
        "initial":  "🟡 MEDIUM",
        "partial":  "🟠 LOW",
    }.get(match_type, "")


def scan_conflicts_smart(current_case_id: str, all_entities: dict,
                         prospective_clients: list = None) -> dict:
    """
    Enhanced conflict scanner with fuzzy matching, nickname detection,
    initial matching, and prospective client screening.

    Args:
        current_case_id: The case to check for conflicts
        all_entities: Output of CaseManager.load_all_entities()
        prospective_clients: Optional list of prospective client records

    Returns: {
        "conflicts": [{name, matched_name, current_role, other_case, other_case_id,
                       other_role, severity, match_type, confidence, explanation}],
        "prospective_hits": [{name, matched_name, subject, date, severity, explanation}],
        "cases_scanned": int,
        "entities_checked": int,
    }
    """
    current_entities = all_entities.get(current_case_id, [])
    if not current_entities:
        return {
            "conflicts": [],
            "prospective_hits": [],
            "message": "No entities found for current case. Run Entity Extraction first or add entities manually.",
            "cases_scanned": 0,
            "entities_checked": 0,
        }

    conflicts = []
    seen_pairs = set()

    # ── Cross-case entity matching ──
    for other_case_id, other_entities in all_entities.items():
        if other_case_id == current_case_id:
            continue

        for ce in current_entities:
            for oe in other_entities:
                ce_name = ce.get("name", "")
                oe_name = oe.get("name", "")
                match_type, confidence, explanation = smart_name_match(ce_name, oe_name)

                if match_type:
                    pair_key = f"{normalize_name(ce_name)}|{other_case_id}"
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    conflicts.append({
                        "name": ce_name,
                        "matched_name": oe_name,
                        "current_role": ce.get("role", "—"),
                        "current_source": ce.get("source", ""),
                        "other_case": oe.get("case_name", other_case_id),
                        "other_case_id": other_case_id,
                        "other_role": oe.get("role", "—"),
                        "other_source": oe.get("source", ""),
                        "severity": severity_for_match(match_type),
                        "match_type": match_type,
                        "confidence": confidence,
                        "explanation": explanation,
                    })

    # ── Prospective client screening (RPC 1.18) ──
    prospective_hits = []
    if prospective_clients:
        for ce in current_entities:
            for pc in prospective_clients:
                match_type, confidence, explanation = smart_name_match(
                    ce.get("name", ""), pc.get("name", "")
                )
                if match_type:
                    prospective_hits.append({
                        "name": ce.get("name", ""),
                        "matched_name": pc.get("name", ""),
                        "subject": pc.get("subject", ""),
                        "date": pc.get("date", ""),
                        "severity": severity_for_match(match_type),
                        "match_type": match_type,
                        "confidence": confidence,
                        "explanation": explanation,
                    })

    # Sort: HIGH first, then by name
    conflicts.sort(key=lambda c: (
        0 if "HIGH" in c["severity"] else 1 if "MEDIUM" in c["severity"] else 2,
        c["name"]
    ))
    prospective_hits.sort(key=lambda c: (
        0 if "HIGH" in c["severity"] else 1,
        c["name"]
    ))

    return {
        "conflicts": conflicts,
        "prospective_hits": prospective_hits,
        "cases_scanned": len(all_entities) - 1,
        "entities_checked": len(current_entities),
    }


# ═══════════════════════════════════════════════════════════════════════
#  2.  PROSPECTIVE CLIENT SCREENING  (RPC 1.18)
# ═══════════════════════════════════════════════════════════════════════

_PROSPECTIVE_PATH = os.path.join(_DATA_DIR, "prospective_clients.json")

def load_prospective_clients() -> List[Dict]:
    """Load all prospective client records (firm-wide)."""
    if os.path.exists(_PROSPECTIVE_PATH):
        with open(_PROSPECTIVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_prospective_clients(clients: List[Dict]):
    os.makedirs(os.path.dirname(_PROSPECTIVE_PATH), exist_ok=True)
    with open(_PROSPECTIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(clients, f, indent=2)

def save_prospective_client(name: str, subject: str = "",
                            disclosed_info: str = "", consultation_date: str = "",
                            notes: str = "", declined_reason: str = "") -> str:
    """Add a new prospective client record. Returns the record ID."""
    clients = load_prospective_clients()
    rec = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "subject": subject,
        "disclosed_info": disclosed_info,
        "date": consultation_date or datetime.now().strftime("%Y-%m-%d"),
        "notes": notes,
        "declined_reason": declined_reason,
        "created_at": datetime.now().isoformat(),
    }
    clients.append(rec)
    _save_prospective_clients(clients)
    return rec["id"]

def delete_prospective_client(client_id: str):
    """Remove a prospective client record by ID."""
    clients = load_prospective_clients()
    clients = [c for c in clients if c.get("id") != client_id]
    _save_prospective_clients(clients)

def update_prospective_client(client_id: str, updates: Dict):
    """Update fields on a prospective client record."""
    clients = load_prospective_clients()
    for c in clients:
        if c.get("id") == client_id:
            c.update(updates)
            c["updated_at"] = datetime.now().isoformat()
            break
    _save_prospective_clients(clients)


# ═══════════════════════════════════════════════════════════════════════
#  3.  COMMUNICATION GAP ALERTS  (RPC 1.4)
# ═══════════════════════════════════════════════════════════════════════

def get_communication_gaps(case_mgr, threshold_days: int = 30) -> List[Dict]:
    """
    Scans all active cases for communication gaps.
    Returns cases where no contact log entry exists within threshold_days.
    """
    gaps = []
    cases = case_mgr.list_cases()
    today = date.today()

    for case in cases:
        cid = case["id"]
        status = case_mgr.get_status(cid)
        if status in ("archived", "closed_resolved", "closed_dismissed",
                       "closed_convicted", "closed_acquitted", "closed_settled"):
            continue

        contact_log = case_mgr.load_contact_log(cid)

        if not contact_log:
            # No contacts ever — flag it
            gaps.append({
                "case_id": cid,
                "case_name": case.get("name", cid),
                "last_contact": None,
                "days_since": None,
                "urgency": "🔴 No contact on record",
                "status": status or "active",
            })
            continue

        # Find most recent contact date
        latest = None
        for entry in contact_log:
            d = entry.get("contact_date", entry.get("created_at", ""))
            if d:
                try:
                    dt = datetime.fromisoformat(d).date() if "T" in d else datetime.strptime(d, "%Y-%m-%d").date()
                    if latest is None or dt > latest:
                        latest = dt
                except (ValueError, TypeError):
                    pass

        if latest is None:
            gaps.append({
                "case_id": cid,
                "case_name": case.get("name", cid),
                "last_contact": None,
                "days_since": None,
                "urgency": "🟡 Contact dates unparseable",
                "status": status or "active",
            })
            continue

        days = (today - latest).days
        if days >= threshold_days:
            if days >= 60:
                urgency = f"🔴 {days} days — CRITICAL"
            elif days >= 45:
                urgency = f"🟠 {days} days — Overdue"
            else:
                urgency = f"🟡 {days} days — Due soon"

            gaps.append({
                "case_id": cid,
                "case_name": case.get("name", cid),
                "last_contact": latest.isoformat(),
                "days_since": days,
                "urgency": urgency,
                "status": status or "active",
            })

    # Sort: most urgent first
    gaps.sort(key=lambda g: (
        0 if "CRITICAL" in g["urgency"] or "No contact" in g["urgency"] else
        1 if "Overdue" in g["urgency"] else 2,
        -(g.get("days_since") or 999)
    ))
    return gaps


# ═══════════════════════════════════════════════════════════════════════
#  4.  COMPLIANCE DASHBOARD  (RPC 1.3 + aggregate)
# ═══════════════════════════════════════════════════════════════════════

def get_compliance_dashboard(case_mgr) -> Dict:
    """
    Aggregates all compliance items into a single dashboard payload.
    Returns: {
        overdue_deadlines: [...],
        upcoming_deadlines: [...],
        communication_gaps: [...],
        missing_fee_agreements: [...],
        prospective_unscreened: [...],
        score: int (0-100),
    }
    """
    # ── Deadlines ──
    all_deadlines = case_mgr.get_all_deadlines()
    today = date.today()
    overdue = []
    upcoming = []

    for dl in all_deadlines:
        dl_date_str = dl.get("date", "")
        try:
            dl_date = datetime.strptime(dl_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        days_until = (dl_date - today).days
        dl["days_until"] = days_until

        if days_until < 0:
            dl["urgency"] = f"🔴 OVERDUE by {abs(days_until)} days"
            overdue.append(dl)
        elif days_until <= 7:
            dl["urgency"] = f"🟡 Due in {days_until} day{'s' if days_until != 1 else ''}"
            upcoming.append(dl)

    # ── Communication Gaps ──
    comm_gaps = get_communication_gaps(case_mgr, threshold_days=30)

    # ── Fee Agreements ──
    missing_fees = get_cases_missing_fee_agreement(case_mgr)

    # ── Prospective clients not screened ──
    prospective = load_prospective_clients()
    # (all are "unscreened" until they appear in a conflict check result)

    # ── Compliance Score ──
    issues = len(overdue) + len(comm_gaps) + len(missing_fees)
    score = max(0, 100 - (issues * 10))

    return {
        "overdue_deadlines": overdue,
        "upcoming_deadlines": upcoming,
        "communication_gaps": comm_gaps,
        "missing_fee_agreements": missing_fees,
        "prospective_count": len(prospective),
        "score": score,
        "total_issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════
#  5.  TRUST ACCOUNT LEDGER  (RPC 1.15)
# ═══════════════════════════════════════════════════════════════════════

def _trust_ledger_path(case_id: str) -> str:
    return os.path.join(_DATA_DIR, "cases", case_id, "trust_ledger.json")

def load_trust_ledger(case_id: str) -> List[Dict]:
    """Load trust account entries for a case (newest first)."""
    path = _trust_ledger_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
            return sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
    return []

def add_trust_entry(case_id: str, entry_type: str, amount: float,
                    description: str = "", date_str: str = "",
                    reference: str = "", client_notified: bool = False) -> str:
    """Add a trust account entry. entry_type: 'deposit' or 'disbursement'. Returns ID."""
    entries = load_trust_ledger(case_id)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "type": entry_type,  # deposit, disbursement
        "amount": abs(amount),
        "description": description,
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "reference": reference,
        "client_notified": client_notified,
        "created_at": datetime.now().isoformat(),
    }
    entries.append(entry)
    path = _trust_ledger_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    return entry["id"]

def delete_trust_entry(case_id: str, entry_id: str):
    """Remove a trust ledger entry."""
    entries = load_trust_ledger(case_id)
    entries = [e for e in entries if e.get("id") != entry_id]
    path = _trust_ledger_path(case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

def get_trust_balance(case_id: str) -> float:
    """Compute current trust balance for a case."""
    entries = load_trust_ledger(case_id)
    balance = 0.0
    for e in entries:
        amt = float(e.get("amount", 0))
        if e.get("type") == "deposit":
            balance += amt
        elif e.get("type") == "disbursement":
            balance -= amt
    return balance

def get_trust_summary(case_mgr) -> List[Dict]:
    """Firm-wide trust account summary across all cases."""
    cases = case_mgr.list_cases()
    summary = []
    for case in cases:
        cid = case["id"]
        balance = get_trust_balance(cid)
        entries = load_trust_ledger(cid)
        if entries or balance != 0:
            # Check for unnotified deposits
            unnotified = [e for e in entries if e.get("type") == "deposit"
                          and not e.get("client_notified")]
            summary.append({
                "case_id": cid,
                "case_name": case.get("name", cid),
                "balance": balance,
                "entries": len(entries),
                "unnotified_deposits": len(unnotified),
            })
    return summary


# ── IOLTA Reconciliation Enhancement (RPC 1.15) ──────────────────────

def _reconciliation_path(case_id: str = "") -> str:
    """Path for reconciliation records (per-case or firm-wide)."""
    if case_id:
        return os.path.join(_DATA_DIR, "cases", case_id, "trust_reconciliation.json")
    return os.path.join(_DATA_DIR, "trust_reconciliation_firm.json")


def load_reconciliations(case_id: str = "") -> List[Dict]:
    """Load reconciliation records."""
    path = _reconciliation_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_reconciliation(case_id: str = "", bank_balance: float = 0.0,
                        book_balance: float = 0.0, client_total: float = 0.0,
                        reconciled_by: str = "", notes: str = "",
                        month: str = "") -> str:
    """Record a monthly reconciliation. Returns record ID."""
    records = load_reconciliations(case_id)
    _diff = round(bank_balance - book_balance, 2)
    _client_diff = round(book_balance - client_total, 2)
    _status = "balanced" if _diff == 0 and _client_diff == 0 else "discrepancy"
    rec = {
        "id": uuid.uuid4().hex[:8],
        "month": month or datetime.now().strftime("%Y-%m"),
        "bank_balance": bank_balance,
        "book_balance": book_balance,
        "client_total": client_total,
        "bank_book_diff": _diff,
        "book_client_diff": _client_diff,
        "status": _status,
        "reconciled_by": reconciled_by,
        "notes": notes,
        "reconciled_at": datetime.now().isoformat(),
    }
    records.append(rec)
    path = _reconciliation_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return rec["id"]


def get_trust_compliance_audit(case_mgr) -> Dict:
    """
    RPC 1.15 Compliance Audit — checks for:
    - Negative balances (commingling/overdraft)
    - Unnotified deposits
    - Missing monthly reconciliations
    - Disbursements exceeding deposits
    Returns a dict with violations, warnings, and score (0-100).
    """
    violations = []
    warnings = []
    cases = case_mgr.list_cases(include_archived=False)
    total_checks = 0
    passed_checks = 0

    for case in cases:
        cid = case["id"]
        cname = case.get("name", cid)
        entries = load_trust_ledger(cid)
        if not entries:
            continue

        balance = get_trust_balance(cid)

        # Check 1: Negative balance
        total_checks += 1
        if balance < 0:
            violations.append({
                "type": "negative_balance",
                "severity": "CRITICAL",
                "case": cname,
                "case_id": cid,
                "detail": f"Negative trust balance: ${balance:,.2f}",
                "rule": "RPC 1.15(a) — Cannot disburse more than held in trust",
            })
        else:
            passed_checks += 1

        # Check 2: Unnotified deposits
        total_checks += 1
        unnotified = [e for e in entries if e.get("type") == "deposit" and not e.get("client_notified")]
        if unnotified:
            _total_unnotif = sum(float(e.get("amount", 0)) for e in unnotified)
            violations.append({
                "type": "unnotified_deposit",
                "severity": "WARNING",
                "case": cname,
                "case_id": cid,
                "detail": f"{len(unnotified)} deposit(s) totaling ${_total_unnotif:,.2f} without client notification",
                "rule": "RPC 1.15(d) — Must promptly notify client of receipt of funds",
            })
        else:
            passed_checks += 1

        # Check 3: Running balance went negative at any point
        total_checks += 1
        _running = 0.0
        _went_negative = False
        for e in sorted(entries, key=lambda x: x.get("date", "")):
            amt = float(e.get("amount", 0))
            if e.get("type") == "deposit":
                _running += amt
            else:
                _running -= amt
            if _running < -0.005:
                _went_negative = True
                break
        if _went_negative:
            warnings.append({
                "type": "historical_overdraft",
                "severity": "WARNING",
                "case": cname,
                "case_id": cid,
                "detail": "Trust balance went negative at some point in the ledger history",
                "rule": "RPC 1.15 — Disbursement before sufficient funds is a violation",
            })
        else:
            passed_checks += 1

        # Check 4: Reconciliation currency
        total_checks += 1
        recs = load_reconciliations(cid)
        current_month = datetime.now().strftime("%Y-%m")
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        has_recent = any(r.get("month") in (current_month, last_month) for r in recs)
        if not has_recent and len(entries) > 0:
            warnings.append({
                "type": "stale_reconciliation",
                "severity": "INFO",
                "case": cname,
                "case_id": cid,
                "detail": f"No reconciliation recorded for {current_month} or {last_month}",
                "rule": "RPC 1.15(a) — Monthly reconciliation required",
            })
        else:
            passed_checks += 1

    score = round((passed_checks / total_checks * 100)) if total_checks > 0 else 100
    return {
        "score": score,
        "total_checks": total_checks,
        "passed": passed_checks,
        "violations": violations,
        "warnings": warnings,
    }


def get_client_sub_ledger(case_id: str) -> Dict:
    """
    Break down trust ledger by client matter description.
    Returns summary grouped by description prefix.
    """
    entries = load_trust_ledger(case_id)
    sub_ledger: Dict[str, float] = {}
    for e in entries:
        desc = e.get("description", "General").strip() or "General"
        amt = float(e.get("amount", 0))
        if e.get("type") == "deposit":
            sub_ledger[desc] = sub_ledger.get(desc, 0.0) + amt
        else:
            sub_ledger[desc] = sub_ledger.get(desc, 0.0) - amt
    return sub_ledger



# ═══════════════════════════════════════════════════════════════════════
#  6.  FEE AGREEMENT TRACKER  (RPC 1.5)
# ═══════════════════════════════════════════════════════════════════════

FEE_TYPES = ["Hourly", "Flat Fee", "Contingent", "Hybrid", "Pro Bono", "Court Appointed"]

def _fee_agreement_path(case_id: str) -> str:
    return os.path.join(_DATA_DIR, "cases", case_id, "fee_agreement.json")

def load_fee_agreement(case_id: str) -> Optional[Dict]:
    """Load fee agreement for a case."""
    path = _fee_agreement_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_fee_agreement(case_id: str, fee_type: str, rate: str = "",
                       retainer: str = "", signed: bool = False,
                       signed_date: str = "", notes: str = "",
                       contingent_pct: str = "", closing_statement: bool = False) -> Dict:
    """Save or update fee agreement for a case."""
    agreement = {
        "fee_type": fee_type,
        "rate": rate,
        "retainer": retainer,
        "signed": signed,
        "signed_date": signed_date,
        "notes": notes,
        "contingent_pct": contingent_pct,
        "closing_statement_sent": closing_statement,
        "updated_at": datetime.now().isoformat(),
    }
    path = _fee_agreement_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(agreement, f, indent=2)
    return agreement

def get_fee_agreement_status(case_id: str) -> str:
    """Returns 'none', 'draft', or 'signed'."""
    fa = load_fee_agreement(case_id)
    if not fa:
        return "none"
    return "signed" if fa.get("signed") else "draft"

def get_cases_missing_fee_agreement(case_mgr) -> List[Dict]:
    """Returns active cases without a signed fee agreement."""
    cases = case_mgr.list_cases()
    missing = []
    for case in cases:
        cid = case["id"]
        status = case_mgr.get_status(cid)
        if status in ("archived", "closed_resolved", "closed_dismissed",
                       "closed_convicted", "closed_acquitted", "closed_settled"):
            continue
        fa_status = get_fee_agreement_status(cid)
        if fa_status != "signed":
            missing.append({
                "case_id": cid,
                "case_name": case.get("name", cid),
                "fee_status": fa_status,
                "status": status or "active",
            })
    return missing


# ═══════════════════════════════════════════════════════════════════════
#  7.  EVIDENCE PRESERVATION / LITIGATION HOLD  (RPC 3.4)
# ═══════════════════════════════════════════════════════════════════════

LIT_HOLD_CHECKLIST_TEMPLATE = [
    {"label": "Litigation hold notice sent to client", "category": "Notice"},
    {"label": "Litigation hold notice sent to opposing party (if required)", "category": "Notice"},
    {"label": "Client instructed to preserve all relevant documents", "category": "Notice"},
    {"label": "Electronic data sources identified", "category": "Identification"},
    {"label": "Custodians of relevant data identified", "category": "Identification"},
    {"label": "Physical document locations inventoried", "category": "Identification"},
    {"label": "Auto-delete / retention policies suspended", "category": "Preservation"},
    {"label": "Backup of electronic data created", "category": "Preservation"},
    {"label": "Social media accounts preserved (screenshots)", "category": "Preservation"},
    {"label": "Chain of custody log initiated", "category": "Documentation"},
    {"label": "Preservation certification prepared", "category": "Documentation"},
]

def _lit_hold_path(case_id: str) -> str:
    return os.path.join(_DATA_DIR, "cases", case_id, "lit_hold.json")

def load_lit_hold(case_id: str) -> Dict:
    """Load litigation hold data for a case."""
    path = _lit_hold_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"active": False, "checklist": [], "custodians": [], "notes": ""}

def save_lit_hold(case_id: str, hold_data: Dict):
    """Save litigation hold data."""
    hold_data["updated_at"] = datetime.now().isoformat()
    path = _lit_hold_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hold_data, f, indent=2)

def init_lit_hold(case_id: str) -> Dict:
    """Initialize a new litigation hold with the template checklist."""
    checklist = []
    for item in LIT_HOLD_CHECKLIST_TEMPLATE:
        checklist.append({
            "id": uuid.uuid4().hex[:8],
            "label": item["label"],
            "category": item["category"],
            "checked": False,
            "date_completed": "",
            "notes": "",
        })
    hold_data = {
        "active": True,
        "initiated_date": datetime.now().strftime("%Y-%m-%d"),
        "checklist": checklist,
        "custodians": [],
        "notes": "",
    }
    save_lit_hold(case_id, hold_data)
    return hold_data


# ═══════════════════════════════════════════════════════════════════════
#  8.  WITHDRAWAL CHECKLIST  (RPC 1.16)
# ═══════════════════════════════════════════════════════════════════════

WITHDRAWAL_CHECKLIST = {
    "mandatory": {
        "title": "Mandatory Withdrawal (RPC 1.16(a))",
        "description": "A lawyer SHALL withdraw if:",
        "triggers": [
            "Representation will result in violation of the Rules of Professional Conduct or other law",
            "The lawyer's physical or mental condition materially impairs the lawyer's ability to represent the client",
            "The lawyer is discharged by the client",
        ],
        "steps": [
            {"label": "Determine if withdrawal is mandatory under RPC 1.16(a)", "required": True},
            {"label": "Give reasonable notice to the client", "required": True},
            {"label": "Allow time for employment of other counsel", "required": True},
            {"label": "Surrender papers and property belonging to client", "required": True},
            {"label": "Refund any unearned fees or unused retainer", "required": True},
            {"label": "If court-appointed, seek permission of the tribunal to withdraw", "required": True},
            {"label": "File motion to withdraw (if litigation pending)", "required": True},
            {"label": "Protect client's interests upon withdrawal", "required": True},
        ],
    },
    "permissive": {
        "title": "Permissive Withdrawal (RPC 1.16(b))",
        "description": "A lawyer MAY withdraw if:",
        "triggers": [
            "Withdrawal can be accomplished without material adverse effect on client interests",
            "Client persists in action the lawyer considers repugnant or with which the lawyer has fundamental disagreement",
            "Client fails substantially to fulfill an obligation to the lawyer (including fee payment)",
            "Representation will result in unreasonable financial burden on the lawyer",
            "Client has used the lawyer's services to perpetrate a crime or fraud",
            "Other good cause for withdrawal exists",
        ],
        "steps": [
            {"label": "Confirm withdrawal won't materially harm client interests", "required": True},
            {"label": "Document the reason for withdrawal", "required": True},
            {"label": "Give reasonable notice to the client", "required": True},
            {"label": "Allow time for employment of other counsel", "required": True},
            {"label": "Surrender papers and property belonging to client", "required": True},
            {"label": "Refund any unearned fees or unused retainer", "required": True},
            {"label": "File motion to withdraw (if litigation pending)", "required": False},
            {"label": "Provide status summary of all pending matters", "required": True},
            {"label": "Notify all relevant parties of withdrawal", "required": True},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  9.  SUPERVISION TRACKER  (RPC 5.1 / 5.3)
# ═══════════════════════════════════════════════════════════════════════

def _supervision_log_path(case_id: str) -> str:
    return os.path.join(_DATA_DIR, "cases", case_id, "supervision_log.json")

def load_supervision_log(case_id: str) -> List[Dict]:
    """Load supervision/delegation entries for a case."""
    path = _supervision_log_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return sorted(json.load(f), key=lambda e: e.get("date", ""), reverse=True)
    return []

def add_supervision_entry(case_id: str, task: str, assignee: str,
                          supervisor: str, assignee_type: str = "Attorney",
                          due_date: str = "", notes: str = "") -> str:
    """Log a delegated task. assignee_type: 'Attorney', 'Paralegal', 'Clerk', 'Extern'. Returns ID."""
    entries = load_supervision_log(case_id)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "task": task,
        "assignee": assignee,
        "assignee_type": assignee_type,
        "supervisor": supervisor,
        "due_date": due_date,
        "status": "assigned",
        "notes": notes,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(),
    }
    entries.append(entry)
    path = _supervision_log_path(case_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    return entry["id"]

def update_supervision_entry(case_id: str, entry_id: str, updates: Dict):
    """Update a supervision entry (e.g., mark as reviewed, complete)."""
    entries = load_supervision_log(case_id)
    for e in entries:
        if e.get("id") == entry_id:
            e.update(updates)
            e["updated_at"] = datetime.now().isoformat()
            break
    path = _supervision_log_path(case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

def delete_supervision_entry(case_id: str, entry_id: str):
    """Remove a supervision log entry."""
    entries = load_supervision_log(case_id)
    entries = [e for e in entries if e.get("id") != entry_id]
    path = _supervision_log_path(case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════
TN_RPC_CATEGORIES = {
    "Client-Lawyer Relationship": "Rules 1.0–1.18 — Core duties to clients",
    "Counselor": "Rules 2.1–2.4 — Scope of counseling duties",
    "Advocate": "Rules 3.1–3.9 — Duties as advocate before tribunals",
    "Transactions with Non-Clients": "Rules 4.1–4.4 — Duties to non-clients",
    "Law Firms & Associations": "Rules 5.1–5.7 — Firm organization & responsibility",
    "Public Service": "Rules 6.1–6.5 — Pro bono & public service duties",
    "Information About Legal Services": "Rules 7.1–7.6 — Advertising & solicitation",
    "Maintaining Integrity": "Rules 8.1–8.5 — Bar admission & discipline",
}

TN_RULES_REFERENCE = [
    # ── Series 1: Client-Lawyer Relationship ──────────────────────────
    {
        "rule": "RPC 1.0", "title": "Terminology",
        "category": "Client-Lawyer Relationship",
        "summary": "Definitions of key terms used throughout the Rules: 'confirmed in writing', 'firm', 'fraud', 'informed consent', 'knowingly', 'partner', 'reasonable', 'screened', 'substantial', 'tribunal', and 'writing'.",
        "key_points": ["Defines 'informed consent' — agreement after adequate information about risks and alternatives", "Defines 'confirmed in writing' — can be email", "Defines 'tribunal' — includes arbitrators and legislative bodies"],
        "risk": "Misunderstanding defined terms can lead to non-compliance",
    },
    {
        "rule": "RPC 1.1", "title": "Competence",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall provide competent representation, including the legal knowledge, skill, thoroughness, and preparation reasonably necessary. This includes staying current with technology relevant to the practice.",
        "key_points": ["Must have requisite knowledge and skill", "Can associate with established competent lawyer", "Must keep abreast of technology changes"],
        "risk": "Malpractice claims from inadequate preparation",
    },
    {
        "rule": "RPC 1.2", "title": "Scope of Representation & Authority",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall abide by a client's decisions concerning the objectives of representation and shall consult with the client about the means. In criminal cases, the client decides on plea, jury trial, and whether to testify.",
        "key_points": ["Client decides objectives", "Lawyer handles means/methods", "Must consult on important decisions"],
        "risk": "Acting beyond authority or failing to consult",
    },
    {
        "rule": "RPC 1.3", "title": "Diligence",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall act with reasonable diligence and promptness. Procrastination is explicitly identified as a disciplinary issue.",
        "key_points": ["No unreasonable delays", "Must carry through to completion", "Workload must allow adequate attention"],
        "risk": "Missed deadlines, statute of limitations — #2 malpractice risk",
    },
    {
        "rule": "RPC 1.4", "title": "Communication",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall keep the client reasonably informed and promptly comply with reasonable requests for information. Must explain matters to the extent necessary for informed decisions.",
        "key_points": ["Prompt response to inquiries", "Status updates without being asked", "Explain to permit informed decisions"],
        "risk": "Most common bar complaint — failure to communicate",
    },
    {
        "rule": "RPC 1.5", "title": "Fees",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall not make an agreement for, charge, or collect an unreasonable fee. Fee basis must be communicated, preferably in writing. Contingent fees require signed written agreement and closing statement.",
        "key_points": ["Fee must be reasonable", "Communicate basis/rate in writing", "Contingent fees: signed agreement + closing statement"],
        "risk": "Fee disputes, refund claims, disciplinary action",
    },
    {
        "rule": "RPC 1.6", "title": "Confidentiality of Information",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall not reveal information relating to the representation unless the client gives informed consent. Limited exceptions for preventing death/substantial bodily harm, or preventing client crime/fraud.",
        "key_points": ["Near-absolute duty of confidentiality", "Includes all information related to representation", "Very narrow exceptions"],
        "risk": "Disciplinary action, malpractice, loss of client trust",
    },
    {
        "rule": "RPC 1.7", "title": "Conflict of Interest — Current Clients",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall not represent a client if there is a concurrent conflict unless: (1) the lawyer reasonably believes competent representation is possible, (2) the representation is not prohibited by law, (3) the clients are not directly adverse in the same proceeding, and (4) each client gives informed consent, confirmed in writing.",
        "key_points": ["Direct adversity between current clients is prohibited", "Must get informed consent confirmed in writing", "Some conflicts are non-waivable"],
        "risk": "Disqualification, malpractice, disciplinary action — #1 risk",
    },
    {
        "rule": "RPC 1.8", "title": "Conflict of Interest — Specific Rules",
        "category": "Client-Lawyer Relationship",
        "summary": "Specific prohibited transactions: business with clients, using client info, gifts, media rights, financial assistance, aggregate settlements, proprietary interest in cause of action, sexual relations with clients.",
        "key_points": ["No business transactions without informed consent + independent counsel", "No using client information to client's disadvantage", "No sexual relations with clients"],
        "risk": "Disciplinary action for specific prohibited conduct",
    },
    {
        "rule": "RPC 1.9", "title": "Duties to Former Clients",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer who has formerly represented a client shall not represent another person in the same or substantially related matter adverse to the former client, unless the former client gives informed consent.",
        "key_points": ["Cannot be adverse to former client in related matter", "Confidential info from former representation is protected", "Must get informed consent for waiver"],
        "risk": "Disqualification, malpractice",
    },
    {
        "rule": "RPC 1.10", "title": "Imputation of Conflicts",
        "category": "Client-Lawyer Relationship",
        "summary": "While lawyers are associated in a firm, none shall knowingly represent a client when any one of them would be prohibited from doing so. Conflicts impute across the entire firm.",
        "key_points": ["Firm-wide imputation of conflicts", "Screening may be available for lateral hires", "Departed lawyer's conflicts may continue"],
        "risk": "Entire firm disqualified from representation",
    },
    {
        "rule": "RPC 1.11", "title": "Special Conflicts — Government Officers & Employees",
        "category": "Client-Lawyer Relationship",
        "summary": "A former government lawyer shall not represent a client in a matter in which the lawyer participated personally and substantially while in government. Firm may still represent if the lawyer is timely screened.",
        "key_points": ["Personal & substantial participation triggers conflict", "Screening of former government lawyer may cure", "Must give written notice to government agency"],
        "risk": "Disqualification of former government lawyers and their firms",
    },
    {
        "rule": "RPC 1.12", "title": "Former Judge, Arbitrator, Mediator, or Other Third-Party Neutral",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer shall not represent anyone in a matter the lawyer participated in personally and substantially as a judge, arbitrator, mediator, or law clerk. Screening with notice may cure for firm.",
        "key_points": ["Cannot represent parties from prior adjudication", "Firm may represent with screening", "Law clerks included"],
        "risk": "Disqualification, appearance of impropriety",
    },
    {
        "rule": "RPC 1.13", "title": "Organization as Client",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer employed or retained by an organization represents the organization, not its constituents. If a constituent's action threatens substantial harm, must refer the matter up the organizational hierarchy.",
        "key_points": ["Organization is the client, not its people", "Reporting up duty when substantial harm threatened", "Must clarify role to organizational constituents"],
        "risk": "Confusion about who the client is — entity vs. individuals",
    },
    {
        "rule": "RPC 1.14", "title": "Client with Diminished Capacity",
        "category": "Client-Lawyer Relationship",
        "summary": "When a client's capacity to make adequately considered decisions is diminished, the lawyer shall maintain a normal client-lawyer relationship as far as reasonably possible. Lawyer may take protective action if at risk of substantial harm.",
        "key_points": ["Maintain normal relationship as far as possible", "May seek appointment of guardian", "Client age alone does not determine capacity"],
        "risk": "Overriding client autonomy or failing to protect vulnerable client",
    },
    {
        "rule": "RPC 1.15", "title": "Safekeeping Property (Trust Accounts)",
        "category": "Client-Lawyer Relationship",
        "summary": "Client funds must be kept in a separate trust account, with complete records maintained for 5 years. Monthly reconciliation required. Client must be promptly notified when funds are received.",
        "key_points": ["Separate trust account required (IOLTA)", "Complete records for 5 years", "Monthly reconciliation", "Prompt notification on receipt"],
        "risk": "#1 cause of disbarment — trust account violations",
    },
    {
        "rule": "RPC 1.16", "title": "Declining or Terminating Representation",
        "category": "Client-Lawyer Relationship",
        "summary": "Mandatory withdrawal: if representation violates rules, lawyer is impaired, or lawyer is discharged. Permissive withdrawal: no material adverse effect, client misconduct, unreasonable financial burden.",
        "key_points": ["Must withdraw if rules would be violated", "Must return unearned fees", "Must surrender client papers", "Must give reasonable notice"],
        "risk": "Improper withdrawal harms client and risks disciplinary action",
    },
    {
        "rule": "RPC 1.17", "title": "Sale of Law Practice",
        "category": "Client-Lawyer Relationship",
        "summary": "A lawyer or law firm may sell or purchase a law practice if the seller ceases to engage in private practice, written notice is given to all clients, and fees are not increased by reason of the sale.",
        "key_points": ["Seller must cease practice in the jurisdiction", "All clients must be notified", "Client may object and retain new counsel"],
        "risk": "Client abandonment if not handled properly",
    },
    {
        "rule": "RPC 1.18", "title": "Duties to Prospective Clients",
        "category": "Client-Lawyer Relationship",
        "summary": "Even if no client-lawyer relationship ensues, a lawyer who has consulted with a prospective client shall not use or reveal information learned in the consultation. If significantly harmful information was received, the lawyer may be disqualified.",
        "key_points": ["Confidentiality owed to prospective clients", "Information learned in consultation is protected", "May create disqualifying conflict"],
        "risk": "Hidden disqualification trap from intake consultations",
    },
    # ── Series 2: Counselor ───────────────────────────────────────────
    {
        "rule": "RPC 2.1", "title": "Advisor",
        "category": "Counselor",
        "summary": "A lawyer shall exercise independent professional judgment and render candid advice. May refer to moral, economic, social, and political factors when relevant.",
        "key_points": ["Must give honest assessment even if unfavorable", "Not limited to purely legal considerations", "May initiate advice when client's course is unwise"],
        "risk": "Failing to give candid advice to please client",
    },
    {
        "rule": "RPC 2.2", "title": "Intermediary (Reserved)",
        "category": "Counselor",
        "summary": "This rule has been reserved in the Tennessee Rules of Professional Conduct. The intermediary function is generally addressed under RPC 1.7 (conflict of interest).",
        "key_points": ["Rule reserved / not active in Tennessee", "Mediation issues addressed under RPC 1.7 and 2.4"],
        "risk": "N/A — reserved",
    },
    {
        "rule": "RPC 2.3", "title": "Evaluation for Use by Third Persons",
        "category": "Counselor",
        "summary": "A lawyer may provide an evaluation of a matter affecting a client for the use of someone other than the client if the lawyer reasonably believes it is compatible with other aspects of the lawyer's relationship with the client.",
        "key_points": ["Client must consent to third-party evaluation", "Must be compatible with client relationship", "May create duty to non-client who relies on evaluation"],
        "risk": "Inadvertent waiver of privilege or duty to third party",
    },
    {
        "rule": "RPC 2.4", "title": "Lawyer Serving as Third-Party Neutral",
        "category": "Counselor",
        "summary": "A lawyer serving as a third-party neutral (mediator, arbitrator) shall inform unrepresented parties that the lawyer is not representing them. Must explain the difference if confusion exists.",
        "key_points": ["Must clarify role as neutral, not advocate", "No client-lawyer relationship with parties", "Must explain distinction if party is confused"],
        "risk": "Inadvertent creation of attorney-client relationship",
    },
    # ── Series 3: Advocate ────────────────────────────────────────────
    {
        "rule": "RPC 3.1", "title": "Meritorious Claims and Contentions",
        "category": "Advocate",
        "summary": "A lawyer shall not bring or defend a proceeding, or assert or controvert an issue, unless there is a basis in law and fact that is not frivolous. A good faith argument for modification of existing law is permissible.",
        "key_points": ["No frivolous claims or defenses", "Good faith arguments to change law are OK", "Criminal defender may require prosecution to prove every element"],
        "risk": "Rule 11 sanctions, disciplinary action for frivolous litigation",
    },
    {
        "rule": "RPC 3.2", "title": "Expediting Litigation",
        "category": "Advocate",
        "summary": "A lawyer shall make reasonable efforts to expedite litigation consistent with the interests of the client. Delay tactics for their own sake are prohibited.",
        "key_points": ["No dilatory tactics", "Delay only if justified by client interest", "Realizing delays are costly"],
        "risk": "Court sanctions for delay tactics",
    },
    {
        "rule": "RPC 3.3", "title": "Candor Toward the Tribunal",
        "category": "Advocate",
        "summary": "A lawyer shall not knowingly make false statements to a tribunal, fail to disclose adverse authority, or offer false evidence. If client commits fraud on tribunal, lawyer must take remedial steps.",
        "key_points": ["No false statements to court", "Must disclose adverse controlling authority", "Must address client fraud on tribunal"],
        "risk": "Sanctions, contempt, disciplinary action",
    },
    {
        "rule": "RPC 3.4", "title": "Fairness to Opposing Party and Counsel",
        "category": "Advocate",
        "summary": "A lawyer shall not destroy or conceal evidence, falsify evidence, or obstruct access to evidence. Litigation hold obligations apply.",
        "key_points": ["No destruction of potential evidence", "No obstructing discovery", "Litigation hold obligations"],
        "risk": "Sanctions, adverse inference, criminal charges for spoliation",
    },
    {
        "rule": "RPC 3.5", "title": "Impartiality and Decorum of the Tribunal",
        "category": "Advocate",
        "summary": "A lawyer shall not seek to influence a judge, juror, or prospective juror by improper means, or communicate ex parte with them unless authorized. Must maintain courtroom decorum.",
        "key_points": ["No ex parte contact with judge (except as authorized)", "No improper contact with jurors", "Must maintain decorum in proceedings"],
        "risk": "Mistrial, contempt, disqualification",
    },
    {
        "rule": "RPC 3.6", "title": "Trial Publicity",
        "category": "Advocate",
        "summary": "A lawyer participating in litigation shall not make extrajudicial statements that the lawyer knows or reasonably should know will be disseminated by public media and have a substantial likelihood of materially prejudicing the proceeding.",
        "key_points": ["No prejudicial public statements about pending case", "May state the claim/defense and public record info", "Right of reply if opposing side made public statement"],
        "risk": "Gag orders, contempt, mistrial",
    },
    {
        "rule": "RPC 3.7", "title": "Lawyer as Witness",
        "category": "Advocate",
        "summary": "A lawyer shall not act as advocate at a trial in which the lawyer is likely to be a necessary witness, with limited exceptions (value of services, uncontested matter, or substantial hardship).",
        "key_points": ["Cannot be both advocate and witness at trial", "Exceptions for fee testimony and uncontested matters", "Conflict may impute to firm members"],
        "risk": "Disqualification from trial if lawyer must testify",
    },
    {
        "rule": "RPC 3.8", "title": "Special Responsibilities of a Prosecutor",
        "category": "Advocate",
        "summary": "A prosecutor shall not prosecute a charge not supported by probable cause. Must disclose evidence negating guilt. Must make reasonable efforts to assure that accused has been advised of right to counsel.",
        "key_points": ["Must have probable cause", "Brady obligation — disclose exculpatory evidence", "Must ensure right to counsel is advised"],
        "risk": "Constitutional violations, reversal of convictions, Brady violations",
    },
    {
        "rule": "RPC 3.9", "title": "Advocate in Non-Adjudicative Proceedings",
        "category": "Advocate",
        "summary": "A lawyer representing a client before a legislative body or administrative agency in a non-adjudicative proceeding shall disclose that the appearance is in a representative capacity and shall conform to RPC 3.3(a)-(c) and 3.4(a)-(c).",
        "key_points": ["Must disclose representative capacity", "Candor rules apply in legislative settings", "No false statements to government bodies"],
        "risk": "Misleading government agencies about representation",
    },
    # ── Series 4: Transactions with Non-Clients ──────────────────────
    {
        "rule": "RPC 4.1", "title": "Truthfulness in Statements to Others",
        "category": "Transactions with Non-Clients",
        "summary": "In the course of representing a client, a lawyer shall not knowingly make a false statement of material fact or law to a third person, or fail to disclose a material fact to avoid assisting a client crime or fraud.",
        "key_points": ["No false statements of fact or law", "Must disclose to prevent client crime/fraud", "Applies in negotiations and all dealings"],
        "risk": "Sanctions, malpractice, disciplinary action for misrepresentation",
    },
    {
        "rule": "RPC 4.2", "title": "Communication with Represented Person",
        "category": "Transactions with Non-Clients",
        "summary": "A lawyer shall not communicate about the subject of the representation with a person the lawyer knows to be represented by another lawyer, unless the lawyer has the consent of the other lawyer or is authorized by law.",
        "key_points": ["No direct contact with represented opposing party", "Must go through opposing counsel", "Authorized law (e.g., criminal investigation) is an exception"],
        "risk": "Evidence suppression, disqualification, disciplinary action",
    },
    {
        "rule": "RPC 4.3", "title": "Dealing with Unrepresented Person",
        "category": "Transactions with Non-Clients",
        "summary": "A lawyer shall not state or imply disinterest when dealing with an unrepresented person. Must clarify role and not give legal advice to unrepresented persons whose interests may conflict with the client's.",
        "key_points": ["Must clarify you are not their lawyer", "Cannot take advantage of unrepresented persons", "No advice if interests conflict with your client"],
        "risk": "Inadvertent attorney-client relationship, overreaching",
    },
    {
        "rule": "RPC 4.4", "title": "Respect for Rights of Third Persons",
        "category": "Transactions with Non-Clients",
        "summary": "A lawyer shall not use means that have no substantial purpose other than to embarrass, delay, or burden a third person. If inadvertently receiving privileged documents, must promptly notify the sender.",
        "key_points": ["No harassing third persons", "Promptly notify sender of inadvertently sent privileged docs", "Cannot review privileged documents once noticed"],
        "risk": "Sanctions, disqualification from using improperly obtained evidence",
    },
    # ── Series 5: Law Firms & Associations ────────────────────────────
    {
        "rule": "RPC 5.1", "title": "Supervisory Responsibilities",
        "category": "Law Firms & Associations",
        "summary": "Partners and supervising lawyers must make reasonable efforts to ensure other lawyers and staff comply with the Rules. Responsible for violations if they order, ratify, or fail to take remedial action with knowledge.",
        "key_points": ["Must have compliance systems in place", "Supervisors responsible for subordinate violations", "Must take remedial action when misconduct is known"],
        "risk": "Vicarious disciplinary liability for firm's violations",
    },
    {
        "rule": "RPC 5.2", "title": "Responsibilities of a Subordinate Lawyer",
        "category": "Law Firms & Associations",
        "summary": "A subordinate lawyer is bound by the Rules even when acting at the direction of a supervisor. However, a subordinate does not violate the Rules if acting in accordance with a supervisor's reasonable resolution of an arguable question of professional duty.",
        "key_points": ["Subordinate is still personally responsible", "'Just following orders' is not a defense for clear violations", "Arguable questions resolved by supervisor provide safe harbor"],
        "risk": "Personal disciplinary liability despite supervisor direction",
    },
    {
        "rule": "RPC 5.3", "title": "Nonlawyer Assistants",
        "category": "Law Firms & Associations",
        "summary": "Same supervisory duties apply to nonlawyer staff (paralegals, investigators, etc.). Must ensure their conduct is compatible with the lawyer's professional obligations.",
        "key_points": ["Must instruct on ethical obligations", "Must supervise delegated work", "Responsible for nonlawyer violations"],
        "risk": "Liability for paralegal/staff ethical violations",
    },
    {
        "rule": "RPC 5.4", "title": "Professional Independence of a Lawyer",
        "category": "Law Firms & Associations",
        "summary": "A lawyer shall not share legal fees with a non-lawyer (with limited exceptions). A non-lawyer shall not direct or regulate the professional judgment of a lawyer. No partnerships with non-lawyers to practice law.",
        "key_points": ["No fee-sharing with non-lawyers (limited exceptions)", "Non-lawyers cannot control legal judgment", "No multi-disciplinary practice partnerships"],
        "risk": "Unauthorized practice issues, loss of professional independence",
    },
    {
        "rule": "RPC 5.5", "title": "Unauthorized Practice; Multijurisdictional Practice",
        "category": "Law Firms & Associations",
        "summary": "A lawyer shall not practice law in a jurisdiction in violation of that jurisdiction's regulation. Limited exceptions for temporary practice (related to home jurisdiction matter, arbitration, or association with local counsel).",
        "key_points": ["Must be admitted to practice in the jurisdiction", "Temporary practice exceptions exist", "Cannot assist non-lawyers in unauthorized practice"],
        "risk": "Unauthorized practice charges, void representation",
    },
    {
        "rule": "RPC 5.6", "title": "Restrictions on Right to Practice",
        "category": "Law Firms & Associations",
        "summary": "A lawyer shall not participate in an agreement that restricts the right of a lawyer to practice after termination of a relationship, except as part of retirement benefits. Settlement agreements cannot restrict a lawyer's right to practice.",
        "key_points": ["Non-compete agreements for lawyers are generally prohibited", "Retirement benefit restriction is an exception", "Cannot restrict practice as condition of settlement"],
        "risk": "Unenforceable non-compete, restricting client choice",
    },
    {
        "rule": "RPC 5.7", "title": "Responsibilities Regarding Law-Related Services",
        "category": "Law Firms & Associations",
        "summary": "A lawyer who provides law-related services (title insurance, financial planning, etc.) is subject to the Rules with respect to those services unless clearly separated from legal practice and the client understands the protections do not apply.",
        "key_points": ["Law-related services may trigger RPC obligations", "Must clarify if RPC protections don't apply", "Includes title insurance, financial planning, lobbying"],
        "risk": "Inadvertent creation of attorney-client protections in non-legal services",
    },
    # ── Series 6: Public Service ──────────────────────────────────────
    {
        "rule": "RPC 6.1", "title": "Voluntary Pro Bono Publico Service",
        "category": "Public Service",
        "summary": "Every lawyer has a professional responsibility to provide legal services to those unable to pay. A lawyer should aspire to render at least 50 hours of pro bono service per year.",
        "key_points": ["Aspirational goal of 50 hours per year", "Priority to persons of limited means", "Can include reduced-fee services and law reform activities"],
        "risk": "Aspirational — no disciplinary risk, but professional expectation",
    },
    {
        "rule": "RPC 6.2", "title": "Accepting Appointments",
        "category": "Public Service",
        "summary": "A lawyer shall not seek to avoid appointment by a tribunal except for good cause, such as: (a) representing the client likely to violate Rules, (b) unreasonable financial burden, or (c) the client or cause is so repugnant it would impair the lawyer-client relationship.",
        "key_points": ["Must accept court appointments unless good cause", "Financial burden is valid excuse", "Repugnancy to the lawyer is valid but narrow"],
        "risk": "Contempt for refusing court appointment without good cause",
    },
    {
        "rule": "RPC 6.3", "title": "Membership in Legal Services Organization",
        "category": "Public Service",
        "summary": "A lawyer may serve as a director, officer, or member of a legal services organization even if the organization serves persons with interests adverse to the lawyer's clients, provided the lawyer does not knowingly participate in decisions that would create a conflict.",
        "key_points": ["Service on legal aid boards is encouraged", "Must recuse from conflicting decisions", "Cannot use position to benefit own clients"],
        "risk": "Conflict between board service and client representation",
    },
    {
        "rule": "RPC 6.4", "title": "Law Reform Activities Affecting Client Interests",
        "category": "Public Service",
        "summary": "A lawyer may serve as a member, officer, or director of an organization involved in law reform even though it may affect the interests of the lawyer's clients. Must disclose client interest when the lawyer knows a client's interests could be materially benefited.",
        "key_points": ["May participate in law reform activities", "Must disclose when client could benefit", "Need not identify client if doing so would violate confidentiality"],
        "risk": "Undisclosed conflict between reform activity and client interest",
    },
    {
        "rule": "RPC 6.5", "title": "Nonprofit and Court-Annexed Limited Legal Services",
        "category": "Public Service",
        "summary": "A lawyer who provides short-term limited legal services under a nonprofit or court-annexed program is subject to reduced conflict-checking obligations, needing only to check for conflicts the lawyer knows of at the time.",
        "key_points": ["Reduced conflict-checking for brief pro bono services", "Only actual knowledge of conflicts triggers duty", "Imputation to firm does not apply in same limited way"],
        "risk": "Minimal — reduced obligations for brief court services",
    },
    # ── Series 7: Information About Legal Services ────────────────────
    {
        "rule": "RPC 7.1", "title": "Communications Concerning a Lawyer's Services",
        "category": "Information About Legal Services",
        "summary": "A lawyer shall not make a false or misleading communication about the lawyer or the lawyer's services. This includes material misrepresentation of fact or law, or omission of facts necessary to prevent a statement from being misleading.",
        "key_points": ["No false or misleading advertising", "Must be verifiable", "Includes all public communications about services"],
        "risk": "Disciplinary action for misleading advertising",
    },
    {
        "rule": "RPC 7.2", "title": "Advertising",
        "category": "Information About Legal Services",
        "summary": "A lawyer may advertise through written, recorded, or electronic communication. Must include the name and office address of at least one responsible lawyer. May pay reasonable costs of advertising.",
        "key_points": ["Advertising permitted with proper identification", "Must retain copies of ads for 2 years", "May pay for advertising costs but not for referrals"],
        "risk": "Failure to retain ad copies or proper identification",
    },
    {
        "rule": "RPC 7.3", "title": "Solicitation of Clients",
        "category": "Information About Legal Services",
        "summary": "A lawyer shall not by in-person, live telephone, or real-time electronic contact solicit professional employment when a significant motive is the lawyer's pecuniary gain, unless the person contacted is a lawyer, family member, close personal friend, or former client.",
        "key_points": ["No in-person solicitation for profit", "Written solicitation must be labeled 'ADVERTISEMENT'", "Exceptions for family, friends, former clients, other lawyers"],
        "risk": "Disciplinary action, especially for ambulance chasing",
    },
    {
        "rule": "RPC 7.4", "title": "Communication of Fields of Practice",
        "category": "Information About Legal Services",
        "summary": "A lawyer may communicate that the lawyer does or does not practice in particular areas of law. Must not claim specialization unless certified by an accredited certifying organization approved by the TN Supreme Court.",
        "key_points": ["Can state practice areas", "Cannot claim 'specialist' without certification", "Patent and admiralty designations permitted"],
        "risk": "Misleading the public about expertise level",
    },
    {
        "rule": "RPC 7.5", "title": "Firm Names and Letterheads",
        "category": "Information About Legal Services",
        "summary": "A firm name shall not be misleading. Lawyers may state or imply they practice in a partnership or organization only when that is the fact. Multi-jurisdictional firms must indicate jurisdictional limitations.",
        "key_points": ["Firm name must not be misleading", "Cannot imply partnership if none exists", "Must note jurisdictional limitations of practice"],
        "risk": "Misleading firm names creating false impressions",
    },
    {
        "rule": "RPC 7.6", "title": "Political Contributions to Obtain Engagements or Appointments",
        "category": "Information About Legal Services",
        "summary": "A lawyer shall not accept a government legal engagement or appointment by a judge if the lawyer or firm made or solicited political contributions for the purpose of obtaining the engagement or appointment.",
        "key_points": ["No pay-to-play in government legal work", "Contributions for purpose of obtaining engagements prohibited", "Applies to both direct and indirect contributions"],
        "risk": "Criminal charges, disciplinary action, loss of government contracts",
    },
    # ── Series 8: Maintaining Integrity of the Profession ─────────────
    {
        "rule": "RPC 8.1", "title": "Bar Admission and Disciplinary Matters",
        "category": "Maintaining Integrity",
        "summary": "A lawyer shall not knowingly make a false statement of material fact in connection with a bar application or disciplinary matter. Failure to respond to a lawful demand for information from a disciplinary authority is grounds for discipline.",
        "key_points": ["No false statements in bar applications", "Must respond to disciplinary inquiries", "Duty extends to bar admission of others"],
        "risk": "Denial of admission, suspension, disbarment",
    },
    {
        "rule": "RPC 8.2", "title": "Judicial and Legal Officials",
        "category": "Maintaining Integrity",
        "summary": "A lawyer shall not make a statement about the qualifications or integrity of a judge or other public legal officer that the lawyer knows to be false or with reckless disregard for its truth or falsity.",
        "key_points": ["Criticism of judges must be truthful", "Reckless disregard standard applies", "Applies to all judicial officers and legal officials"],
        "risk": "Disciplinary action for defaming judicial officers",
    },
    {
        "rule": "RPC 8.3", "title": "Reporting Professional Misconduct",
        "category": "Maintaining Integrity",
        "summary": "A lawyer who knows that another lawyer has committed a violation that raises a substantial question as to that lawyer's honesty, trustworthiness or fitness as a lawyer shall report to the Board of Professional Responsibility.",
        "key_points": ["Mandatory reporting of known serious violations", "Limited by RPC 1.6 confidentiality", "Applies to fellow lawyers and judges"],
        "risk": "Failure to report is itself a disciplinary violation",
    },
    {
        "rule": "RPC 8.4", "title": "Misconduct",
        "category": "Maintaining Integrity",
        "summary": "It is professional misconduct for a lawyer to: violate the Rules, commit a criminal act reflecting adversely on honesty/trustworthiness/fitness, engage in conduct involving dishonesty/fraud/deceit/misrepresentation, or engage in conduct prejudicial to the administration of justice.",
        "key_points": ["Catch-all misconduct rule", "Criminal conduct reflecting on fitness is grounds for discipline", "Dishonesty, fraud, deceit — even outside practice — is grounds"],
        "risk": "Catch-all for any conduct unbecoming a lawyer",
    },
    {
        "rule": "RPC 8.5", "title": "Disciplinary Authority; Choice of Law",
        "category": "Maintaining Integrity",
        "summary": "A lawyer admitted to practice in Tennessee is subject to Tennessee disciplinary authority regardless of where the conduct occurs. For matters before a tribunal, the rules of the jurisdiction where the tribunal sits apply.",
        "key_points": ["TN has authority over TN-admitted lawyers anywhere", "Tribunal jurisdiction rules apply for court matters", "Multi-jurisdiction practice may trigger multiple authorities"],
        "risk": "Subject to discipline in multiple jurisdictions",
    },
]


def search_rules(query: str) -> List[Dict]:
    """Search the TN Rules reference by keyword across all fields."""
    q = query.lower()
    results = []
    for rule in TN_RULES_REFERENCE:
        searchable = f"{rule['rule']} {rule['title']} {rule['summary']} {' '.join(rule.get('key_points', []))} {rule.get('category', '')}".lower()
        if q in searchable:
            results.append(rule)
    return results


def search_rules_by_category(category: str) -> List[Dict]:
    """Return all rules in a given category."""
    return [r for r in TN_RULES_REFERENCE if r.get("category", "").lower() == category.lower()]


def get_rule_summary(rule_number: str) -> Optional[Dict]:
    """Get a specific rule by number (e.g., '1.7' or 'RPC 1.7')."""
    target = rule_number.upper().replace("RPC ", "").strip()
    for rule in TN_RULES_REFERENCE:
        if target in rule["rule"]:
            return rule
    return None



# ═══════════════════════════════════════════════════════════════════════
#  11.  REPORTING OBLIGATIONS  (RPC 8.3)
# ═══════════════════════════════════════════════════════════════════════

REPORTING_CHECKLIST = {
    "when_to_report": [
        "Another lawyer has committed a violation raising a substantial question about their honesty, trustworthiness, or fitness",
        "A judge has committed a violation of the Code of Judicial Conduct raising a substantial question about their fitness for office",
    ],
    "exceptions": [
        "Information protected by RPC 1.6 (client confidentiality) — cannot report if learned through client representation",
        "Information learned while serving as a Rule 31 dispute resolution neutral",
        "Lawyers participating in approved lawyer assistance programs (RPC 8.3(d))",
    ],
    "how_to_report": [
        "File a complaint with the Tennessee Board of Professional Responsibility",
        "Include specific facts supporting the allegation",
        "Provide any non-privileged supporting documentation",
    ],
    "consequences_of_not_reporting": [
        "Failure to report is itself a violation of RPC 8.3",
        "May result in disciplinary action against the non-reporting lawyer",
    ],
}


# ═══════════════════════════════════════════════════════════════════════
#  12.  STATUTE OF LIMITATIONS TRACKER  (Malpractice Prevention)
# ═══════════════════════════════════════════════════════════════════════

TN_SOL_TABLE = [
    {"claim_type": "Personal Injury", "years": 1, "statute": "T.C.A. § 28-3-104(a)(1)", "discovery_rule": True, "notes": "1 year from date of injury; discovery rule may apply"},
    {"claim_type": "Medical Malpractice", "years": 1, "statute": "T.C.A. § 29-26-116", "discovery_rule": True, "notes": "1 year from discovery, max 3 years from act (statute of repose)"},
    {"claim_type": "Legal Malpractice", "years": 1, "statute": "T.C.A. § 28-3-104(a)(2)", "discovery_rule": True, "notes": "1 year from discovery of malpractice"},
    {"claim_type": "Wrongful Death", "years": 1, "statute": "T.C.A. § 28-3-104(a)(1)", "discovery_rule": False, "notes": "1 year from date of death"},
    {"claim_type": "Property Damage", "years": 3, "statute": "T.C.A. § 28-3-105", "discovery_rule": False, "notes": "3 years from date of damage"},
    {"claim_type": "Written Contract", "years": 6, "statute": "T.C.A. § 28-3-109(a)(3)", "discovery_rule": False, "notes": "6 years from breach"},
    {"claim_type": "Oral Contract", "years": 6, "statute": "T.C.A. § 28-3-109(a)(3)", "discovery_rule": False, "notes": "6 years from breach"},
    {"claim_type": "Fraud / Misrepresentation", "years": 3, "statute": "T.C.A. § 28-3-105", "discovery_rule": True, "notes": "3 years; discovery rule applies"},
    {"claim_type": "Defamation / Libel / Slander", "years": 1, "statute": "T.C.A. § 28-3-104(a)(1)", "discovery_rule": False, "notes": "1 year from publication"},
    {"claim_type": "Products Liability", "years": 1, "statute": "T.C.A. § 28-3-104", "discovery_rule": True, "notes": "1 year; 10-year statute of repose"},
    {"claim_type": "Workers' Compensation", "years": 1, "statute": "T.C.A. § 50-6-203", "discovery_rule": False, "notes": "1 year from injury or last voluntary payment"},
    {"claim_type": "Government Tort Claims", "years": 1, "statute": "T.C.A. § 29-20-305", "discovery_rule": False, "notes": "12 months; notice to government within 120 days"},
    {"claim_type": "TCPA (Consumer Protection)", "years": 1, "statute": "T.C.A. § 47-18-110", "discovery_rule": True, "notes": "1 year; 5-year statute of repose from transaction"},
    {"claim_type": "Conversion", "years": 3, "statute": "T.C.A. § 28-3-105", "discovery_rule": False, "notes": "3 years from conversion"},
    {"claim_type": "Trespass", "years": 3, "statute": "T.C.A. § 28-3-105", "discovery_rule": False, "notes": "3 years from trespass"},
    {"claim_type": "Intentional Infliction of Emotional Distress", "years": 1, "statute": "T.C.A. § 28-3-104(a)(1)", "discovery_rule": False, "notes": "1 year from conduct"},
    {"claim_type": "Employment Discrimination (State)", "years": 1, "statute": "T.C.A. § 4-21-311", "discovery_rule": False, "notes": "1 year from discriminatory act; file with THRC first"},
    {"claim_type": "Employment Discrimination (Federal/Title VII)", "years": 0, "statute": "42 U.S.C. § 2000e-5", "discovery_rule": False, "notes": "300 days to file EEOC charge; 90 days to sue after right-to-sue letter"},
]

SOL_CLAIM_TYPES = [entry["claim_type"] for entry in TN_SOL_TABLE]


def compute_sol_urgency(days_remaining: int) -> str:
    """Return urgency level for statute of limitations countdown."""
    if days_remaining < 0:
        return "expired"
    if days_remaining <= 30:
        return "critical"
    if days_remaining <= 90:
        return "warning"
    return "ok"


_SOL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sol_tracking")


def _sol_path(case_id: str) -> str:
    return os.path.join(_SOL_DIR, f"{case_id}_sol.json")


def calculate_sol_deadline(claim_type: str, incident_date: str,
                           discovery_date: str = "") -> Dict:
    """Calculate SOL deadline for a given claim type and incident date."""
    sol_entry = next((s for s in TN_SOL_TABLE if s["claim_type"] == claim_type), None)
    if not sol_entry:
        return {"error": f"Unknown claim type: {claim_type}"}

    try:
        base_date_str = discovery_date if discovery_date and sol_entry.get("discovery_rule") else incident_date
        base_date = date.fromisoformat(base_date_str)
    except (ValueError, TypeError):
        return {"error": f"Invalid date format: {base_date_str}"}

    years = sol_entry["years"]
    if years == 0:
        # Special handling (e.g., federal employment — admin filing)
        return {
            "claim_type": claim_type,
            "statute": sol_entry["statute"],
            "deadline": "See administrative filing deadlines",
            "days_remaining": None,
            "notes": sol_entry["notes"],
            "urgency": "📋 Administrative",
        }

    try:
        deadline = base_date.replace(year=base_date.year + years)
    except ValueError:
        # Handle Feb 29 → Feb 28
        deadline = base_date.replace(year=base_date.year + years, day=28)

    days_remaining = (deadline - date.today()).days

    if days_remaining < 0:
        urgency = "🔴 EXPIRED"
    elif days_remaining <= 30:
        urgency = "🔴 CRITICAL"
    elif days_remaining <= 60:
        urgency = "🟠 URGENT"
    elif days_remaining <= 90:
        urgency = "🟡 WARNING"
    else:
        urgency = "🟢 OK"

    return {
        "claim_type": claim_type,
        "statute": sol_entry["statute"],
        "incident_date": incident_date,
        "discovery_date": discovery_date,
        "base_date": str(base_date),
        "deadline": str(deadline),
        "days_remaining": days_remaining,
        "notes": sol_entry["notes"],
        "urgency": urgency,
        "discovery_rule": sol_entry.get("discovery_rule", False),
    }


def load_sol_tracking(case_id: str) -> Dict:
    """Load SOL tracking data for a case."""
    path = _sol_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"claims": [], "notes": ""}


def save_sol_tracking(case_id: str, data: Dict):
    """Save SOL tracking data for a case."""
    data["updated_at"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(_sol_path(case_id)), exist_ok=True)
    with open(_sol_path(case_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_sol_claim(case_id: str, claim_type: str, incident_date: str,
                  discovery_date: str = "", tolling_notes: str = "",
                  description: str = "") -> str:
    """Add a SOL claim to track for a case."""
    data = load_sol_tracking(case_id)
    claim_id = uuid.uuid4().hex[:8]
    claim = {
        "id": claim_id,
        "claim_type": claim_type,
        "incident_date": incident_date,
        "discovery_date": discovery_date,
        "tolling_notes": tolling_notes,
        "description": description,
        "created_at": datetime.now().isoformat(),
    }
    # Calculate deadline
    calc = calculate_sol_deadline(claim_type, incident_date, discovery_date)
    claim["deadline"] = calc.get("deadline", "")
    claim["days_remaining"] = calc.get("days_remaining")
    claim["urgency"] = calc.get("urgency", "")

    data["claims"].append(claim)
    save_sol_tracking(case_id, data)
    return claim_id


def delete_sol_claim(case_id: str, claim_id: str):
    """Delete a SOL claim from tracking."""
    data = load_sol_tracking(case_id)
    data["claims"] = [c for c in data["claims"] if c.get("id") != claim_id]
    save_sol_tracking(case_id, data)


def get_sol_alerts(case_mgr, threshold_days: int = 90) -> List[Dict]:
    """Scan all cases for SOL deadlines within threshold. Returns urgency-ranked list."""
    alerts = []
    cases = case_mgr.list_cases()
    today = date.today()

    for case in cases:
        cid = case["id"]
        status = case_mgr.get_status(cid)
        if status in ("archived", "closed_resolved", "closed_dismissed",
                       "closed_plea", "closed_acquitted", "closed_other"):
            continue

        sol_data = load_sol_tracking(cid)
        for claim in sol_data.get("claims", []):
            calc = calculate_sol_deadline(
                claim.get("claim_type", ""),
                claim.get("incident_date", ""),
                claim.get("discovery_date", ""),
            )
            days = calc.get("days_remaining")
            if days is not None and days <= threshold_days:
                alerts.append({
                    "case_id": cid,
                    "case_name": case.get("name", cid),
                    "claim_type": claim.get("claim_type", ""),
                    "description": claim.get("description", ""),
                    "deadline": calc.get("deadline", ""),
                    "days_remaining": days,
                    "urgency": calc.get("urgency", ""),
                    "statute": calc.get("statute", ""),
                    "tolling_notes": claim.get("tolling_notes", ""),
                })

    alerts.sort(key=lambda x: x.get("days_remaining", 999))
    return alerts


# ═══════════════════════════════════════════════════════════════════════
#  13.  ENGAGEMENT / DISENGAGEMENT LETTER GENERATOR  (RPC 1.2 / 1.16)
# ═══════════════════════════════════════════════════════════════════════

LETTER_TYPES = [
    "Engagement Letter",
    "Limited Scope Engagement",
    "Non-Engagement / Declination",
    "Disengagement / Withdrawal",
    "Conflict Waiver",
]

LETTER_TEMPLATES = {
    "Engagement Letter": {
        "rpc": "RPC 1.2, 1.4, 1.5",
        "description": "Formal agreement to represent a client in a specific matter",
        "required_fields": ["client_name", "matter_description", "fee_type", "rate_or_amount", "retainer_amount"],
        "optional_fields": ["scope_limitations", "billing_frequency", "termination_terms"],
        "template": """
{firm_name}
{firm_address}
{date}

{client_name}
{client_address}

Re: Engagement of Legal Services — {matter_description}

Dear {client_name},

Thank you for selecting {firm_name} to represent you in the above-referenced matter. This letter confirms the terms of our engagement.

SCOPE OF REPRESENTATION
We have agreed to represent you in connection with: {matter_description}.
{scope_limitations}

This engagement does not include representation in any other matters unless separately agreed in writing.

FEES AND BILLING
Fee Arrangement: {fee_type}
Rate/Amount: {rate_or_amount}
Retainer: {retainer_amount}
{billing_frequency}

EXPENSES
In addition to legal fees, you will be responsible for costs and expenses incurred on your behalf, including but not limited to filing fees, deposition costs, expert witness fees, and travel expenses.

CLIENT RESPONSIBILITIES
You agree to cooperate fully, provide all relevant information and documents promptly, and keep us informed of any changes relevant to your matter. Per RPC 1.4, we will keep you reasonably informed of the status of your matter and promptly respond to your reasonable requests for information.

DOCUMENT RETENTION
Following conclusion of this matter, we will retain your file for a period consistent with our firm's retention policy, after which it may be destroyed.

TERMINATION
{termination_terms}
Either party may terminate this engagement at any time, consistent with RPC 1.16 and applicable court rules.

Please sign below to indicate your agreement to these terms and return one copy to our office.

Sincerely,

_______________________________
{attorney_name}
{firm_name}

AGREED AND ACCEPTED:

_______________________________    Date: ______________
{client_name}
""",
    },

    "Limited Scope Engagement": {
        "rpc": "RPC 1.2(c)",
        "description": "Agreement for limited/unbundled legal services",
        "required_fields": ["client_name", "matter_description", "specific_services", "excluded_services"],
        "optional_fields": ["fee_type", "rate_or_amount"],
        "template": """
{firm_name}
{firm_address}
{date}

{client_name}
{client_address}

Re: Limited Scope Engagement — {matter_description}

Dear {client_name},

This letter confirms that you have engaged {firm_name} to provide LIMITED legal services in connection with the above matter, pursuant to RPC 1.2(c).

SERVICES INCLUDED
The following specific services are included in this engagement:
{specific_services}

SERVICES EXCLUDED
The following services are specifically EXCLUDED from this engagement:
{excluded_services}

You understand and agree that our representation is limited to the specific services described above. We will not be responsible for any aspects of your matter outside this scope.

FEES
Fee Arrangement: {fee_type}
Rate/Amount: {rate_or_amount}

This engagement will conclude automatically upon completion of the specified services unless extended by mutual written agreement.

Sincerely,

_______________________________
{attorney_name}
{firm_name}

AGREED AND ACCEPTED:

_______________________________    Date: ______________
{client_name}
""",
    },

    "Non-Engagement / Declination": {
        "rpc": "RPC 1.16(d)",
        "description": "Formal declination of representation — critical for avoiding implied attorney-client relationships",
        "required_fields": ["client_name", "matter_description", "reason_declined"],
        "optional_fields": ["sol_warning", "referral_info"],
        "template": """
{firm_name}
{firm_address}
{date}

{client_name}
{client_address}

Re: Declination of Representation — {matter_description}

Dear {client_name},

Thank you for consulting with our firm regarding the above-referenced matter. After careful consideration, we have determined that we are unable to represent you in this matter.

REASON
{reason_declined}

IMPORTANT NOTICE — NO ATTORNEY-CLIENT RELATIONSHIP
Please be advised that NO attorney-client relationship has been formed between you and {firm_name}. Our consultation does not constitute legal representation, and we have not undertaken any obligation to protect your legal interests in this matter.

{sol_warning}

We strongly recommend that you consult with another attorney as soon as possible to protect your rights and interests.

{referral_info}

We wish you the best in resolving this matter.

Sincerely,

_______________________________
{attorney_name}
{firm_name}
""",
    },

    "Disengagement / Withdrawal": {
        "rpc": "RPC 1.16",
        "description": "Formal termination of representation with client protection provisions",
        "required_fields": ["client_name", "matter_description", "effective_date", "reason_withdrawal"],
        "optional_fields": ["pending_deadlines", "file_transfer_instructions"],
        "template": """
{firm_name}
{firm_address}
{date}

{client_name}
{client_address}

Re: Termination of Representation — {matter_description}

Dear {client_name},

This letter serves as formal notice that {firm_name} is withdrawing from representation in the above-referenced matter, effective {effective_date}.

REASON FOR WITHDRAWAL
{reason_withdrawal}

PENDING DEADLINES AND OBLIGATIONS
{pending_deadlines}

FILE TRANSFER
{file_transfer_instructions}

Your complete file will be made available to you or your new counsel upon request. Please arrange for pickup or provide instructions for delivery within 30 days.

IMPORTANT — PROTECT YOUR INTERESTS
It is essential that you retain new counsel promptly to avoid any adverse consequences to your legal rights. Any applicable statutes of limitations, filing deadlines, or court dates remain your responsibility.

TRUST ACCOUNT
Any funds remaining in our trust account on your behalf will be accounted for and returned to you, less any outstanding fees and costs, in accordance with RPC 1.15.

Sincerely,

_______________________________
{attorney_name}
{firm_name}

ACKNOWLEDGED:

_______________________________    Date: ______________
{client_name}
""",
    },

    "Conflict Waiver": {
        "rpc": "RPC 1.7(b)",
        "description": "Informed consent to waive conflict of interest",
        "required_fields": ["client_name", "matter_description", "conflict_description", "risks_to_client"],
        "optional_fields": ["other_client_name", "screening_measures"],
        "template": """
{firm_name}
{firm_address}
{date}

{client_name}
{client_address}

Re: Conflict of Interest Waiver — {matter_description}

Dear {client_name},

We are writing to disclose a potential conflict of interest and to request your informed written consent to proceed with representation, as required by RPC 1.7(b).

NATURE OF CONFLICT
{conflict_description}

POTENTIAL RISKS TO YOU
{risks_to_client}

{screening_measures}

YOUR RIGHT TO INDEPENDENT COUNSEL
You have the right to consult with independent counsel before deciding whether to consent to this conflict waiver. We encourage you to do so.

CONDITIONS OF CONSENT
By signing below, you acknowledge that:
1. You have been fully informed of the nature and extent of the conflict
2. You understand the potential risks to your interests
3. You have had the opportunity to consult with independent counsel
4. You voluntarily consent to {firm_name} continuing representation despite the conflict

This consent may be revoked at any time by providing written notice.

Sincerely,

_______________________________
{attorney_name}
{firm_name}

INFORMED CONSENT — I HAVE READ AND UNDERSTOOD THE ABOVE:

_______________________________    Date: ______________
{client_name}
""",
    },
}

_LETTERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "letters")


def _letters_path(case_id: str) -> str:
    return os.path.join(_LETTERS_DIR, f"{case_id}_letters.json")


def generate_letter(template_type: str, fields: Dict) -> str:
    """Generate a letter from a template, filling in placeholder fields."""
    tmpl = LETTER_TEMPLATES.get(template_type)
    if not tmpl:
        return f"Error: Unknown template type '{template_type}'"

    text = tmpl["template"]

    # Set defaults for common fields
    defaults = {
        "firm_name": "[FIRM NAME]",
        "firm_address": "[FIRM ADDRESS]",
        "attorney_name": "[ATTORNEY NAME]",
        "client_address": "[CLIENT ADDRESS]",
        "date": date.today().strftime("%B %d, %Y"),
        "scope_limitations": "",
        "billing_frequency": "",
        "termination_terms": "Either party may terminate this engagement upon reasonable written notice.",
        "sol_warning": "⚠️ STATUTE OF LIMITATIONS WARNING: Legal claims are subject to time limits. Failure to act within the applicable statute of limitations may result in permanent loss of your legal rights.",
        "referral_info": "You may contact the Tennessee Bar Association Lawyer Referral Service at (800) 486-8529 for assistance finding another attorney.",
        "pending_deadlines": "Please consult with your new attorney regarding any pending deadlines.",
        "file_transfer_instructions": "Please contact our office to arrange for transfer of your file.",
        "screening_measures": "",
    }

    for key, default in defaults.items():
        if key not in fields or not fields[key]:
            fields[key] = default

    for key, value in fields.items():
        text = text.replace(f"{{{key}}}", str(value))

    return text.strip()


def load_letter_records(case_id: str) -> List[Dict]:
    """Load letter records for a case."""
    path = _letters_path(case_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return sorted(json.load(f), key=lambda e: e.get("created_at", ""), reverse=True)
    return []


def save_letter_record(case_id: str, letter_type: str, recipient: str,
                       sent: bool = False, sent_date: str = "",
                       notes: str = "") -> str:
    """Save a record of a generated letter."""
    records = load_letter_records(case_id)
    record_id = uuid.uuid4().hex[:8]
    record = {
        "id": record_id,
        "letter_type": letter_type,
        "recipient": recipient,
        "sent": sent,
        "sent_date": sent_date,
        "notes": notes,
        "created_at": datetime.now().isoformat(),
    }
    records.append(record)
    os.makedirs(os.path.dirname(_letters_path(case_id)), exist_ok=True)
    with open(_letters_path(case_id), "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return record_id


def delete_letter_record(case_id: str, record_id: str):
    """Delete a letter record."""
    records = load_letter_records(case_id)
    records = [r for r in records if r.get("id") != record_id]
    os.makedirs(os.path.dirname(_letters_path(case_id)), exist_ok=True)
    with open(_letters_path(case_id), "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def get_cases_missing_engagement_letter(case_mgr) -> List[Dict]:
    """Find active cases without an engagement letter on file."""
    cases = case_mgr.list_cases()
    missing = []
    for case in cases:
        cid = case["id"]
        status = case_mgr.get_status(cid)
        if status in ("archived", "closed_resolved", "closed_dismissed",
                       "closed_plea", "closed_acquitted", "closed_other"):
            continue
        records = load_letter_records(cid)
        has_engagement = any(
            r.get("letter_type") in ("Engagement Letter", "Limited Scope Engagement")
            for r in records
        )
        if not has_engagement:
            missing.append({
                "case_id": cid,
                "case_name": case.get("name", cid),
                "status": status or "active",
                "letter_count": len(records),
            })
    return missing


# ═══════════════════════════════════════════════════════════════════════
#  14.  TENNESSEE SENTENCING & FINE RANGES  (T.C.A. § 40-35-111 / 112)
# ═══════════════════════════════════════════════════════════════════════

# Felony Sentencing Ranges — T.C.A. § 40-35-112
# Columns: Class, Offender Range, Min (years), Max (years), Statute
TN_FELONY_SENTENCING = [
    # Class A Felony
    {"class": "A", "range": "Esp. Mitigated", "min_years": 15, "max_years": 25, "statute": "§ 40-35-112(a)(1)", "notes": "Mitigating factors substantially outweigh enhancing; no prior felonies"},
    {"class": "A", "range": "Range I (Standard)", "min_years": 15, "max_years": 25, "statute": "§ 40-35-112(a)(1)", "notes": "No prior felony convictions"},
    {"class": "A", "range": "Range II (Multiple)", "min_years": 25, "max_years": 40, "statute": "§ 40-35-112(b)(1)", "notes": "Prior felony conviction(s)"},
    {"class": "A", "range": "Range III (Persistent)", "min_years": 40, "max_years": 60, "statute": "§ 40-35-112(c)(1)", "notes": "Two or more prior felony convictions"},
    {"class": "A", "range": "Career Offender", "min_years": 60, "max_years": 60, "statute": "§ 40-35-108(c)", "notes": "Three or more Class A or B felonies; 60-year mandatory minimum"},

    # Class B Felony
    {"class": "B", "range": "Esp. Mitigated", "min_years": 8, "max_years": 12, "statute": "§ 40-35-112(a)(2)", "notes": "Mitigating factors substantially outweigh enhancing"},
    {"class": "B", "range": "Range I (Standard)", "min_years": 8, "max_years": 12, "statute": "§ 40-35-112(a)(2)", "notes": "No prior felony convictions"},
    {"class": "B", "range": "Range II (Multiple)", "min_years": 12, "max_years": 20, "statute": "§ 40-35-112(b)(2)", "notes": "Prior felony conviction(s)"},
    {"class": "B", "range": "Range III (Persistent)", "min_years": 20, "max_years": 30, "statute": "§ 40-35-112(c)(2)", "notes": "Two or more prior felony convictions"},
    {"class": "B", "range": "Career Offender", "min_years": 30, "max_years": 30, "statute": "§ 40-35-108(c)", "notes": "Three or more Class A or B felonies"},

    # Class C Felony
    {"class": "C", "range": "Esp. Mitigated", "min_years": 3, "max_years": 6, "statute": "§ 40-35-112(a)(3)", "notes": "Mitigating factors substantially outweigh enhancing"},
    {"class": "C", "range": "Range I (Standard)", "min_years": 3, "max_years": 6, "statute": "§ 40-35-112(a)(3)", "notes": "No prior felony convictions"},
    {"class": "C", "range": "Range II (Multiple)", "min_years": 6, "max_years": 10, "statute": "§ 40-35-112(b)(3)", "notes": "Prior felony conviction(s)"},
    {"class": "C", "range": "Range III (Persistent)", "min_years": 10, "max_years": 15, "statute": "§ 40-35-112(c)(3)", "notes": "Two or more prior felony convictions"},
    {"class": "C", "range": "Career Offender", "min_years": 15, "max_years": 15, "statute": "§ 40-35-108(c)", "notes": "Three or more qualifying felonies"},

    # Class D Felony
    {"class": "D", "range": "Esp. Mitigated", "min_years": 2, "max_years": 4, "statute": "§ 40-35-112(a)(4)", "notes": "Mitigating factors substantially outweigh enhancing"},
    {"class": "D", "range": "Range I (Standard)", "min_years": 2, "max_years": 4, "statute": "§ 40-35-112(a)(4)", "notes": "No prior felony convictions"},
    {"class": "D", "range": "Range II (Multiple)", "min_years": 4, "max_years": 8, "statute": "§ 40-35-112(b)(4)", "notes": "Prior felony conviction(s)"},
    {"class": "D", "range": "Range III (Persistent)", "min_years": 8, "max_years": 12, "statute": "§ 40-35-112(c)(4)", "notes": "Two or more prior felony convictions"},
    {"class": "D", "range": "Career Offender", "min_years": 12, "max_years": 12, "statute": "§ 40-35-108(c)", "notes": "Three or more qualifying felonies"},

    # Class E Felony
    {"class": "E", "range": "Esp. Mitigated", "min_years": 1, "max_years": 2, "statute": "§ 40-35-112(a)(5)", "notes": "Mitigating factors substantially outweigh enhancing"},
    {"class": "E", "range": "Range I (Standard)", "min_years": 1, "max_years": 2, "statute": "§ 40-35-112(a)(5)", "notes": "No prior felony convictions"},
    {"class": "E", "range": "Range II (Multiple)", "min_years": 2, "max_years": 4, "statute": "§ 40-35-112(b)(5)", "notes": "Prior felony conviction(s)"},
    {"class": "E", "range": "Range III (Persistent)", "min_years": 4, "max_years": 6, "statute": "§ 40-35-112(c)(5)", "notes": "Two or more prior felony convictions"},
    {"class": "E", "range": "Career Offender", "min_years": 6, "max_years": 6, "statute": "§ 40-35-108(c)", "notes": "Three or more qualifying felonies"},
]

# Misdemeanor Sentencing — T.C.A. § 40-35-111(e)
TN_MISDEMEANOR_SENTENCING = [
    {"class": "A", "max_jail": "11 months, 29 days", "max_jail_days": 364, "statute": "§ 40-35-111(e)(1)", "notes": "Most serious misdemeanor; includes DUI, domestic assault, theft under $1,000"},
    {"class": "B", "max_jail": "6 months", "max_jail_days": 180, "statute": "§ 40-35-111(e)(2)", "notes": "Includes reckless driving, harassment"},
    {"class": "C", "max_jail": "30 days", "max_jail_days": 30, "statute": "§ 40-35-111(e)(3)", "notes": "Least serious; includes disorderly conduct, gambling"},
]

# Fine Ranges — T.C.A. § 40-35-111(b)
TN_FINE_SCHEDULE = [
    {"class": "A Felony", "max_fine": 50000, "statute": "§ 40-35-111(b)(1)", "notes": "Up to $50,000; or an amount not exceeding the amount of gain from the offense"},
    {"class": "B Felony", "max_fine": 25000, "statute": "§ 40-35-111(b)(2)", "notes": "Up to $25,000"},
    {"class": "C Felony", "max_fine": 10000, "statute": "§ 40-35-111(b)(3)", "notes": "Up to $10,000"},
    {"class": "D Felony", "max_fine": 5000, "statute": "§ 40-35-111(b)(4)", "notes": "Up to $5,000"},
    {"class": "E Felony", "max_fine": 3000, "statute": "§ 40-35-111(b)(5)", "notes": "Up to $3,000"},
    {"class": "A Misdemeanor", "max_fine": 2500, "statute": "§ 40-35-111(e)(1)", "notes": "Up to $2,500"},
    {"class": "B Misdemeanor", "max_fine": 500, "statute": "§ 40-35-111(e)(2)", "notes": "Up to $500"},
    {"class": "C Misdemeanor", "max_fine": 50, "statute": "§ 40-35-111(e)(3)", "notes": "Up to $50"},
]

# Release Eligibility — T.C.A. § 40-35-501
TN_RELEASE_ELIGIBILITY = [
    {"class": "A Felony", "percentage": "100%", "notes": "Must serve 100% of sentence (no parole for offenses after July 1, 1995); life sentences: 51 years before parole eligibility"},
    {"class": "B Felony", "percentage": "30%", "notes": "Serve 30% before release eligibility; certain violent B felonies require 85%"},
    {"class": "C Felony", "percentage": "30%", "notes": "Serve 30% before release eligibility; certain violent offenses require higher %"},
    {"class": "D Felony", "percentage": "20%", "notes": "Serve 20% before release eligibility"},
    {"class": "E Felony", "percentage": "20%", "notes": "Serve 20% before release eligibility"},
    {"class": "Especially Violent", "percentage": "85-100%", "notes": "First-degree murder, aggravated rape, certain drug offenses — 85-100% service required"},
]

# Community Corrections Eligibility — T.C.A. § 40-36-106
TN_COMMUNITY_CORRECTIONS = [
    {"eligible": "Class C, D, E felonies — Range I offenders", "statute": "§ 40-36-106(a)(1)", "notes": "Property offenses, drug offenses (non-violent)"},
    {"eligible": "Selected Class B felonies — Range I offenders", "statute": "§ 40-36-106(a)(2)", "notes": "Non-violent B felonies only; judge discretion"},
    {"eligible": "Probation violators — alternative to incarceration", "statute": "§ 40-36-106(c)", "notes": "As an intermediate sanction"},
    {"ineligible": "Class A felonies", "statute": "§ 40-36-106(a)", "notes": "Not eligible for community corrections"},
    {"ineligible": "Sexual offenses against minors", "statute": "§ 40-36-106(a)", "notes": "Not eligible regardless of class"},
    {"ineligible": "Offenses requiring 85% or 100% service", "statute": "§ 40-36-106(a)", "notes": "Not eligible"},
]

# Probation Eligibility — T.C.A. § 40-35-303
TN_PROBATION_ELIGIBILITY = [
    {"class": "Class C, D, E Felony", "presumption": "Favorable", "statute": "§ 40-35-303(a)", "notes": "Presumption of eligibility for alternative sentencing if sentence is 8 years or less and defendant is not disqualified"},
    {"class": "Class A, B Felony", "presumption": "None", "statute": "§ 40-35-303(a)", "notes": "No presumption of probation; must demonstrate suitability"},
    {"class": "Misdemeanors", "presumption": "Favorable", "statute": "§ 40-35-303(d)", "notes": "Presumption of probation or other alternative"},
]


def get_sentencing_range(felony_class: str, offender_range: str = "") -> List[Dict]:
    """Look up sentencing range for a felony class and optional offender range."""
    results = []
    for entry in TN_FELONY_SENTENCING:
        if entry["class"].upper() == felony_class.upper():
            if not offender_range or offender_range.lower() in entry["range"].lower():
                results.append(entry)
    return results


def get_full_sentencing_summary(felony_class: str) -> Dict:
    """Get a comprehensive sentencing summary for a felony class."""
    ranges = get_sentencing_range(felony_class)
    fine = next((f for f in TN_FINE_SCHEDULE if f["class"].startswith(f"{felony_class.upper()} Felony")), None)
    release = next((r for r in TN_RELEASE_ELIGIBILITY if r["class"].startswith(f"{felony_class.upper()} Felony")), None)
    return {
        "class": felony_class.upper(),
        "ranges": ranges,
        "max_fine": fine.get("max_fine", 0) if fine else 0,
        "fine_statute": fine.get("statute", "") if fine else "",
        "release_eligibility": release.get("percentage", "") if release else "",
        "release_notes": release.get("notes", "") if release else "",
    }


