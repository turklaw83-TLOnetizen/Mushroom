"""
payment_feed.py -- Payment Monitoring & Classification
Upload CSV exports from Chime, Venmo, Cash App (or generic bank CSVs),
parse transactions, AI-classify to clients, and record confirmed payments.
Storage: data/comms/payment_feed.json
"""

import csv
import io
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# -- Paths -----------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_COMMS_DIR = os.path.join(_SCRIPT_DIR, os.pardir, "data", "comms")
_FEED_FILE = os.path.join(_COMMS_DIR, "payment_feed.json")

FEED_STATUSES = ["unclassified", "classified", "recorded", "dismissed"]
PLATFORMS = ["venmo", "cashapp", "chime", "generic"]


def _ensure_dir():
    os.makedirs(_COMMS_DIR, exist_ok=True)


def _load_feed() -> List[Dict]:
    _ensure_dir()
    if os.path.exists(_FEED_FILE):
        with open(_FEED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_feed(feed: List[Dict]):
    _ensure_dir()
    with open(_FEED_FILE, "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)


# ===================================================================
#  1.  CSV PARSERS  — normalize transactions from each platform
# ===================================================================

def parse_venmo_csv(file_data: str) -> List[Dict]:
    """
    Parse Venmo CSV export. Venmo CSVs have columns:
    ,ID,Datetime,Type,Status,Note,From,To,Amount (total),...
    We want incoming payments (Type=Payment where we are the 'To').
    """
    transactions = []
    reader = csv.DictReader(io.StringIO(file_data))

    for row in reader:
        try:
            # Venmo uses various column names — try common ones
            amount_str = (
                row.get("Amount (total)", "")
                or row.get("Amount", "")
                or row.get("amount", "")
            ).strip()
            if not amount_str:
                continue

            # Clean amount: remove $, +, spaces
            amount_clean = amount_str.replace("$", "").replace("+", "").replace(",", "").strip()
            try:
                amount = float(amount_clean)
            except ValueError:
                continue

            # Only include incoming (positive) amounts
            if amount <= 0:
                continue

            sender = (
                row.get("From", "")
                or row.get("from", "")
                or row.get("Sender", "")
            ).strip()

            note = (
                row.get("Note", "")
                or row.get("note", "")
                or row.get("Description", "")
            ).strip()

            date_str = (
                row.get("Datetime", "")
                or row.get("Date", "")
                or row.get("date", "")
            ).strip()

            # Try to normalize date
            parsed_date = _parse_date(date_str)

            txn_type = row.get("Type", row.get("type", "")).strip()
            status = row.get("Status", row.get("status", "")).strip()

            # Skip non-complete transactions
            if status.lower() not in ("complete", "completed", ""):
                continue

            transactions.append({
                "id": f"txn_{uuid.uuid4().hex[:8]}",
                "platform": "venmo",
                "date": parsed_date,
                "amount": round(amount, 2),
                "sender": sender,
                "note": note,
                "type": txn_type,
                "raw_status": status,
                "status": "unclassified",
                "suggested_client_id": None,
                "suggested_plan_id": None,
                "confidence": 0.0,
                "classification_reason": "",
                "imported_at": datetime.now().isoformat(),
            })
        except Exception:
            logger.debug("Skipping unparseable Venmo row: %s", row)
            continue

    return transactions


def parse_cashapp_csv(file_data: str) -> List[Dict]:
    """
    Parse Cash App CSV export. Cash App CSVs typically have:
    Transaction ID, Date, Transaction Type, Currency, Amount, Fee, Net Amount,
    Asset Type, Asset Price, Asset Amount, Status, Notes, Name of sender/receiver, Account
    """
    transactions = []
    reader = csv.DictReader(io.StringIO(file_data))

    for row in reader:
        try:
            # Get amount (Cash App uses positive for received, negative for sent)
            amount_str = (
                row.get("Amount", "")
                or row.get("Net Amount", "")
                or row.get("amount", "")
            ).strip()
            if not amount_str:
                continue

            amount_clean = amount_str.replace("$", "").replace("+", "").replace(",", "").strip()
            try:
                amount = float(amount_clean)
            except ValueError:
                continue

            if amount <= 0:
                continue

            sender = (
                row.get("Name of sender/receiver", "")
                or row.get("Name", "")
                or row.get("Sender", "")
            ).strip()

            note = (
                row.get("Notes", "")
                or row.get("Note", "")
                or row.get("Description", "")
            ).strip()

            date_str = (
                row.get("Date", "")
                or row.get("date", "")
                or row.get("Datetime", "")
            ).strip()

            parsed_date = _parse_date(date_str)

            status = row.get("Status", row.get("status", "")).strip()
            if status.lower() not in ("complete", "completed", ""):
                continue

            transactions.append({
                "id": f"txn_{uuid.uuid4().hex[:8]}",
                "platform": "cashapp",
                "date": parsed_date,
                "amount": round(amount, 2),
                "sender": sender,
                "note": note,
                "type": row.get("Transaction Type", ""),
                "raw_status": status,
                "status": "unclassified",
                "suggested_client_id": None,
                "suggested_plan_id": None,
                "confidence": 0.0,
                "classification_reason": "",
                "imported_at": datetime.now().isoformat(),
            })
        except Exception:
            logger.debug("Skipping unparseable Cash App row: %s", row)
            continue

    return transactions


def parse_chime_csv(file_data: str) -> List[Dict]:
    """
    Parse Chime CSV/bank statement export. Chime statements typically have:
    Date, Description, Amount, Balance, Transaction Type
    """
    transactions = []
    reader = csv.DictReader(io.StringIO(file_data))

    for row in reader:
        try:
            amount_str = (
                row.get("Amount", "")
                or row.get("Credit", "")
                or row.get("amount", "")
            ).strip()
            if not amount_str:
                continue

            amount_clean = amount_str.replace("$", "").replace("+", "").replace(",", "").strip()
            try:
                amount = float(amount_clean)
            except ValueError:
                continue

            if amount <= 0:
                continue

            description = (
                row.get("Description", "")
                or row.get("Memo", "")
                or row.get("description", "")
            ).strip()

            date_str = (
                row.get("Date", "")
                or row.get("Transaction Date", "")
                or row.get("date", "")
            ).strip()

            parsed_date = _parse_date(date_str)

            # Try to extract sender from description
            sender = _extract_sender_from_description(description)

            transactions.append({
                "id": f"txn_{uuid.uuid4().hex[:8]}",
                "platform": "chime",
                "date": parsed_date,
                "amount": round(amount, 2),
                "sender": sender,
                "note": description,
                "type": row.get("Transaction Type", row.get("Type", "")),
                "raw_status": "",
                "status": "unclassified",
                "suggested_client_id": None,
                "suggested_plan_id": None,
                "confidence": 0.0,
                "classification_reason": "",
                "imported_at": datetime.now().isoformat(),
            })
        except Exception:
            logger.debug("Skipping unparseable Chime row: %s", row)
            continue

    return transactions


def parse_generic_csv(file_data: str) -> List[Dict]:
    """
    Fallback parser for generic bank CSVs.
    Auto-detects common column patterns.
    """
    transactions = []
    reader = csv.DictReader(io.StringIO(file_data))

    # Map common column name variants
    cols = reader.fieldnames or []
    col_lower = {c.lower().strip(): c for c in cols}

    def find_col(*candidates):
        for c in candidates:
            if c in col_lower:
                return col_lower[c]
        return None

    date_col = find_col("date", "transaction date", "posted date", "datetime")
    amount_col = find_col("amount", "credit", "deposit", "net amount", "credit amount")
    desc_col = find_col("description", "memo", "notes", "note", "details", "narrative")
    sender_col = find_col("sender", "from", "name", "payee", "name of sender/receiver")

    if not amount_col:
        logger.warning("Could not detect amount column in CSV. Columns: %s", cols)
        return []

    for row in reader:
        try:
            amount_str = row.get(amount_col, "").strip()
            if not amount_str:
                continue

            amount_clean = amount_str.replace("$", "").replace("+", "").replace(",", "").strip()
            try:
                amount = float(amount_clean)
            except ValueError:
                continue

            if amount <= 0:
                continue

            date_str = row.get(date_col, "") if date_col else ""
            parsed_date = _parse_date(date_str)

            description = row.get(desc_col, "") if desc_col else ""
            sender = row.get(sender_col, "") if sender_col else _extract_sender_from_description(description)

            transactions.append({
                "id": f"txn_{uuid.uuid4().hex[:8]}",
                "platform": "generic",
                "date": parsed_date,
                "amount": round(amount, 2),
                "sender": sender.strip(),
                "note": description.strip(),
                "type": "",
                "raw_status": "",
                "status": "unclassified",
                "suggested_client_id": None,
                "suggested_plan_id": None,
                "confidence": 0.0,
                "classification_reason": "",
                "imported_at": datetime.now().isoformat(),
            })
        except Exception:
            continue

    return transactions


# ===================================================================
#  2.  HELPERS
# ===================================================================

def _parse_date(date_str: str) -> str:
    """Try multiple date formats and return ISO date string."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M %p",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Return original if can't parse
    return date_str.strip()[:10]


def _extract_sender_from_description(description: str) -> str:
    """Try to extract a person/entity name from a bank description."""
    desc = description.strip()
    # Common patterns: "Zelle from John Smith", "VENMO John Smith", etc.
    prefixes = [
        "zelle from ", "venmo ", "cashapp ", "cash app ",
        "payment from ", "transfer from ", "deposit from ",
    ]
    lower = desc.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return desc[len(prefix):].strip()
    return desc


# ===================================================================
#  3.  AI CLASSIFICATION  — match transactions to clients
# ===================================================================

def classify_transactions(
    transactions: List[Dict],
    clients: List[Dict],
    plans_by_client: Dict[str, List[Dict]],
) -> List[Dict]:
    """
    For each transaction, suggest which client/plan it belongs to.
    Uses name matching + amount matching first, then AI for ambiguous cases.
    Returns updated transaction list with suggestions.
    """
    if not clients:
        return transactions

    # Build lookup structures
    client_names = {}  # lowercase name -> client
    for c in clients:
        name = c.get("name", "").lower().strip()
        if name:
            client_names[name] = c
        # Also index by first name and last name
        parts = name.split()
        if len(parts) >= 2:
            client_names[parts[0]] = c  # first name
            client_names[parts[-1]] = c  # last name

    for txn in transactions:
        if txn["status"] != "unclassified":
            continue

        sender = txn.get("sender", "").lower().strip()
        note = txn.get("note", "").lower().strip()
        amount = txn.get("amount", 0)

        best_match = None
        best_confidence = 0.0
        best_reason = ""
        best_plan_id = None

        # -- Pass 1: Exact / fuzzy name matching --
        for name_key, client in client_names.items():
            if not name_key:
                continue

            score = 0.0
            reasons = []

            # Check sender name
            if name_key in sender or sender in name_key:
                score += 0.5
                reasons.append(f"sender name matches '{client.get('name', '')}'")

            # Check note/memo
            if name_key in note:
                score += 0.2
                reasons.append("name found in memo")

            if score == 0:
                continue

            # -- Pass 2: Amount matching against pending payments --
            client_id = client.get("id", "")
            client_plans = plans_by_client.get(client_id, [])
            for plan in client_plans:
                if plan.get("status") != "active":
                    continue
                for sp in plan.get("scheduled_payments", []):
                    if sp["status"] in ("paid", "waived"):
                        continue
                    owed = sp["amount"] - sp.get("paid_amount", 0)
                    if abs(owed - amount) < 0.01:
                        score += 0.3
                        reasons.append(f"amount ${amount:.2f} matches pending payment")
                        best_plan_id = plan["id"]
                        break

            if score > best_confidence:
                best_confidence = score
                best_match = client
                best_reason = "; ".join(reasons)

        if best_match and best_confidence > 0:
            txn["suggested_client_id"] = best_match.get("id", "")
            txn["suggested_plan_id"] = best_plan_id
            txn["confidence"] = round(min(best_confidence, 1.0), 2)
            txn["classification_reason"] = best_reason
            txn["status"] = "classified"
            txn["suggested_client_name"] = best_match.get("name", "")

    return transactions


def classify_with_ai(
    transactions: List[Dict],
    clients: List[Dict],
) -> List[Dict]:
    """
    Use LLM for ambiguous transaction classification.
    Only processes unclassified transactions (those that failed name/amount matching).
    """
    unclassified = [t for t in transactions if t["status"] == "unclassified"]
    if not unclassified or not clients:
        return transactions

    try:
        from core.llm import get_llm, invoke_with_retry
        llm = get_llm(max_output_tokens=2048)
        if not llm:
            return transactions

        client_list = "\n".join(
            f"- {c.get('name', '?')} (ID: {c.get('id', '?')}, email: {c.get('email', '')})"
            for c in clients
        )

        txn_list = "\n".join(
            f"- ID={t['id']}, ${t['amount']:.2f}, sender='{t['sender']}', "
            f"note='{t['note']}', date={t['date']}, platform={t['platform']}"
            for t in unclassified[:20]  # Limit to 20 at a time
        )

        system_msg = (
            "You are a legal billing assistant. Match incoming payments to clients. "
            "Output ONLY valid JSON: an array of objects with keys: "
            "txn_id, client_id (or null if no match), confidence (0-1), reason."
        )
        user_msg = (
            f"Match these incoming payments to the correct client:\n\n"
            f"CLIENTS:\n{client_list}\n\n"
            f"TRANSACTIONS:\n{txn_list}\n\n"
            f"Return JSON array."
        )

        from langchain_core.messages import SystemMessage, HumanMessage
        response = invoke_with_retry(llm, [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg),
        ])

        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

        matches = json.loads(text.strip())
        if not isinstance(matches, list):
            return transactions

        # Apply AI suggestions
        txn_map = {t["id"]: t for t in transactions}
        client_map = {c["id"]: c for c in clients}
        for match in matches:
            txn_id = match.get("txn_id", "")
            client_id = match.get("client_id")
            if txn_id in txn_map and client_id and client_id in client_map:
                t = txn_map[txn_id]
                t["suggested_client_id"] = client_id
                t["confidence"] = match.get("confidence", 0.5)
                t["classification_reason"] = match.get("reason", "AI classification")
                t["status"] = "classified"
                t["suggested_client_name"] = client_map[client_id].get("name", "")

    except Exception:
        logger.exception("AI classification failed")

    return transactions


# ===================================================================
#  4.  FEED CRUD  — manage imported transactions
# ===================================================================

def import_transactions(file_data: str, platform: str) -> List[Dict]:
    """
    Parse a CSV file and import transactions into the feed.
    Returns list of newly imported transactions.
    """
    # Parse based on platform
    parsers = {
        "venmo": parse_venmo_csv,
        "cashapp": parse_cashapp_csv,
        "chime": parse_chime_csv,
        "generic": parse_generic_csv,
    }
    parser = parsers.get(platform, parse_generic_csv)
    new_txns = parser(file_data)

    if not new_txns:
        return []

    # Run classification
    try:
        from core.crm import _load_all as load_all_clients
        from core.billing import load_payment_plans

        clients = load_all_clients()
        plans_by_client: Dict[str, List[Dict]] = {}
        for c in clients:
            cid = c.get("id", "")
            if cid:
                plans_by_client[cid] = load_payment_plans(cid)

        new_txns = classify_transactions(new_txns, clients, plans_by_client)

        # AI classify any still-unclassified
        still_unclassified = [t for t in new_txns if t["status"] == "unclassified"]
        if still_unclassified:
            new_txns = classify_with_ai(new_txns, clients)

    except Exception:
        logger.exception("Classification failed during import")

    # Save to feed
    feed = _load_feed()
    feed.extend(new_txns)
    _save_feed(feed)

    logger.info("Imported %d transactions from %s", len(new_txns), platform)
    return new_txns


def get_unclassified() -> List[Dict]:
    """Return transactions pending classification."""
    feed = _load_feed()
    return [
        t for t in feed
        if t.get("status") in ("unclassified", "classified")
    ]


def get_feed(status_filter: str = "") -> List[Dict]:
    """Get all feed items, optionally filtered by status."""
    feed = _load_feed()
    if status_filter:
        feed = [t for t in feed if t.get("status") == status_filter]
    return sorted(feed, key=lambda t: t.get("date", ""), reverse=True)


def confirm_and_record(
    transaction_id: str,
    client_id: str,
    plan_id: str,
    user: str = "",
) -> Optional[str]:
    """
    Confirm a transaction classification and record as a payment.
    Returns payment_id on success, None on failure.
    """
    feed = _load_feed()
    txn = None
    for t in feed:
        if t["id"] == transaction_id:
            txn = t
            break

    if not txn:
        return None

    if txn.get("status") == "recorded":
        return None  # Already recorded

    try:
        from core.billing import record_plan_payment

        payment_id = record_plan_payment(
            client_id=client_id,
            plan_id=plan_id,
            amount=txn["amount"],
            method=txn.get("platform", ""),
            payer_name=txn.get("sender", ""),
            note=f"[Auto-imported from {txn.get('platform', 'CSV')}] {txn.get('note', '')}",
            date_str=txn.get("date", ""),
            recorded_by=user,
        )

        if payment_id:
            txn["status"] = "recorded"
            txn["recorded_client_id"] = client_id
            txn["recorded_plan_id"] = plan_id
            txn["recorded_payment_id"] = payment_id
            txn["recorded_at"] = datetime.now().isoformat()
            txn["recorded_by"] = user
            _save_feed(feed)
            logger.info(
                "Recorded txn %s as payment %s for client %s",
                transaction_id, payment_id, client_id,
            )
            return payment_id
        else:
            logger.warning("record_plan_payment returned None for txn %s", transaction_id)
            return None

    except Exception:
        logger.exception("Failed to record transaction %s", transaction_id)
        return None


def dismiss_transaction(transaction_id: str, reason: str = "") -> bool:
    """Mark a transaction as dismissed (not a client payment)."""
    feed = _load_feed()
    for t in feed:
        if t["id"] == transaction_id:
            t["status"] = "dismissed"
            t["dismissed_reason"] = reason
            t["dismissed_at"] = datetime.now().isoformat()
            _save_feed(feed)
            return True
    return False


def reclassify_transaction(
    transaction_id: str,
    client_id: str,
    plan_id: str = "",
    client_name: str = "",
) -> bool:
    """Manually reassign a transaction to a different client."""
    feed = _load_feed()
    for t in feed:
        if t["id"] == transaction_id:
            t["suggested_client_id"] = client_id
            t["suggested_plan_id"] = plan_id
            t["suggested_client_name"] = client_name
            t["confidence"] = 1.0
            t["classification_reason"] = "Manual classification"
            t["status"] = "classified"
            _save_feed(feed)
            return True
    return False
