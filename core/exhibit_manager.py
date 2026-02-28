"""
exhibit_manager.py -- Evidence Exhibit Numbering & Export
Auto-generate exhibit labels based on relevance sort order.
One-click PDF export of exhibit list.
"""

import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def generate_exhibit_list(
    case_id: str,
    prep_id: str,
    case_mgr,
    relevance_scores: Dict[str, dict],
    custom_order: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Generate ordered exhibit list from relevance-sorted files.
    
    Args:
        case_id: Case ID
        prep_id: Preparation ID
        case_mgr: CaseManager instance
        relevance_scores: {filename: {"score": N, "citations": N}}
        custom_order: Optional custom ordering override
    
    Returns:
        List of exhibit dicts with label, filename, score, page_count
    """
    files = case_mgr.get_case_files(case_id) or []
    
    if custom_order:
        # Use custom order
        basename_to_path = {os.path.basename(f): f for f in files}
        sorted_files = [basename_to_path[n] for n in custom_order if n in basename_to_path]
        # Append any files not in custom order
        remaining = [f for f in files if os.path.basename(f) not in custom_order]
        sorted_files.extend(remaining)
    else:
        # Sort by relevance score descending
        sorted_files = sorted(
            files,
            key=lambda f: relevance_scores.get(os.path.basename(f), {}).get("score", 0),
            reverse=True,
        )
    
    exhibits = []
    for i, fpath in enumerate(sorted_files):
        fname = os.path.basename(fpath)
        rel = relevance_scores.get(fname, {})
        
        # Generate label: A-Z, then AA, AB, etc.
        label = _exhibit_label(i)
        
        # Get page count for PDFs
        page_count = _get_page_count(fpath)
        
        # Get file tags
        all_tags = case_mgr.get_all_file_tags(case_id)
        tags = all_tags.get(fname, [])
        
        exhibits.append({
            "label": label,
            "filename": fname,
            "path": fpath,
            "score": rel.get("score", 0),
            "citations": rel.get("citations", 0),
            "page_count": page_count,
            "tags": tags,
            "description": ", ".join(tags) if tags else "",
            "size_bytes": os.path.getsize(fpath) if os.path.exists(fpath) else 0,
        })
    
    return exhibits


def _exhibit_label(index: int) -> str:
    """Generate exhibit label: A, B, ..., Z, AA, AB, ..."""
    if index < 26:
        return f"Exhibit {chr(65 + index)}"
    else:
        # AA, AB, AC... after Z
        first = chr(65 + (index // 26) - 1)
        second = chr(65 + (index % 26))
        return f"Exhibit {first}{second}"


def _get_page_count(file_path: str) -> int:
    """Get page count for PDF files. Returns 0 for non-PDFs."""
    if not file_path.lower().endswith(".pdf"):
        return 0
    try:
        import fitz
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def save_exhibit_list(case_id: str, prep_id: str, exhibits: List[Dict], case_mgr) -> None:
    """Save the exhibit list to the preparation directory."""
    data = {
        "generated_at": datetime.now().isoformat(),
        "exhibits": exhibits,
    }
    case_mgr.storage.save_prep_json(case_id, prep_id, "exhibit_list.json", data)


def load_exhibit_list(case_id: str, prep_id: str, case_mgr) -> List[Dict]:
    """Load a previously saved exhibit list."""
    data = case_mgr.storage.load_prep_json(case_id, prep_id, "exhibit_list.json", {})
    return data.get("exhibits", [])


def export_exhibit_list_pdf(exhibits: List[Dict], case_name: str) -> io.BytesIO:
    """
    Generate a PDF exhibit list document.
    
    Returns BytesIO buffer with the PDF.
    """
    from fpdf import FPDF
    
    class ExhibitPDF(FPDF):
        @property
        def epw(self):
            return self.w - self.l_margin - self.r_margin
    
    pdf = ExhibitPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "EXHIBIT LIST", ln=1, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, case_name, ln=1, align="C")
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%B %d, %Y')}", ln=1, align="C")
    pdf.ln(8)
    
    # Table header
    col_widths = [25, 70, 45, 20, 30]
    headers = ["Exhibit", "Document", "Description", "Pages", "Relevance"]
    
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()
    
    # Table rows
    pdf.set_font("Helvetica", "", 8)
    for ex in exhibits:
        label = ex.get("label", "")
        fname = ex.get("filename", "")
        desc = ex.get("description", "")
        pages = str(ex.get("page_count", "")) if ex.get("page_count") else "-"
        score = str(ex.get("score", "")) if ex.get("score") else "-"
        
        # Truncate long filenames
        if len(fname) > 35:
            fname = fname[:32] + "..."
        if len(desc) > 25:
            desc = desc[:22] + "..."
        
        pdf.cell(col_widths[0], 6, label, border=1, align="C")
        pdf.cell(col_widths[1], 6, fname, border=1)
        pdf.cell(col_widths[2], 6, desc, border=1)
        pdf.cell(col_widths[3], 6, pages, border=1, align="C")
        pdf.cell(col_widths[4], 6, score, border=1, align="C")
        pdf.ln()
    
    # Footer
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Total exhibits: {len(exhibits)}", ln=1)
    
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf
