# ─── PDF Export Functions ───────────────────────────────────────────
# Generates PDF reports and trial binders using fpdf2.
#
# fpdf2 cursor fix applied: self.set_x(self.l_margin) before every
# multi_cell() call, and w=self.epw instead of w=0 where appropriate.

import io
import json
import logging
import re
from datetime import datetime

from fpdf import FPDF

logger = logging.getLogger(__name__)


class PDFReport(FPDF):
    @property
    def epw(self):
        """Effective page width (available in fpdf2 but not fpdf 1.x)."""
        return self.w - self.l_margin - self.r_margin

    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'AllRise Beta - Case Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def generate_pdf_report(state, case_name):
    """
    Generates a PDF document from the AgentState using fpdf2.
    Returns a BytesIO object.
    """
    pdf = PDFReport()
    pdf.add_page()

    def safe_text(text):
        if not text: return ""
        t = str(text)
        # Replace common Unicode characters with ASCII equivalents
        t = t.replace('\u2014', '-').replace('\u2013', '-')  # em/en dash
        t = t.replace('\u2018', "'").replace('\u2019', "'")  # curly quotes
        t = t.replace('\u201c', '"').replace('\u201d', '"')  # curly double quotes
        t = t.replace('\u2022', '*').replace('\u2026', '...')  # bullet, ellipsis
        t = t.replace('\u2010', '-').replace('\u2011', '-')  # hyphens
        t = t.replace('\u2012', '-').replace('\u2015', '-')  # more dashes
        return t.encode('latin-1', 'replace').decode('latin-1')

    # Title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, safe_text(f"{case_name}"), ln=True, align="C")
    pdf.ln(10)

    def add_section_header(title):
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, safe_text(title), ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "", 11)

    # 1. Case Summary
    add_section_header("1. Case Summary")
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(state.get("case_summary", "No summary available.")))
    pdf.ln(5)

    # 2. Defense Strategy
    add_section_header("2. Defense Strategy")
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(state.get("strategy_notes", "No strategy notes available.")))
    pdf.ln(5)

    # 3. Witnesses
    add_section_header("3. Witness Analysis")
    witnesses = state.get("witnesses", [])
    if witnesses:
        # Simple list view for PDF (tables are complex in simple fpdf)
        for w in witnesses:
            name = safe_text(w.get("name", "Unknown"))
            w_type = safe_text(w.get("type", "Unknown"))
            goal = safe_text(w.get("goal", ""))

            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 6, f"{name} ({w_type})", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=6, txt=f"Goal: {goal}")
            pdf.ln(2)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt="No specific witnesses identified.")
    pdf.ln(5)

    # 4. Timeline
    add_section_header("4. Chronological Timeline")
    timeline = state.get("timeline", [])
    if isinstance(timeline, list) and timeline:
        for event in timeline:
            date = safe_text(event.get("date", ""))
            time = safe_text(event.get("time", ""))
            desc = safe_text(event.get("event", ""))
            src = safe_text(event.get("source", ""))
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=6, txt=f"{date} {time} - {desc} [Source: {src}]")
            pdf.ln(1)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(timeline) if timeline else "No detailed timeline."))
    pdf.ln(5)

    # 5. Cross Examination
    add_section_header("5. Cross-Examination Plan")
    cross = state.get("cross_examination_plan", [])
    if isinstance(cross, list):
        for item in cross:
            try:
                q = safe_text(item.get('question', '') if isinstance(item, dict) else str(item))
                rat = safe_text(item.get('rationale', '') if isinstance(item, dict) else '')

                pdf.set_font("Arial", "B", 10)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(w=pdf.epw, h=6, txt=f"Q: {q}")
                pdf.set_font("Arial", "I", 10)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(w=pdf.epw, h=6, txt=f"Rationale: {rat}")
                pdf.ln(2)
            except Exception:
                pdf.ln(2)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(cross)))
    pdf.ln(5)

    # 6. Direct Examination
    add_section_header("6. Direct Examination Plan")
    direct = state.get("direct_examination_plan", [])
    if isinstance(direct, list):
        for item in direct:
            try:
                q = safe_text(item.get('question', '') if isinstance(item, dict) else str(item))
                goal = safe_text(item.get('goal', '') if isinstance(item, dict) else '')

                pdf.set_font("Arial", "B", 10)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(w=pdf.epw, h=6, txt=f"Q: {q}")
                pdf.set_font("Arial", "I", 10)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(w=pdf.epw, h=6, txt=f"Goal: {goal}")
                pdf.ln(2)
            except Exception:
                pdf.ln(2)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(direct)))

    # 7. Devil's Advocate
    da = state.get("devils_advocate_notes", "")
    if da:
        add_section_header("7. Devil's Advocate Analysis")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(da)))
        pdf.ln(5)

    # 8. Evidence Foundations
    evidence = state.get("evidence_foundations", [])
    if evidence:
        add_section_header("8. Evidence Foundations")
        if isinstance(evidence, list):
            for e in evidence:
                if isinstance(e, dict):
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(e.get('item', e.get('evidence', '')))))
                    pdf.set_font("Arial", "", 10)
                    if e.get('foundation'):
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(f"Foundation: {e['foundation']}"))
                    if e.get('admissibility'):
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(f"Admissibility: {e['admissibility']}"))
                    pdf.ln(2)
                else:
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(e)))
        else:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(evidence)))
        pdf.ln(5)

    # 9. Statement Conflicts
    conflicts = state.get("consistency_check", "")
    if conflicts:
        add_section_header("9. Statement Consistency & Contradictions")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(conflicts)))
        pdf.ln(5)

    # 10. Elements Map
    elements = state.get("elements_map", "")
    if elements:
        add_section_header("10. Legal Elements Map")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(elements)))
        pdf.ln(5)

    # 11. Investigation Plan
    investigation = state.get("investigation_plan", [])
    if investigation:
        add_section_header("11. Investigation Plan")
        if isinstance(investigation, list):
            for task in investigation:
                if isinstance(task, dict):
                    status = "[DONE]" if task.get('completed') else "[ ]"
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(f"{status} {task.get('task', task.get('description', str(task)))}"))
                else:
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(f"[ ] {task}"))
                pdf.ln(1)
        else:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(investigation)))
        pdf.ln(5)

    # 12. Knowledge Graph Entities
    entities = state.get("entities", [])
    if entities:
        add_section_header("12. Knowledge Graph Entities")
        if isinstance(entities, list):
            for ent in entities:
                if isinstance(ent, dict):
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(0, 6, safe_text(f"{ent.get('name', '')} ({ent.get('type', '')})"), ln=True)
                    pdf.set_font("Arial", "", 10)
                    details = ent.get('details', ent.get('description', ''))
                    if details:
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(details)))
                    pdf.ln(1)
        else:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(entities)))
        pdf.ln(5)

    # 13. Voir Dire Strategy
    voir_dire = state.get("voir_dire_strategy", "")
    if voir_dire:
        add_section_header("13. Voir Dire Strategy")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(voir_dire)))
        pdf.ln(5)

    # 14. Legal Research
    research = state.get("legal_research_data", [])
    research_summary = state.get("research_summary", "")
    if research_summary or research:
        add_section_header("14. Legal Research")
        if research_summary:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(research_summary)))
            pdf.ln(3)
        if isinstance(research, list):
            for r in research:
                if isinstance(r, dict):
                    try:
                        pdf.set_font("Arial", "B", 10)
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(str(r.get('query', ''))))
                        pdf.set_font("Arial", "", 10)
                        result_text = str(r.get('result', ''))
                        if len(result_text) > 5000:
                            result_text = result_text[:5000] + "... [truncated]"
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(result_text))
                        pdf.ln(2)
                    except Exception:
                        pdf.ln(2)
        pdf.ln(5)

    # 15. Medical Records Analysis
    medical = state.get("medical_records_analysis", {})
    if medical and isinstance(medical, dict):
        add_section_header("15. Medical Records Analysis")
        for key, value in medical.items():
            if value:
                try:
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(0, 6, safe_text(key.replace('_', ' ').title()), ln=True)
                    pdf.set_font("Arial", "", 10)
                    val_text = str(value)
                    if len(val_text) > 5000:
                        val_text = val_text[:5000] + "... [truncated]"
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(w=pdf.epw, h=6, txt=safe_text(val_text))
                    pdf.ln(3)
                except Exception:
                    pdf.ln(3)
        pdf.ln(5)

    # Output
    buffer = io.BytesIO()
    pdf_content = pdf.output(dest='S')
    # fpdf2 may return str or bytes depending on version -- ensure bytes
    if isinstance(pdf_content, str):
        pdf_content = pdf_content.encode('latin-1')
    buffer.write(pdf_content)
    buffer.seek(0)
    return buffer


# =====================================================================
#  TRIAL BINDER -- NATIVE PDF VERSION
# =====================================================================

class TrialBinderPDF(FPDF):
    """Custom FPDF subclass for the trial binder."""
    def __init__(self, case_name=""):
        super().__init__()
        self._case_name = case_name

    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 7)
            self.set_text_color(120, 120, 120)
            txt = self._case_name[:60] if self._case_name else ''
            # Sanitize Unicode chars that built-in FPDF fonts can't handle
            txt = txt.replace('\u2014', '-').replace('\u2013', '-')
            txt = txt.replace('\u2018', "'").replace('\u2019', "'")
            txt = txt.replace('\u201c', '"').replace('\u201d', '"')
            txt = txt.replace('\u2022', '*').replace('\u2026', '...')
            txt = txt.encode('latin-1', 'replace').decode('latin-1')
            self.cell(0, 5, f'{txt}', 0, 0, 'L')
            self.cell(0, 5, 'CONFIDENTIAL - ATTORNEY WORK PRODUCT', 0, 1, 'R')
            self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def generate_trial_binder_pdf(state, case_name, prep_type="trial", prep_name=""):
    """
    Generates a print-ready trial binder as a native PDF.
    Mirrors the Word version's 13-tab structure with full-page tab divider pages.
    Returns a BytesIO object.
    """
    pdf = TrialBinderPDF(case_name)
    pdf.set_auto_page_break(auto=True, margin=20)

    # -- Helpers --------------------------------------------------------
    def s(text):
        """Safe text for fpdf (latin-1 encode)."""
        if not text:
            return ""
        t = str(text)
        t = t.replace('\u2014', '-').replace('\u2013', '-')
        t = t.replace('\u2018', "'").replace('\u2019', "'")
        t = t.replace('\u201c', '"').replace('\u201d', '"')
        t = t.replace('\u2022', '*').replace('\u2026', '...')
        t = t.replace('\u2501', '-').replace('\u25b6', '>').replace('\u25c0', '<')
        return t.encode('latin-1', 'replace').decode('latin-1')

    def try_parse_json(content, fallback_type="list"):
        if not content:
            return [] if fallback_type == "list" else {}
        if isinstance(content, list):
            return content
        if isinstance(content, dict):
            return content
        text = str(content)
        try:
            text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
            text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
            text = text.strip()
            if fallback_type == "list":
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            else:
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
        except Exception:
            pass
        return [] if fallback_type == "list" else {}

    def tab_divider(tab_num, title):
        """Full-page tab divider separator sheet."""
        pdf.add_page()
        pdf.ln(80)
        pdf.set_font('Arial', 'B', 48)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 20, s(f'TAB {tab_num}'), 0, 1, 'C')
        pdf.ln(5)
        pdf.set_font('Arial', '', 14)
        pdf.set_text_color(187, 187, 187)
        pdf.cell(0, 8, '-' * 50, 0, 1, 'C')
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(52, 73, 94)
        pdf.cell(0, 15, s(title), 0, 1, 'C')
        pdf.ln(20)
        pdf.set_font('Arial', 'I', 11)
        pdf.set_text_color(153, 153, 153)
        pdf.cell(0, 10, '> Insert physical tab divider here <', 0, 1, 'C')

    def section_header(title):
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 10, s(title), 0, 1, 'L')
        pdf.set_draw_color(44, 62, 80)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
        pdf.ln(5)

    def body_text(text, bold=False):
        pdf.set_font('Arial', 'B' if bold else '', 10)
        pdf.set_text_color(30, 30, 30)
        try:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w=pdf.epw, h=5, txt=s(text))
        except Exception:
            pass
        pdf.ln(2)

    def bullet(text):
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(30, 30, 30)
        try:
            pdf.set_x(pdf.l_margin)
            pdf.cell(8, 5, '*', 0, 0)
            w = pdf.w - pdf.r_margin - pdf.get_x()
            if w < 10:
                pdf.ln()
                pdf.set_x(pdf.l_margin + 8)
                w = pdf.w - pdf.r_margin - pdf.get_x()
            pdf.multi_cell(w, 5, s(text))
        except Exception:
            pdf.ln()
        pdf.ln(1)

    def table_header(cols, widths):
        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(44, 62, 80)
        pdf.set_text_color(255, 255, 255)
        for i, col in enumerate(cols):
            pdf.cell(widths[i], 7, s(col), 1, 0, 'C', fill=True)
        pdf.ln()

    def table_row(vals, widths, shade=False):
        pdf.set_font('Arial', '', 9)
        if shade:
            pdf.set_fill_color(240, 240, 240)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(30, 30, 30)
        max_h = 7
        for i, val in enumerate(vals):
            pdf.cell(widths[i], max_h, s(str(val)[:60]), 1, 0, 'L', fill=True)
        pdf.ln()

    def empty_note(text="No data available for this section."):
        pdf.set_font('Arial', 'I', 10)
        pdf.set_text_color(150, 150, 150)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w=pdf.epw, h=6, txt=s(text))
        pdf.ln(3)

    type_labels = {
        "trial": "Trial Preparation",
        "prelim_hearing": "Preliminary Hearing",
        "motion_hearing": "Motion Hearing"
    }

    # -- TAB 1: COVER PAGE ---------------------------------------------
    tab_divider(1, "COVER PAGE")
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font('Arial', 'B', 28)
    pdf.set_text_color(44, 62, 80)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w=pdf.epw, h=14, txt=s(case_name), align='C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, s(type_labels.get(prep_type, "Analysis")), 0, 1, 'C')
    if prep_name:
        pdf.cell(0, 10, s(prep_name), 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, s(f'Generated: {datetime.now().strftime("%B %d, %Y")}'), 0, 1, 'C')
    pdf.ln(30)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 8, 'CONFIDENTIAL - ATTORNEY WORK PRODUCT', 0, 1, 'C')
    pdf.cell(0, 6, 'ATTORNEY-CLIENT PRIVILEGE', 0, 1, 'C')

    # -- TAB 2: TABLE OF CONTENTS --------------------------------------
    tab_divider(2, "TABLE OF CONTENTS")
    pdf.add_page()
    section_header("Table of Contents")
    toc_items = [
        (1, "Cover Page"), (2, "Table of Contents"), (3, "Case Theory & Themes"),
        (4, "Charges / Claims Checklist"), (5, "Legal Elements Matrix"),
        (6, "Witness Binder"), (7, "Exhibit List & Foundations"),
        (8, "Timeline of Events"), (9, "Cross-Examination Outlines"),
        (10, "Direct-Examination Outlines"), (11, "Jury Selection (Voir Dire)"),
        (12, "Risk Assessment & Devil's Advocate"), (13, "Investigation Checklist")
    ]
    for num, title in toc_items:
        pdf.set_font('Arial', '', 11)
        pdf.set_text_color(30, 30, 30)
        dotted = '.' * (60 - len(title))
        pdf.cell(0, 8, s(f'  Tab {num}:  {title}  {dotted}'), 0, 1)

    # -- TAB 3: CASE THEORY & THEMES -----------------------------------
    tab_divider(3, "CASE THEORY & THEMES")
    pdf.add_page()
    section_header("Case Theory & Strategy")
    summary = state.get("case_summary", "")
    if summary:
        body_text(str(summary))
    else:
        empty_note("Case summary has not been generated.")
    strategy = state.get("strategy_notes", "")
    if strategy:
        pdf.ln(5)
        section_header("Defense Strategy")
        body_text(str(strategy))

    # -- TAB 4: CHARGES / CLAIMS ---------------------------------------
    tab_divider(4, "CHARGES / CLAIMS CHECKLIST")
    pdf.add_page()
    section_header("Charges / Claims")
    charges = try_parse_json(state.get("charges", []))
    if charges:
        widths = [60, 40, 30, 60]
        table_header(["Charge / Claim", "Statute", "Severity", "Jury Instructions"], widths)
        for i, ch in enumerate(charges):
            if isinstance(ch, dict):
                table_row([
                    ch.get("name", ch.get("charge", "Unknown")),
                    ch.get("statute", "N/A"),
                    ch.get("severity", ch.get("class", "N/A")),
                    ch.get("jury_instructions", "")[:60]
                ], widths, shade=(i % 2 == 1))
    else:
        empty_note("No charges have been identified.")

    # -- TAB 5: LEGAL ELEMENTS MATRIX ----------------------------------
    tab_divider(5, "LEGAL ELEMENTS MATRIX")
    pdf.add_page()
    section_header("Legal Elements Map")
    elements = try_parse_json(state.get("legal_elements", []))
    if elements:
        widths = [40, 50, 60, 40]
        table_header(["Charge", "Element", "Evidence", "Strength"], widths)
        for i, el in enumerate(elements):
            if isinstance(el, dict):
                table_row([
                    el.get("charge", ""),
                    el.get("element", ""),
                    el.get("evidence", el.get("supporting_evidence", "")),
                    el.get("strength", el.get("assessment", ""))
                ], widths, shade=(i % 2 == 1))
    else:
        empty_note("Legal elements analysis has not been run.")

    # -- TAB 6: WITNESS BINDER -----------------------------------------
    tab_divider(6, "WITNESS BINDER")
    pdf.add_page()
    witnesses = try_parse_json(state.get("witnesses", []))
    cross_plan = try_parse_json(state.get("cross_examination_plan", []))
    direct_plan = try_parse_json(state.get("direct_examination_plan", []))
    if witnesses:
        section_header(f"Master Witness List ({len(witnesses)} witnesses)")
        widths = [50, 30, 60, 50]
        table_header(["Name", "Type", "Goal", "Contact"], widths)
        for i, w in enumerate(witnesses):
            if isinstance(w, dict):
                table_row([
                    w.get("name", "Unknown"),
                    w.get("type", w.get("classification", "Unknown")),
                    w.get("goal", "")[:60],
                    w.get("contact", "")[:50]
                ], widths, shade=(i % 2 == 1))

        # Per-witness detail
        for w in witnesses:
            if not isinstance(w, dict):
                continue
            wname = w.get("name", "Unknown")
            pdf.ln(8)
            section_header(f"Witness: {wname}")
            body_text(f"Type: {w.get('type', 'Unknown')}  |  Goal: {w.get('goal', 'N/A')}")

            # Linked cross-exam questions
            for cp in cross_plan:
                if isinstance(cp, dict):
                    cp_name = cp.get("witness", cp.get("witness_name", ""))
                    if cp_name and cp_name.lower() in wname.lower():
                        topics = cp.get("topics", cp.get("questions", []))
                        if isinstance(topics, list):
                            for t in topics:
                                if isinstance(t, dict):
                                    body_text(f"Cross Topic: {t.get('topic', '')}", bold=True)
                                    for q in t.get("questions", []):
                                        if isinstance(q, dict):
                                            bullet(q.get("question", str(q)))
                                        else:
                                            bullet(str(q))

            # Linked direct-exam questions
            for dp in direct_plan:
                if isinstance(dp, dict):
                    dp_name = dp.get("witness", dp.get("witness_name", ""))
                    if dp_name and dp_name.lower() in wname.lower():
                        topics = dp.get("topics", dp.get("questions", []))
                        if isinstance(topics, list):
                            for t in topics:
                                if isinstance(t, dict):
                                    body_text(f"Direct Topic: {t.get('topic', '')}", bold=True)
                                    for q in t.get("questions", []):
                                        if isinstance(q, dict):
                                            bullet(q.get("question", str(q)))
                                        else:
                                            bullet(str(q))
    else:
        section_header("Witness Binder")
        empty_note("No witnesses have been identified.")

    # -- TAB 7: EXHIBIT LIST & FOUNDATIONS ------------------------------
    tab_divider(7, "EXHIBIT LIST & FOUNDATIONS")
    pdf.add_page()
    section_header("Exhibit List & Admissibility")
    evidence = try_parse_json(state.get("evidence_foundations", []))
    if evidence:
        for i, ev in enumerate(evidence):
            if isinstance(ev, dict):
                body_text(f"Exhibit {i+1}: {ev.get('item', ev.get('evidence', 'Unknown'))}", bold=True)
                if ev.get("foundation") or ev.get("admissibility_steps"):
                    bullet(f"Foundation: {ev.get('foundation', ev.get('admissibility_steps', ''))}")
                if ev.get("attacks") or ev.get("potential_attacks"):
                    bullet(f"Attacks: {ev.get('attacks', ev.get('potential_attacks', ''))}")
                pdf.ln(3)
    else:
        empty_note("Evidence foundations have not been analyzed.")

    # -- TAB 8: TIMELINE -----------------------------------------------
    tab_divider(8, "TIMELINE OF EVENTS")
    pdf.add_page()
    section_header("Chronological Timeline")
    timeline = try_parse_json(state.get("timeline", []))
    if timeline:
        widths = [30, 20, 90, 50]
        table_header(["Date", "Time", "Event", "Source"], widths)
        for i, ev in enumerate(timeline):
            if isinstance(ev, dict):
                table_row([
                    ev.get("date", ""),
                    ev.get("time", ""),
                    ev.get("event", ev.get("description", ""))[:90],
                    ev.get("source", "")[:50]
                ], widths, shade=(i % 2 == 1))
    else:
        empty_note("Timeline has not been generated.")

    # -- TAB 9: CROSS-EXAMINATION OUTLINES -----------------------------
    tab_divider(9, "CROSS-EXAMINATION OUTLINES")
    pdf.add_page()
    section_header("Cross-Examination Plans")
    if cross_plan:
        for wp in cross_plan:
            if isinstance(wp, dict):
                wname = wp.get("witness", wp.get("witness_name", "Unknown"))
                body_text(f"Witness: {wname}", bold=True)
                topics = wp.get("topics", wp.get("questions", []))
                if isinstance(topics, list):
                    for t in topics:
                        if isinstance(t, dict):
                            body_text(f"  Topic: {t.get('topic', '')}")
                            for q in t.get("questions", []):
                                if isinstance(q, dict):
                                    bullet(f"Q: {q.get('question', '')}")
                                    if q.get("source"):
                                        pdf.set_font('Arial', 'I', 8)
                                        pdf.set_text_color(100, 100, 100)
                                        pdf.cell(8)
                                        pdf.set_x(pdf.l_margin + 8)
                                        pdf.multi_cell(w=pdf.epw - 8, h=4, txt=s(f"Source: {q['source']}"))
                                else:
                                    bullet(str(q))
                pdf.ln(4)
    else:
        empty_note("Cross-examination plans have not been generated.")

    # -- TAB 10: DIRECT-EXAMINATION OUTLINES ---------------------------
    tab_divider(10, "DIRECT-EXAMINATION OUTLINES")
    pdf.add_page()
    section_header("Direct-Examination Plans")
    if direct_plan:
        for wp in direct_plan:
            if isinstance(wp, dict):
                wname = wp.get("witness", wp.get("witness_name", "Unknown"))
                body_text(f"Witness: {wname}", bold=True)
                topics = wp.get("topics", wp.get("questions", []))
                if isinstance(topics, list):
                    for t in topics:
                        if isinstance(t, dict):
                            body_text(f"  Topic: {t.get('topic', '')}")
                            for q in t.get("questions", []):
                                if isinstance(q, dict):
                                    bullet(f"Q: {q.get('question', '')}")
                                    if q.get("goal"):
                                        pdf.set_font('Arial', 'I', 8)
                                        pdf.set_text_color(100, 100, 100)
                                        pdf.cell(8)
                                        pdf.set_x(pdf.l_margin + 8)
                                        pdf.multi_cell(w=pdf.epw - 8, h=4, txt=s(f"Goal: {q['goal']}"))
                                else:
                                    bullet(str(q))
                pdf.ln(4)
    else:
        empty_note("Direct-examination plans have not been generated.")

    # -- TAB 11: JURY SELECTION (VOIR DIRE) ----------------------------
    tab_divider(11, "JURY SELECTION (VOIR DIRE)")
    pdf.add_page()
    section_header("Voir Dire Strategy")
    vd = try_parse_json(state.get("voir_dire", {}), fallback_type="dict")
    if vd:
        if vd.get("ideal_juror"):
            body_text("Ideal Juror Profile:", bold=True)
            body_text(str(vd["ideal_juror"]))
        if vd.get("red_flags"):
            body_text("Red Flags:", bold=True)
            flags = vd["red_flags"]
            if isinstance(flags, list):
                for f in flags:
                    bullet(str(f))
            else:
                body_text(str(flags))
        if vd.get("questions"):
            body_text("Voir Dire Questions:", bold=True)
            qs = vd["questions"]
            if isinstance(qs, list):
                for q in qs:
                    if isinstance(q, dict):
                        bullet(f"{q.get('question', '')}  [Goal: {q.get('goal', '')}]")
                    else:
                        bullet(str(q))
    else:
        empty_note("Voir dire strategy has not been generated.")

    # -- TAB 12: RISK ASSESSMENT & DEVIL'S ADVOCATE --------------------
    tab_divider(12, "RISK ASSESSMENT")
    pdf.add_page()
    section_header("Risk Assessment & Devil's Advocate")
    da = state.get("devils_advocate_notes", "")
    if da:
        body_text("Devil's Advocate Analysis:", bold=True)
        body_text(str(da))
    mock = state.get("mock_jury_feedback", "")
    if mock:
        pdf.ln(3)
        body_text("Mock Jury Feedback:", bold=True)
        body_text(str(mock))
    cc = state.get("consistency_check", "")
    if cc:
        pdf.ln(3)
        body_text("Consistency Check:", bold=True)
        if isinstance(cc, list):
            for item in cc:
                if isinstance(item, dict):
                    bullet(f"{item.get('issue', item.get('finding', str(item)))}")
                else:
                    bullet(str(item))
        else:
            body_text(str(cc))
    if not da and not mock and not cc:
        empty_note("Risk assessment data has not been generated.")

    # -- TAB 13: INVESTIGATION CHECKLIST -------------------------------
    tab_divider(13, "INVESTIGATION CHECKLIST")
    pdf.add_page()
    section_header("Investigation Tasks")
    inv = try_parse_json(state.get("investigation_plan", []))
    if inv:
        widths = [90, 30, 30, 40]
        table_header(["Task", "Priority", "Status", "Assigned To"], widths)
        for i, task in enumerate(inv):
            if isinstance(task, dict):
                status = task.get("status", "pending")
                marker = "[X]" if status == "completed" else "[ ]"
                table_row([
                    f"{marker} {task.get('task', task.get('description', ''))}",
                    task.get("priority", ""),
                    status,
                    task.get("assigned_to", "")
                ], widths, shade=(i % 2 == 1))
    else:
        empty_note("Investigation plan has not been generated.")

    # -- APPENDICES ----------------------------------------------------
    med = state.get("medical_records_analysis", "")
    legal_research = state.get("legal_research_data", "")
    depo = state.get("deposition_analysis", "")
    if med or legal_research or depo:
        pdf.add_page()
        pdf.ln(60)
        pdf.set_font('Arial', 'B', 36)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 20, 'APPENDICES', 0, 1, 'C')

        if med:
            pdf.add_page()
            section_header("Appendix A: Medical Records Analysis")
            body_text(str(med))
        if legal_research:
            pdf.add_page()
            section_header("Appendix B: Legal Research")
            body_text(str(legal_research))
        if depo:
            pdf.add_page()
            section_header("Appendix C: Deposition Analysis")
            body_text(str(depo))

    # -- END OF BINDER -------------------------------------------------
    pdf.add_page()
    pdf.ln(80)
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, 'END OF TRIAL BINDER', 0, 1, 'C')
    pdf.ln(5)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, s(f'Generated by AllRise Beta on {datetime.now().strftime("%B %d, %Y")}'), 0, 1, 'C')
    pdf.ln(3)
    pdf.set_font('Arial', 'B', 9)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 8, 'CONFIDENTIAL - ATTORNEY WORK PRODUCT', 0, 1, 'C')

    # -- Save ----------------------------------------------------------
    buffer = io.BytesIO()
    pdf_content = pdf.output(dest='S')
    # fpdf may return str or bytes depending on version -- ensure bytes
    if isinstance(pdf_content, str):
        pdf_content = pdf_content.encode('latin-1')
    buffer.write(pdf_content)
    buffer.seek(0)
    return buffer
