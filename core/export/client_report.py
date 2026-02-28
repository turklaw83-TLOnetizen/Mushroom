# ─── Client-Facing Report Generation ──────────────────────────────
# Generates a clean, professional HTML report suitable for sharing
# with clients. Uses plain language, no legal jargon. Printable layout.

import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_client_report_html(state, case_name):
    """
    Generates a clean, professional HTML report suitable for sharing with clients.
    Uses plain language, no legal jargon. Printable layout.
    Returns a BytesIO object containing UTF-8 HTML.
    """
    summary = state.get("case_summary", "Analysis pending.")
    strategy = state.get("strategy_notes", "")
    timeline = state.get("timeline", [])
    witnesses = state.get("witnesses", [])
    investigation = state.get("investigation_plan", [])
    client_report = state.get("client_report", "")  # Pre-generated if available

    # Timeline HTML
    timeline_html = ""
    if isinstance(timeline, list) and timeline:
        timeline_html = "<h2>Key Dates &amp; Events</h2><table><tr><th>Date</th><th>Event</th></tr>"
        for evt in timeline[:30]:
            if isinstance(evt, dict):
                date = evt.get('date', '')
                event = evt.get('event', str(evt))
                timeline_html += f"<tr><td>{date}</td><td>{event}</td></tr>"
        timeline_html += "</table>"
    elif isinstance(timeline, str) and timeline:
        timeline_html = f"<h2>Key Dates &amp; Events</h2><p>{timeline[:3000]}</p>"

    # Witnesses HTML
    witnesses_html = ""
    if isinstance(witnesses, list) and witnesses:
        witnesses_html = "<h2>Key People Involved</h2><ul>"
        for w in witnesses[:20]:
            if isinstance(w, dict):
                name = w.get('name', 'Unknown')
                role = w.get('type', w.get('role', ''))
                witnesses_html += f"<li><strong>{name}</strong> -- {role}</li>"
        witnesses_html += "</ul>"

    # Next steps
    next_steps_html = ""
    if isinstance(investigation, list) and investigation:
        next_steps_html = "<h2>Next Steps</h2><ul>"
        for task in investigation[:15]:
            if isinstance(task, dict):
                desc = task.get('task', task.get('description', str(task)))
                status = '[DONE]' if task.get('completed') else '[ ]'
                next_steps_html += f"<li>{status} {desc}</li>"
            else:
                next_steps_html += f"<li>[ ] {task}</li>"
        next_steps_html += "</ul>"

    # Strategy summary (simplified for client)
    strategy_html = ""
    if strategy:
        # Take first 1500 chars as a simplified overview
        strategy_html = f"<h2>Our Approach</h2><p>{str(strategy)[:1500]}</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Case Report -- {case_name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', sans-serif; color: #1a1a2e; background: #fff; padding: 40px; max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 1.8rem; color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: 10px; margin-bottom: 20px; }}
  h2 {{ font-size: 1.3rem; color: #0f3460; margin: 28px 0 12px; }}
  p {{ line-height: 1.7; margin-bottom: 14px; color: #333; }}
  ul {{ margin-left: 20px; margin-bottom: 16px; }}
  li {{ margin-bottom: 6px; line-height: 1.5; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 0.9rem; }}
  th {{ background: #0f3460; color: white; }}
  tr:nth-child(even) {{ background: #f8f9fa; }}
  .header {{ text-align: center; margin-bottom: 30px; }}
  .header .case-label {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px; color: #888; }}
  .header .date {{ font-size: 0.85rem; color: #888; margin-top: 5px; }}
  .confidential {{ text-align: center; color: #e74c3c; font-size: 0.8rem; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; }}
  @media print {{ body {{ padding: 20px; }} }}
</style>
</head>
<body>
<div class="header">
  <div class="case-label">Case Report</div>
  <h1>{case_name}</h1>
  <div class="date">Prepared: {datetime.now().strftime('%B %d, %Y')}</div>
</div>

<h2>Case Overview</h2>
<p>{summary[:3000] if isinstance(summary, str) else 'Analysis pending.'}</p>

{strategy_html}
{timeline_html}
{witnesses_html}
{next_steps_html}

{f'<h2>Detailed Report</h2><div>{client_report}</div>' if client_report else ''}

<div class="confidential">
  <p>CONFIDENTIAL -- ATTORNEY-CLIENT PRIVILEGED</p>
  <p>This report was prepared for client review purposes only.</p>
</div>
</body>
</html>"""

    buffer = io.BytesIO(html.encode('utf-8'))
    buffer.seek(0)
    return buffer
