# ─── Courtroom Quick Cards (Print-Ready PDF) ─────────────────────
# Generates compact, print-ready reference cards for courtroom use:
#   - Witness cards with key facts and impeachment points
#   - Evidence cards with authentication scripts
#   - Objection quick-reference cards

import io
import json
import logging

from fpdf import FPDF

logger = logging.getLogger(__name__)


class QuickCardPDF(FPDF):
    """Compact PDF for courtroom reference cards."""
    @property
    def epw(self):
        """Effective page width (available in fpdf2 but not fpdf 1.x)."""
        return self.w - self.l_margin - self.r_margin

    def __init__(self, card_type="witness", case_name=""):
        super().__init__(orientation='L', unit='mm', format='A5')  # landscape A5 ~ 5.8x8.3"
        self._card_type = card_type
        self._case_name = case_name

    def header(self):
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(120, 120, 120)
        label = {"witness": "WITNESS CARD", "evidence": "EVIDENCE CARD", "objections": "OBJECTION CARD"}.get(self._card_type, "QUICK CARD")
        self.cell(0, 4, f"{label}  |  {self._case_name}", border=0, align='R', ln=1)
        self.ln(1)

    def footer(self):
        self.set_y(-8)
        self.set_font("Helvetica", "I", 6)
        self.set_text_color(160, 160, 160)
        self.cell(0, 4, f"Page {self.page_no()}", align='C')


def _safe_latin1(text):
    """Encode text for FPDF (latin-1 safe)."""
    if not isinstance(text, str):
        text = str(text)
    return text.encode('latin-1', 'replace').decode('latin-1')


def generate_quick_cards_pdf(state: dict, card_type: str = "witness", case_name: str = "") -> io.BytesIO:
    """
    Generates compact, print-ready courtroom reference cards as a PDF.

    Card types:
        "witness"    -- Key facts, impeachment points, do/don't ask per witness
        "evidence"   -- Authentication script for each exhibit
        "objections" -- Common objections with basis and response

    Returns a BytesIO object containing the PDF.
    """
    pdf = QuickCardPDF(card_type=card_type, case_name=case_name)
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(8, 12, 8)

    if card_type == "witness":
        _build_witness_cards(pdf, state)
    elif card_type == "evidence":
        _build_evidence_cards(pdf, state)
    elif card_type == "objections":
        _build_objection_cards(pdf, state)
    else:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, _safe_latin1(f"Unknown card type: {card_type}"), align='C')

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf


def _build_witness_cards(pdf, state):
    """One card per witness with key facts, alignment, impeachment points."""
    witnesses = state.get("witnesses", [])
    cross_data = state.get("cross_examination_plan", [])

    # Parse cross data if string
    if isinstance(cross_data, str):
        try:
            cross_data = json.loads(cross_data.replace("```json", "").replace("```", ""))
        except Exception as e:
            logger.warning("Cross-exam JSON parse failed in quick cards: %s", e)
            cross_data = []

    # Build lookup of cross questions by witness name
    cross_by_name = {}
    if isinstance(cross_data, list):
        for wb in cross_data:
            if isinstance(wb, dict):
                wname = wb.get("witness", "").strip().lower()
                cross_by_name[wname] = wb

    if not witnesses or not isinstance(witnesses, list):
        pdf.add_page()
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 10, "No witnesses identified. Run the Strategist module first.", align='C')
        return

    for w in witnesses:
        if not isinstance(w, dict):
            continue
        pdf.add_page()
        name = w.get("name", w.get("witness", "Unknown"))
        role = w.get("role", w.get("type", ""))
        alignment = w.get("alignment", "")
        summary = w.get("summary", w.get("significance", ""))

        # Header bar
        align_color = {"friendly": (34, 197, 94), "hostile": (239, 68, 68), "neutral": (234, 179, 8)}.get(
            str(alignment).lower(), (100, 116, 139)
        )
        pdf.set_fill_color(*align_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _safe_latin1(f"  {name}"), fill=True, ln=1)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 5, _safe_latin1(f"Role: {role}  |  Alignment: {alignment}"), ln=1)
        pdf.ln(2)

        # Summary
        if summary:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(str(summary)[:300]))
            pdf.ln(2)

        # Cross questions from cross_data
        wx = cross_by_name.get(name.strip().lower(), {})
        topics = wx.get("topics", []) if isinstance(wx, dict) else []
        if topics:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "KEY CROSS QUESTIONS:", ln=1)
            pdf.set_font("Helvetica", "", 8)
            q_num = 0
            for t in topics[:4]:
                if isinstance(t, dict):
                    for q in t.get("questions", [])[:3]:
                        q_text = q.get("question", str(q)) if isinstance(q, dict) else str(q)
                        q_num += 1
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(f"  {q_num}. {q_text[:120]}"))
            pdf.ln(1)

        # Impeachment points
        impeachment = w.get("impeachment_points", w.get("weaknesses", []))
        if impeachment and isinstance(impeachment, list):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "IMPEACHMENT POINTS:", ln=1)
            pdf.set_font("Helvetica", "", 8)
            for ip in impeachment[:5]:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(f"  * {str(ip)[:120]}"))


def _build_evidence_cards(pdf, state):
    """One card per evidence item with authentication script."""
    evidence = state.get("evidence_foundations", [])
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence.replace("```json", "").replace("```", ""))
        except Exception as e:
            logger.warning("Evidence JSON parse failed in quick cards: %s", e)
            evidence = []

    if not evidence or not isinstance(evidence, list):
        pdf.add_page()
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 10, "No evidence analysis available. Run the Evidence module first.", align='C')
        return

    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        pdf.add_page()
        title = ev.get("exhibit", ev.get("title", ev.get("document", "Unknown Exhibit")))
        ev_type = ev.get("type", ev.get("category", ""))
        foundation = ev.get("foundation", ev.get("authentication", ""))
        objections = ev.get("objections", ev.get("potential_objections", []))
        defense_value = ev.get("defense_value", ev.get("value", ev.get("significance", "")))

        # Header
        pdf.set_fill_color(59, 130, 246)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, _safe_latin1(f"  {str(title)[:80]}"), fill=True, ln=1)

        pdf.set_text_color(0, 0, 0)
        if ev_type:
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 5, _safe_latin1(f"Type: {ev_type}"), ln=1)
        pdf.ln(2)

        # Foundation / Authentication
        if foundation:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "AUTHENTICATION SCRIPT:", ln=1)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(str(foundation)[:500]))
            pdf.ln(2)

        # Potential Objections
        if objections:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "ANTICIPATED OBJECTIONS:", ln=1)
            pdf.set_font("Helvetica", "", 8)
            if isinstance(objections, list):
                for obj in objections[:5]:
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(f"  * {str(obj)[:120]}"))
            elif isinstance(objections, str):
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(objections[:400]))
            pdf.ln(1)

        # Defense Value
        if defense_value:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "VALUE:", ln=1)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=4, txt=_safe_latin1(str(defense_value)[:300]))


def _build_objection_cards(pdf, state):
    """Pre-built objection quick-reference cards."""
    # Standard objection library -- always useful even without case-specific data
    OBJECTIONS = [
        ("Hearsay", "FRE 801/802", "Out-of-court statement offered for truth of the matter asserted.",
         "Not offered for truth; state of mind; business record (803(6)); present sense impression (803(1)); excited utterance (803(2)); prior inconsistent statement (801(d)(1)(A))"),
        ("Relevance", "FRE 401/402", "Evidence that has no tendency to make a fact of consequence more or less probable.",
         "Goes to [specific fact]. Probative value outweighs any prejudice."),
        ("Prejudicial (403)", "FRE 403", "Probative value is substantially outweighed by danger of unfair prejudice.",
         "Probative value is high because [reason]. Limiting instruction cures any prejudice."),
        ("Lack of Foundation", "FRE 901/902", "Insufficient showing of authenticity or competence to testify.",
         "Lay proper foundation through witness testimony, chain of custody, or self-authentication."),
        ("Leading Question", "FRE 611(c)", "Suggests the answer on direct examination.",
         "Hostile witness / adverse party / foundational question / refreshing recollection."),
        ("Speculation", "FRE 602/701", "Witness lacks personal knowledge or is guessing.",
         "Witness has personal knowledge from [source]. Opinion is rationally based on perception (701)."),
        ("Best Evidence", "FRE 1002", "Original writing/recording/photo required to prove content.",
         "Original is unavailable (1004). Duplicate is admissible (1003). Content not in dispute."),
        ("Character Evidence", "FRE 404(a)/(b)", "Improper use of character to prove conforming conduct.",
         "Not offered for character -- offered to show motive/opportunity/intent/plan/knowledge/identity (404(b))."),
        ("Opinion (Lay)", "FRE 701", "Lay witness giving improper opinion testimony.",
         "Rationally based on perception, helpful to trier of fact, not based on specialized knowledge."),
        ("Expert Reliability", "FRE 702/Daubert", "Expert opinion lacks sufficient basis, reliability, or methodology.",
         "Methodology is generally accepted, peer-reviewed, tested, with known error rate. Expert is qualified."),
        ("Cumulative", "FRE 403/611", "Evidence is unnecessarily repetitive of what has already been established.",
         "This exhibit/testimony adds [specific new element] not yet covered."),
        ("Assumes Facts Not in Evidence", "FRE 611", "Question embeds an unproven factual premise.",
         "Rephrase without the embedded assumption."),
    ]

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "OBJECTION QUICK REFERENCE", align='C', ln=1)
    pdf.ln(3)

    for obj_name, rule, basis, response in OBJECTIONS:
        # Check if we need a new page
        if pdf.get_y() > 125:  # A5 landscape is ~148mm tall
            pdf.add_page()

        # Objection header
        pdf.set_fill_color(239, 68, 68)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, _safe_latin1(f"  {obj_name}  ({rule})"), fill=True, ln=1)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=3.5, txt=_safe_latin1(f"Basis: {basis}"))

        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(34, 97, 34)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=3.5, txt=_safe_latin1(f"Response: {response}"))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
