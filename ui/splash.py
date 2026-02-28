# ---- Splash Screen Component ----------------------------------------------
# Branded loading splash screen with progress animation.
# Uses CSS via st.markdown and JavaScript via streamlit.components.v1.

import streamlit as st
import streamlit.components.v1 as components


def render_splash():
    """Inject the splash screen overlay and progress animation."""
    st.markdown("""
<style>
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0e1117 !important;
    }
    #splash-overlay {
        position: fixed; inset: 0; z-index: 999999;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        background: linear-gradient(135deg, #060b18 0%, #0c1225 40%, #111827 100%);
        transition: opacity 0.8s ease;
    }
    #splash-overlay.hidden { opacity: 0; pointer-events: none; }
    .splash-title {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 2rem; font-weight: 800; letter-spacing: -0.03em;
        background: linear-gradient(135deg, #6366f1, #a78bfa, #c4b5fd);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; margin-bottom: 8px;
    }
    .splash-subtitle {
        font-family: 'Inter', sans-serif; font-size: 0.9rem;
        color: #64748b; margin-bottom: 24px;
    }
    .splash-progress-wrap {
        width: 320px; height: 6px;
        background: rgba(99,102,241,0.12);
        border-radius: 3px; overflow: hidden;
        margin-bottom: 12px;
    }
    .splash-progress-bar {
        height: 100%; width: 0%;
        background: linear-gradient(90deg, #6366f1, #a78bfa);
        border-radius: 3px;
        transition: width 0.3s ease;
    }
    .splash-pct {
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.85rem; color: #a78bfa;
        margin-bottom: 6px; letter-spacing: 0.05em;
    }
    .splash-status {
        font-family: 'Inter', sans-serif; font-size: 0.78rem;
        color: #475569; margin-top: 0;
    }
</style>
<div id="splash-overlay">
    <div class="splash-title">Legal Case Prep Agent</div>
    <div class="splash-subtitle">Initializing workspace...</div>
    <div class="splash-pct" id="splash-pct">0.00%</div>
    <div class="splash-progress-wrap">
        <div class="splash-progress-bar" id="splash-bar"></div>
    </div>
    <div class="splash-status" id="splash-status">Loading core modules...</div>
</div>
""", unsafe_allow_html=True)

    # JavaScript must run via components.html (st.markdown does NOT execute <script>)
    components.html("""
<script>
(function() {
    var doc = window.parent.document;
    var retries = 0;

    function init() {
        var bar = doc.getElementById('splash-bar');
        var pct = doc.getElementById('splash-pct');
        var status = doc.getElementById('splash-status');
        var overlay = doc.getElementById('splash-overlay');

        if (!overlay) {
            retries++;
            if (retries < 60) { setTimeout(init, 50); }
            return;
        }

        var progress = 0;
        var dismissed = false;

        var phases = [
            { at: 3,  msg: 'Loading core modules...' },
            { at: 12, msg: 'Importing AI frameworks...' },
            { at: 25, msg: 'Initializing LangChain & embeddings...' },
            { at: 45, msg: 'Loading case manager...' },
            { at: 60, msg: 'Building analysis graph...' },
            { at: 75, msg: 'Preparing user interface...' },
            { at: 90, msg: 'Rendering dashboard...' },
            { at: 100, msg: 'Ready!' }
        ];

        function update(p) {
            progress = Math.min(p, 100);
            if (bar) bar.style.width = progress.toFixed(2) + '%';
            if (pct) pct.textContent = progress.toFixed(2) + '%';
            for (var i = phases.length - 1; i >= 0; i--) {
                if (progress >= phases[i].at) {
                    if (status) status.textContent = phases[i].msg;
                    break;
                }
            }
        }

        update(1);

        function dismiss() {
            if (dismissed) return;
            dismissed = true;
            update(100);
            setTimeout(function() {
                if (overlay) {
                    overlay.classList.add('hidden');
                    setTimeout(function(){ overlay.remove(); }, 900);
                }
            }, 400);
        }

        var tick = 0;
        var timer = setInterval(function() {
            tick++;
            if (dismissed) { clearInterval(timer); return; }
            if (progress < 20)       update(progress + 2.0);
            else if (progress < 50)  update(progress + 0.8);
            else if (progress < 80)  update(progress + 0.3);
            else if (progress < 95)  update(progress + 0.08);
            if (tick > 900) dismiss();
        }, 100);

        var observer = new MutationObserver(function() {
            var sidebar = doc.querySelector('[data-testid="stSidebar"]');
            var main = doc.querySelector('[data-testid="stMainBlockContainer"]');
            if (sidebar || (main && main.children.length > 2)) {
                observer.disconnect();
                clearInterval(timer);
                dismiss();
            }
        });
        observer.observe(doc.body, { childList: true, subtree: true });
    }

    init();
})();
</script>
""", height=0)
