"""
doc_viewer_ui.py -- In-App Document Viewer
Renders PDFs page-by-page using PyMuPDF (fitz), images inline, and text files.
Includes page navigation, zoom, and OCR text overlay.
"""

import logging
import os
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)


def render(case_id, case_mgr, model_provider=None, **kwargs):
    """Render the document viewer for a case."""
    file_path = st.session_state.get("_viewing_file")

    if not file_path or not os.path.exists(file_path):
        st.info("Select a file to view from the Case Library.")
        # Show file list for quick selection
        files = case_mgr.get_case_files(case_id) or []
        if files:
            st.markdown("#### Available Files")
            for fp in files:
                fname = os.path.basename(fp)
                if st.button(f"\U0001f4c4 {fname}", key=f"_dv_open_{fname}"):
                    st.session_state["_viewing_file"] = fp
                    st.rerun()
        return

    fname = os.path.basename(file_path)
    ext = os.path.splitext(fname)[1].lower()

    # Header with file name and close button
    _hdr_col1, _hdr_col2 = st.columns([5, 1])
    with _hdr_col1:
        st.markdown(f"### \U0001f4c4 {fname}")
    with _hdr_col2:
        if st.button("\u2716 Close", key="_dv_close"):
            st.session_state.pop("_viewing_file", None)
            st.rerun()

    # --- PDF Viewer ---
    if ext == ".pdf":
        _render_pdf(file_path, fname, case_id)

    # --- Image Viewer ---
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"):
        _render_image(file_path, fname)

    # --- Text / Code Viewer ---
    elif ext in (".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"):
        _render_text(file_path, fname, ext)

    # --- Spreadsheet ---
    elif ext in (".xlsx", ".xls"):
        _render_spreadsheet(file_path, fname)

    # --- Unsupported ---
    else:
        st.warning(f"No inline viewer for `{ext}` files. Use the download button below.")
        with open(file_path, "rb") as f:
            st.download_button(
                f"\U0001f4e5 Download {fname}",
                data=f.read(),
                file_name=fname,
                key="_dv_download",
            )


def _render_pdf(file_path, fname, case_id):
    """Render a PDF page-by-page with navigation and optional OCR overlay."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        st.error("PyMuPDF (fitz) is required for PDF viewing. Install with: `pip install pymupdf`")
        return

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        st.error(f"Could not open PDF: {e}")
        return

    total_pages = len(doc)
    if total_pages == 0:
        st.warning("This PDF has no pages.")
        doc.close()
        return

    # Navigation controls
    _nav_col1, _nav_col2, _nav_col3, _nav_col4 = st.columns([1, 2, 1, 2])

    _page_key = f"_dv_page_{fname}"
    current_page = st.session_state.get(_page_key, 0)

    with _nav_col1:
        if st.button("\u25c0 Prev", key="_dv_prev", disabled=current_page <= 0):
            st.session_state[_page_key] = max(0, current_page - 1)
            st.rerun()
    with _nav_col2:
        page_num = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=current_page + 1,
            key="_dv_page_input",
            label_visibility="collapsed",
        )
        if page_num - 1 != current_page:
            st.session_state[_page_key] = page_num - 1
            st.rerun()
    with _nav_col3:
        if st.button("Next \u25b6", key="_dv_next", disabled=current_page >= total_pages - 1):
            st.session_state[_page_key] = min(total_pages - 1, current_page + 1)
            st.rerun()
    with _nav_col4:
        st.caption(f"Page {current_page + 1} of {total_pages}")

    # Zoom control
    _zoom_options = {"75%": 1.0, "100%": 1.33, "125%": 1.67, "150%": 2.0, "200%": 2.67}
    _zoom_key = f"_dv_zoom_{fname}"
    _zoom_label = st.session_state.get(_zoom_key, "100%")
    _zoom_col1, _zoom_col2 = st.columns([1, 5])
    with _zoom_col1:
        _zoom_label = st.selectbox(
            "Zoom",
            list(_zoom_options.keys()),
            index=list(_zoom_options.keys()).index(_zoom_label) if _zoom_label in _zoom_options else 1,
            key="_dv_zoom_sel",
            label_visibility="collapsed",
        )
        st.session_state[_zoom_key] = _zoom_label

    _dpi_factor = _zoom_options.get(_zoom_label, 1.33)

    # Render page
    try:
        page = doc[current_page]
        pix = page.get_pixmap(dpi=int(72 * _dpi_factor))
        img_bytes = pix.tobytes("png")
        st.image(img_bytes, use_container_width=True)
    except Exception as e:
        st.error(f"Error rendering page {current_page + 1}: {e}")

    # OCR text overlay
    _show_ocr = st.checkbox("Show OCR / extracted text", key="_dv_show_ocr", value=False)
    if _show_ocr:
        try:
            from core.ingest import OCRCache
            _data_cases = str(Path(__file__).resolve().parent.parent.parent / "data" / "cases")
            _ocr_cache = OCRCache(os.path.join(_data_cases, case_id))
            fsize = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            _fkey = f"{fname}:{fsize}"

            # Try page-level text first
            _page_text = _ocr_cache.get_page_text(_fkey, current_page)
            if _page_text:
                with st.expander(f"OCR Text -- Page {current_page + 1}", expanded=True):
                    st.text(_page_text)
            else:
                # Fall back to full text
                _full_text = _ocr_cache.get_text(_fkey)
                if _full_text:
                    with st.expander("Full OCR Text", expanded=False):
                        st.text(_full_text[:5000])
                        if len(_full_text) > 5000:
                            st.caption("(Showing first 5,000 characters)")
                else:
                    st.caption("No OCR text available for this file.")
        except Exception as e:
            st.caption(f"OCR text not available: {e}")

    doc.close()

    # --- Annotations Panel ---
    _render_annotations(case_id, fname, current_page)


def _render_annotations(case_id, fname, current_page):
    """Render annotation panel for the current page."""
    try:
        from core.annotations import (
            add_annotation, load_annotations, delete_annotation,
            count_annotations_by_page, ANNOTATION_COLORS,
        )
        from ui.shared import PROJECT_ROOT
        import streamlit as st

        _data_dir = str(PROJECT_ROOT / "data")

        # Annotation counts badge
        _ann_counts = count_annotations_by_page(_data_dir, case_id, fname)
        _page_ann_count = _ann_counts.get(current_page, 0)
        _total_ann_count = sum(_ann_counts.values())

        _ann_label = f"\U0001f4dd Annotations ({_page_ann_count} on this page, {_total_ann_count} total)"
        with st.expander(_ann_label, expanded=False):
            # Existing annotations for this page
            _page_annotations = load_annotations(_data_dir, case_id, fname, page=current_page)

            if _page_annotations:
                for _ann in _page_annotations:
                    _ann_id = _ann.get("id", "")
                    _ann_color = _ann.get("color", "yellow")
                    _ann_text = _ann.get("text", "")
                    _ann_note = _ann.get("note", "")
                    _ann_user = _ann.get("user_name", "")
                    _ann_time = _ann.get("created_at", "")[:16]
                    _color_hex = {
                        "yellow": "#f59e0b", "green": "#22c55e",
                        "blue": "#3b82f6", "red": "#ef4444", "purple": "#a855f7",
                    }.get(_ann_color, "#f59e0b")

                    st.markdown(
                        f"<div style='border-left:3px solid {_color_hex};padding:4px 8px;"
                        f"margin:4px 0;background:rgba(0,0,0,0.1);border-radius:4px;'>"
                        f"<strong style='color:{_color_hex};'>{_ann_note}</strong>"
                        f"{'<br/><span style=\"opacity:0.7;font-size:0.85em;\">' + _ann_text + '</span>' if _ann_text else ''}"
                        f"<br/><span style='opacity:0.5;font-size:0.75em;'>{_ann_user} \u00b7 {_ann_time}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("\U0001f5d1\ufe0f", key=f"_del_ann_{_ann_id}", help="Delete annotation"):
                        delete_annotation(_data_dir, case_id, fname, _ann_id)
                        st.rerun()
            else:
                st.caption("No annotations on this page yet.")

            # Add new annotation form
            st.markdown("---")
            st.markdown("**Add Annotation**")
            _new_ann_text = st.text_input(
                "Text excerpt (optional)",
                key=f"_ann_text_{current_page}",
                placeholder="Highlight text from the document...",
            )
            _new_ann_note = st.text_area(
                "Note",
                key=f"_ann_note_{current_page}",
                placeholder="Your annotation or comment...",
                height=80,
            )
            _ann_col1, _ann_col2 = st.columns([1, 1])
            with _ann_col1:
                _new_ann_color = st.selectbox(
                    "Color",
                    ANNOTATION_COLORS,
                    key=f"_ann_color_{current_page}",
                )
            with _ann_col2:
                if st.button("Add Annotation", key=f"_add_ann_{current_page}", type="primary"):
                    if _new_ann_note.strip():
                        _user = st.session_state.get("current_user", {})
                        add_annotation(
                            data_dir=_data_dir,
                            case_id=case_id,
                            filename=fname,
                            page=current_page,
                            text=_new_ann_text.strip(),
                            note=_new_ann_note.strip(),
                            color=_new_ann_color,
                            user_id=_user.get("id", "") if _user else "",
                            user_name=_user.get("name", "") if _user else "",
                        )
                        st.toast("\U0001f4dd Annotation added!")
                        st.rerun()
                    else:
                        st.warning("Please enter a note.")
    except Exception as _ann_exc:
        st.caption(f"Annotations unavailable: {_ann_exc}")


def _render_image(file_path, fname):
    """Render an image file."""
    st.image(file_path, use_container_width=True)
    st.caption(f"{fname}")


def _render_text(file_path, fname, ext):
    """Render a text-based file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    _lang_map = {
        ".json": "json", ".xml": "xml", ".html": "html", ".htm": "html",
        ".csv": "csv", ".md": "markdown", ".py": "python",
    }
    lang = _lang_map.get(ext, "text")

    st.code(content[:50000], language=lang)
    if len(content) > 50000:
        st.caption(f"(Showing first 50,000 of {len(content):,} characters)")


def _render_spreadsheet(file_path, fname):
    """Render a spreadsheet with pandas."""
    try:
        import pandas as pd
        if fname.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        st.dataframe(df, use_container_width=True)
        st.caption(f"{len(df)} rows x {len(df.columns)} columns")
    except ImportError:
        st.warning("Install pandas and openpyxl for spreadsheet viewing.")
    except Exception as e:
        st.error(f"Could not read spreadsheet: {e}")
