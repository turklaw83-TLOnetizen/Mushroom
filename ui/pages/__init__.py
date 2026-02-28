# UI Page modules - one per navigation group
# Each module exposes a render() function

from ui.pages import tools_ui
from ui.pages import ethical_compliance_ui
from ui.pages import billing_ui
from ui.pages import crm_ui
from ui.pages import calendar_ui
from ui.pages import esign_ui
from ui.pages import user_admin_ui
from ui.pages import activity_ui

__all__ = [
    "tools_ui",
    "ethical_compliance_ui",
    "billing_ui",
    "crm_ui",
    "calendar_ui",
    "esign_ui",
    "user_admin_ui",
    "activity_ui",
]
