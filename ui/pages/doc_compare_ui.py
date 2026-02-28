"""
doc_compare_ui.py -- Side-by-Side Document Comparison
Compare two case documents with synchronized page navigation and text diff.
"""

import difflib
import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)


def render(case_id=None, case_mgr=None, results=None, **kwargs):
    """Render side-by-side document comparison."""
    st.markdown("### \U0001f4d1 Document Compare")
    st.caption("Compare two case documents side-by-side with text diff.")

    if not case_id or not case_mgr:
        st.info("No case selected.")
        return

    # Get all case files
    all_files = case_mgr.get_case_files(case_id)
    if len(all_files) < 2:
        st.info("Upload at least 2 documents to use the comparison tool.")
        return

    basenames = [os.path.basename(f) for f in all_files]
    file_map = {os.path.basename(f): f for f in all_files}

    # File selectors
    _sel1, _sel2 = st.columns(2)
    with _sel1:
        doc_a = st.selectbox(
            "Document A",
            basenames,
            index=0,
            key="_dc_doc_a",
        )
    with _sel2:
        _default_b = 1 if len(basenames) > 1 else 0
        doc_b = st.selectbox(
            "Document B",
            basenames,
            index=_default_b,
            key="_dc_doc_b",
        )

    if doc_a == doc_b:
        st.warning("Select two different documents to compare.")
        return

    path_a = file_map.get(doc_a, "")
    path_b = file_map.get(doc_b, "")

    if not os.path.exists(path_a) or not os.path.exists(path_b):
        st.error("One or both files not found.")
        return

    ext_a = os.path.splitext(doc_a)[1].lower()
    ext_b = os.path.splitext(doc_b)[1].lower()

    # Determine compare mode
    both_pdf = ext_a == ".pdf" and ext_b == ".pdf"
    both_text = ext_a in (".txt", ".md", ".csv") and ext_b in (".txt", ".md", ".csv")

    if both_pdf:
        _render_pdf_compare(path_a, path_b, doc_a, doc_b, case_id, case_mgr)
    elif both_text:
        _render_text_compare(path_a, path_b, doc_a, doc_b)
    else:
        # OCR text compare for mixed types
        _render_ocr_compare(path_a, path_b, doc_a, doc_b, case_id, case_mgr)


def _render_pdf_compare(path_a, path_b, name_a, name_b, case_id, case_mgr):
    """Render side-by-side PDF comparison with synchronized page nav."""
    try:
        import fitz
    except ImportError:
        st.error("Install `pymupdf` for PDF comparison.")
        return

    doc_a = fitz.open(path_a)
    doc_b = fitz.open(path_b)
    pages_a = len(doc_a)
    pages_b = len(doc_b)
    max_pages = max(pages_a, pages_b)

    # Zoom control
    _z1, _z2 = st.columns([3, 1])
    with _z2:
        zoom = st.selectbox("Zoom", [75, 100, 125, 150], index=1, key="_dc_zoom")
    dpi = int(72 * zoom / 100)

    # Synchronized page navigation
    _nav1, _nav2, _nav3 = st.columns([1, 2, 1])
    with _nav1:
        if st.button("\u2190 Prev", key="_dc_prev", disabled=st.session_state.get("_dc_page", 1) <= 1):
            st.session_state["_dc_page"] = max(1, st.session_state.get("_dc_page", 1) - 1)
            st.rerun()
    with _nav2:
        page_num = st.number_input(
            "Page", min_value=1, max_value=max_pages,
            value=st.session_state.get("_dc_page", 1),
            key="_dc_page_input",
        )
        if page_num != st.session_state.get("_dc_page", 1):
            st.session_state["_dc_page"] = page_num
            st.rerun()
    with _nav3:
        if st.button("Next \u2192", key="_dc_next", disabled=st.session_state.get("_dc_page", 1) >= max_pages):
            st.session_state["_dc_page"] = min(max_pages, st.session_state.get("_dc_page", 1) + 1)
            st.rerun()

    current_page = st.session_state.get("_dc_page", 1) - 1  # 0-indexed
    st.caption(f"Page {current_page + 1} of {max_pages}  |  {name_a}: {pages_a} pages  |  {name_b}: {pages_b} pages")

    # Side-by-side rendering
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(f"**{name_a}**")
        if current_page < pages_a:
            page_a = doc_a[current_page]
            pix_a = page_a.get_pixmap(dpi=dpi)
            st.image(pix_a.tobytes("png"), use_container_width=True)
        else:
            st.info(f"Document A has only {pages_a} pages.")

    with col_b:
        st.markdown(f"**{name_b}**")
        if current_page < pages_b:
            page_b = doc_b[current_page]
            pix_b = page_b.get_pixmap(dpi=dpi)
            st.image(pix_b.tobytes("png"), use_container_width=True)
        else:
            st.info(f"Document B has only {pages_b} pages.")

    doc_a.close()
    doc_b.close()

    # OCR text diff for current page
    _render_page_text_diff(case_id, case_mgr, name_a, name_b, path_a, path_b, current_page)


def _render_page_text_diff(case_id, case_mgr, name_a, name_b, path_a, path_b, page_num):
    """Show text diff for the current page using OCR cache."""
    with st.expander("\U0001f4dd Text Diff for This Page", expanded=False):
        text_a = _get_page_text(case_id, case_mgr, name_a, path_a, page_num)
        text_b = _get_page_text(case_id, case_mgr, name_b, path_b, page_num)

        if not text_a and not text_b:
            st.info("No OCR text available for this page. Run OCR first.")
            return

        _show_diff(text_a or "(no text)", text_b or "(no text)", name_a, name_b)


def _get_page_text(case_id, case_mgr, filename, filepath, page_num):
    """Get text for a specific page from OCR cache or PyMuPDF."""
    # Try OCR cache first
    try:
        from core.ingest import OCRCache
        data_dir = str(case_mgr.storage._base_dir)
        case_dir = os.path.join(data_dir, "cases", case_id)
        cache = OCRCache(case_dir)
        fsize = os.path.getsize(filepath)
        fkey = f"{filename}:{fsize}"
        page_text = cache.get_page_text(fkey, page_num)
        if page_text:
            return page_text
    except Exception:
        pass

    # Fall back to PyMuPDF text extraction
    try:
        import fitz
        doc = fitz.open(filepath)
        if page_num < len(doc):
            text = doc[page_num].get_text()
            doc.close()
            return text
        doc.close()
    except Exception:
        pass

    return ""


def _render_text_compare(path_a, path_b, name_a, name_b):
    """Compare two text files."""
    try:
        with open(path_a, "r", encoding="utf-8", errors="replace") as f:
            text_a = f.read()[:50000]
        with open(path_b, "r", encoding="utf-8", errors="replace") as f:
            text_b = f.read()[:50000]
    except IOError as e:
        st.error(f"Error reading files: {e}")
        return

    _show_diff(text_a, text_b, name_a, name_b)


def _render_ocr_compare(path_a, path_b, name_a, name_b, case_id, case_mgr):
    """Compare documents using OCR text."""
    st.info("Comparing using extracted/OCR text. For best results, ensure both documents have been OCR'd.")

    text_a = _get_full_text(case_id, case_mgr, name_a, path_a)
    text_b = _get_full_text(case_id, case_mgr, name_b, path_b)

    if not text_a and not text_b:
        st.warning("No text available for either document. Run OCR first.")
        return

    _show_diff(text_a or "(no text)", text_b or "(no text)", name_a, name_b)


def _get_full_text(case_id, case_mgr, filename, filepath):
    """Get full text for a document."""
    try:
        from core.ingest import OCRCache
        data_dir = str(case_mgr.storage._base_dir)
        case_dir = os.path.join(data_dir, "cases", case_id)
        cache = OCRCache(case_dir)
        fsize = os.path.getsize(filepath)
        fkey = f"{filename}:{fsize}"
        text = cache.get_text(fkey)
        if text:
            return text
    except Exception:
        pass

    # Try direct text extraction
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".txt", ".md", ".csv"):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read()[:50000]
        except IOError:
            pass
    elif ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(filepath)
            text = "\n".join(doc[i].get_text() for i in range(min(len(doc), 100)))
            doc.close()
            return text
        except Exception:
            pass
    return ""


def _show_diff(text_a, text_b, name_a, name_b):
    """Display unified diff with color coding."""
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    diff = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=name_a, tofile=name_b,
        lineterm="",
    ))

    if not diff:
        st.success("\u2705 Documents are identical (text content matches).")
        return

    # Stats
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    st.markdown(f"**Differences:** \U0001f7e2 {added} lines added, \U0001f534 {removed} lines removed")

    # Render diff lines with color
    diff_lines = []
    for line in diff[:500]:
        if line.startswith("+++") or line.startswith("---"):
            diff_lines.append(f"**{line}**")
        elif line.startswith("@@"):
            diff_lines.append(f"<span style='color:#58a6ff'>{line}</span>")
        elif line.startswith("+"):
            diff_lines.append(f"<span style='color:#3fb950;background:rgba(63,185,80,0.1)'>{line}</span>")
        elif line.startswith("-"):
            diff_lines.append(f"<span style='color:#f85149;background:rgba(248,81,73,0.1)'>{line}</span>")
        else:
            diff_lines.append(f"<span style='color:#8b949e'>{line}</span>")

    st.markdown(
        "<div style='font-family:monospace;font-size:12px;line-height:1.6;white-space:pre-wrap;'>"
        + "<br>".join(diff_lines)
        + "</div>",
        unsafe_allow_html=True,
    )

    if len(diff) > 500:
        st.caption(f"(Showing first 500 of {len(diff)} diff lines)")
