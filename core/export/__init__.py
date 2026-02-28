# ---- Export Package -------------------------------------------------------
# Re-exports all public generation functions from sub-modules.
# Uses lazy imports so the heavy docx/fpdf2 libraries only load on first use.

import importlib as _importlib


class _Lazy:
    __slots__ = ("_mod", "_name", "_real")

    def __init__(self, mod, name):
        object.__setattr__(self, "_mod", mod)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_real", None)

    def _resolve(self):
        real = object.__getattribute__(self, "_real")
        if real is None:
            mod = _importlib.import_module(object.__getattribute__(self, "_mod"))
            real = getattr(mod, object.__getattribute__(self, "_name"))
            object.__setattr__(self, "_real", real)
        return real

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)


# Word exports
generate_word_report = _Lazy("core.export.word_export", "generate_word_report")
generate_brief_outline = _Lazy("core.export.word_export", "generate_brief_outline")
generate_trial_binder = _Lazy("core.export.word_export", "generate_trial_binder")

# PDF exports
PDFReport = _Lazy("core.export.pdf_export", "PDFReport")
generate_pdf_report = _Lazy("core.export.pdf_export", "generate_pdf_report")
TrialBinderPDF = _Lazy("core.export.pdf_export", "TrialBinderPDF")
generate_trial_binder_pdf = _Lazy("core.export.pdf_export", "generate_trial_binder_pdf")

# Exhibit exports
generate_exhibit_index = _Lazy("core.export.exhibit_export", "generate_exhibit_index")
generate_exhibit_stickers = _Lazy("core.export.exhibit_export", "generate_exhibit_stickers")

# Client report
generate_client_report_html = _Lazy("core.export.client_report", "generate_client_report_html")

# Court documents
JURISDICTION_PRESETS = _Lazy("core.export.court_docs", "JURISDICTION_PRESETS")
format_court_document = _Lazy("core.export.court_docs", "format_court_document")
get_jurisdiction_list = _Lazy("core.export.court_docs", "get_jurisdiction_list")

# Quick cards
QuickCardPDF = _Lazy("core.export.quick_cards", "QuickCardPDF")
generate_quick_cards_pdf = _Lazy("core.export.quick_cards", "generate_quick_cards_pdf")

__all__ = [
    "generate_word_report", "generate_brief_outline", "generate_trial_binder",
    "PDFReport", "generate_pdf_report", "TrialBinderPDF", "generate_trial_binder_pdf",
    "generate_exhibit_index", "generate_exhibit_stickers",
    "generate_client_report_html",
    "JURISDICTION_PRESETS", "format_court_document", "get_jurisdiction_list",
    "QuickCardPDF", "generate_quick_cards_pdf",
]
