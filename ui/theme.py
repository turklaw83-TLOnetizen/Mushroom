# --- Theme CSS Module ---
# Extracted from app.py - single source of truth for all Streamlit CSS.
# Three themes: dark, grey (slate), light.

def get_theme_css(theme):
    # Shared styles across all themes
    shared = """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        /* ── Anti-Flicker / Hiding Streamlit Loading Artifacts ── */
        /* Force all containers visible at all times — prevents white flash on rerun */
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > section,
        [data-testid="stAppViewContainer"] > section > div,
        [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewBlockContainer"],
        .stApp {
            opacity: 1 !important;
            visibility: visible !important;
            transition: none !important;
            filter: none !important;
            background: var(--bg-primary) !important;
            will-change: auto !important;
        }

        /* Kill ALL transitions during Streamlit reruns to prevent flicker */
        [data-testid="stAppViewContainer"] *,
        .stApp * {
            transition-duration: 0s !important;
            transition-delay: 0s !important;
        }

        /* Prevent Streamlit from dimming "stale" elements during auto-refresh */
        div[style*="opacity: 0."],
        div[style*="opacity:0."],
        [data-stale="true"],
        .stale {
            opacity: 1 !important;
            filter: none !important;
            visibility: visible !important;
        }

        /* Hide Streamlit chrome: header, toolbar, running indicators */
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
        .st-emotion-cache-16txtl3 { display: none !important; }
        .st-emotion-cache-1kyxreq { display: none !important; }
        /* Hide Streamlit's skeleton placeholders during reruns */
        [data-testid="stSkeleton"] { display: none !important; }
        .stSpinner { display: none !important; }

        /* ── Keyframe Animations ─────────────────────────── */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
            0%   { background-position: -200% center; }
            100% { background-position: 200% center; }
        }
        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 8px var(--accent-glow); }
            50%      { box-shadow: 0 0 20px var(--accent-glow); }
        }
        @keyframes gradientShift {
            0%   { background-position: 0% 50%; }
            50%  { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        @keyframes floatIn {
            from { opacity: 0; transform: translateY(8px) scale(0.98); }
            to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes borderGlow {
            0%, 100% { border-color: var(--accent-dim); }
            50%      { border-color: var(--accent-bright); }
        }

        /* ── Base Typography & App ───────────────────────── */
        .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            transition: background-color 0.4s ease, color 0.3s ease;
        }
        h1, h2, h3, h4 {
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            letter-spacing: -0.03em;
        }
        h1 { font-size: 2rem !important; }

        /* ── Glassmorphic Cards & Containers ─────────────── */
        [data-testid="stExpander"], .stForm {
            border-radius: 16px !important;
            backdrop-filter: blur(16px) saturate(1.4);
            -webkit-backdrop-filter: blur(16px) saturate(1.4);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            animation: floatIn 0.4s ease-out;
        }
        [data-testid="stExpander"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 32px var(--card-hover-shadow);
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            border-radius: 12px !important;
            transition: all 0.25s ease;
        }

        /* ── Buttons — Premium with Glow ─────────────────── */
        .stButton>button {
            border-radius: 10px;
            font-weight: 600;
            font-size: 13px;
            padding: 0.45rem 1.1rem;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid transparent;
            letter-spacing: 0.01em;
            position: relative;
            overflow: hidden;
        }
        .stButton>button:hover {
            transform: translateY(-2px) scale(1.01);
        }
        .stButton>button:active {
            transform: translateY(0px) scale(0.99);
            transition: transform 0.1s ease;
        }

        /* ── Tabs — Pill Style ───────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            flex-wrap: wrap;
            padding: 4px;
            border-radius: 14px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 36px;
            white-space: nowrap;
            border-radius: 10px !important;
            padding: 0 16px;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid transparent;
        }

        /* ── Metrics — Premium ───────────────────────────── */
        div[data-testid="stMetricValue"] {
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        div[data-testid="stMetricLabel"] {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.08em;
            opacity: 0.7;
        }
        div[data-testid="stMetric"] {
            animation: floatIn 0.5s ease-out both;
        }
        div[data-testid="stMetric"]:nth-child(1) { animation-delay: 0s; }
        div[data-testid="stMetric"]:nth-child(2) { animation-delay: 0.05s; }
        div[data-testid="stMetric"]:nth-child(3) { animation-delay: 0.1s; }
        div[data-testid="stMetric"]:nth-child(4) { animation-delay: 0.15s; }
        div[data-testid="stMetric"]:nth-child(5) { animation-delay: 0.2s; }

        /* ── Progress Bar — Gradient Animated + Candy Stripes ── */
        @keyframes progressStripe {
            0%   { background-position: 0 0; }
            100% { background-position: 40px 0; }
        }
        .stProgress > div > div {
            border-radius: 10px;
            background: linear-gradient(90deg, var(--accent-start), var(--accent-end), var(--accent-start)) !important;
            background-size: 200% 100% !important;
            animation: gradientShift 3s ease infinite;
            position: relative;
            overflow: hidden;
        }
        .stProgress > div > div::after {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: repeating-linear-gradient(
                -45deg,
                transparent,
                transparent 8px,
                rgba(255,255,255,0.08) 8px,
                rgba(255,255,255,0.08) 16px
            );
            animation: progressStripe 0.8s linear infinite;
            border-radius: 10px;
        }

        /* ── Sidebar — Frosted Glass ─────────────────────── */
        [data-testid="stSidebar"] {
            backdrop-filter: blur(20px) saturate(1.5);
            -webkit-backdrop-filter: blur(20px) saturate(1.5);
            transition: all 0.4s ease;
        }

        /* ── Scrollbar — Sleek ───────────────────────────── */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { border-radius: 6px; }

        /* ── Custom Component Classes ────────────────────── */
        .hero-title {
            font-size: 2.4rem !important;
            font-weight: 800 !important;
            letter-spacing: -0.04em;
            background: linear-gradient(135deg, var(--accent-start), var(--accent-end), var(--accent-bright));
            background-size: 200% 200%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: gradientShift 4s ease 1 forwards;
            margin-bottom: 0 !important;
            line-height: 1.1 !important;
        }
        .hero-subtitle {
            font-size: 1.05rem;
            font-weight: 400;
            opacity: 0.65;
            margin-top: 4px;
            letter-spacing: 0.02em;
        }
        .hero-divider {
            height: 3px;
            background: linear-gradient(90deg, var(--accent-start), var(--accent-end), transparent);
            border: none;
            border-radius: 3px;
            margin: 12px 0 20px 0;
            /* static gradient — no animation */
            background-size: 200% 100%;
        }
        .glass-stat-card {
            backdrop-filter: blur(16px) saturate(1.5);
            -webkit-backdrop-filter: blur(16px) saturate(1.5);
            border-radius: 16px;
            padding: 20px 24px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            animation: floatIn 0.5s ease-out both;
            position: relative;
            overflow: hidden;
        }
        .glass-stat-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 4px; height: 100%;
            background: linear-gradient(180deg, var(--accent-start), var(--accent-end));
            border-radius: 4px 0 0 4px;
        }
        .glass-stat-card:hover {
            transform: translateY(-3px) scale(1.01);
            box-shadow: 0 12px 40px var(--card-hover-shadow);
            border-color: var(--accent-dim);
        }
        .glass-stat-card .stat-value {
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1;
            margin: 4px 0;
        }
        .glass-stat-card .stat-label {
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            opacity: 0.6;
        }
        .glass-stat-card .stat-icon {
            font-size: 1.3rem;
            margin-bottom: 4px;
        }
        .case-card-premium {
            backdrop-filter: blur(12px) saturate(1.3);
            -webkit-backdrop-filter: blur(12px) saturate(1.3);
            border-radius: 14px;
            padding: 16px 20px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            animation: floatIn 0.4s ease-out both;
            margin-bottom: 8px;
            border-left: 3px solid var(--accent-start);
        }
        .case-card-premium:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 32px var(--card-hover-shadow);
            border-left-color: var(--accent-bright);
        }
        .pill-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .pill-badge-accent {
            background: linear-gradient(135deg, var(--accent-start), var(--accent-end));
            color: #fff;
        }
        .pill-badge-success { background: rgba(34,197,94,0.15); color: #22c55e; }
        .pill-badge-warning { background: rgba(234,179,8,0.15); color: #eab308; }
        .pill-badge-danger  { background: rgba(239,68,68,0.15); color: #ef4444; }
        .pill-badge-neutral { background: rgba(148,163,184,0.15); color: #94a3b8; }
        .gauge-container {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .gauge-ring {
            position: relative;
            width: 72px; height: 72px;
        }
        .gauge-ring svg { transform: rotate(-90deg); }
        .gauge-ring .gauge-value {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            font-weight: 800;
            letter-spacing: -0.03em;
        }
        .sidebar-brand {
            text-align: center;
            padding: 8px 0 16px 0;
        }
        .sidebar-brand .brand-name {
            font-size: 1.2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg, var(--accent-start), var(--accent-end));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .sidebar-brand .brand-version {
            font-size: 10px;
            font-weight: 500;
            opacity: 0.5;
            margin-top: 2px;
        }
        .cost-card {
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 12px;
            padding: 12px 16px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
        }

        /* ═══════════════ 1. CASE CARD REDESIGN ═══════════════ */
        .case-card-v2 {
            backdrop-filter: blur(14px) saturate(1.4);
            -webkit-backdrop-filter: blur(14px) saturate(1.4);
            border-radius: 14px;
            padding: 18px 22px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            animation: floatIn 0.4s ease-out both;
            position: relative;
            overflow: hidden;
            cursor: pointer;
        }
        .case-card-v2::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 4px; height: 100%;
            background: linear-gradient(180deg, var(--accent-start), var(--accent-end));
            border-radius: 4px 0 0 4px;
            opacity: 0.7;
            transition: opacity 0.3s ease;
        }
        .case-card-v2:hover {
            transform: translateY(-3px) scale(1.005);
            box-shadow: 0 12px 40px var(--card-hover-shadow);
            border-color: var(--accent-dim);
        }
        .case-card-v2:hover::before { opacity: 1; }
        .case-card-v2 .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .case-card-v2 .card-title {
            font-size: 15px;
            font-weight: 700;
            letter-spacing: -0.01em;
        }
        .case-card-v2 .card-meta {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
            font-size: 11px;
            opacity: 0.6;
        }
        .case-card-v2 .card-badges {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-top: 8px;
        }
        .mini-progress-ring {
            position: relative;
            width: 28px; height: 28px;
            display: inline-flex;
            vertical-align: middle;
        }
        .mini-progress-ring svg { transform: rotate(-90deg); }
        .mini-progress-ring .ring-label {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-size: 8px;
            font-weight: 700;
        }

        /* ═══════════════ 2. TAB CONTENT TRANSITIONS ═══════════════ */
        @keyframes tabFadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .stTabs [data-baseweb="tab-panel"] {
            animation: tabFadeIn 0.35s ease-out;
        }

        /* ═══════════════ 3. ANALYSIS BUTTON REDESIGN ═══════════════ */
        .analysis-btn-wrap {
            position: relative;
            overflow: hidden;
            border-radius: 12px;
        }
        .analysis-btn-wrap .stButton>button[kind="primary"] {
            font-size: 15px !important;
            font-weight: 700 !important;
            padding: 14px 24px !important;
            border-radius: 12px !important;
            letter-spacing: 0.01em;
            position: relative;
            overflow: hidden;
        }
        .analysis-btn-wrap .stButton>button[kind="primary"]::after {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
            animation: shimmer 2.5s ease 1 forwards;
        }

        /* ═══════════════ 4. SKELETON LOADING ═══════════════ */
        @keyframes skeletonPulse {
            0%   { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
        .skeleton-card {
            border-radius: 14px;
            padding: 20px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
            animation: floatIn 0.4s ease-out both;
        }
        .skeleton-line {
            height: 12px;
            border-radius: 6px;
            margin: 10px 0;
            background: linear-gradient(90deg,
                var(--glass-border) 25%,
                var(--accent-dim) 50%,
                var(--glass-border) 75%
            );
            background-size: 200% 100%;
            animation: skeletonPulse 1.5s ease-in-out infinite;
        }
        .skeleton-line.short { width: 40%; }
        .skeleton-line.medium { width: 65%; }
        .skeleton-line.long { width: 90%; }
        .skeleton-circle {
            width: 48px; height: 48px;
            border-radius: 50%;
            background: linear-gradient(90deg,
                var(--glass-border) 25%,
                var(--accent-dim) 50%,
                var(--glass-border) 75%
            );
            background-size: 200% 100%;
            animation: skeletonPulse 1.5s ease-in-out infinite;
        }

        /* ═══════════════ 5. TOAST NOTIFICATIONS ═══════════════ */
        @keyframes toastSlideIn {
            from { transform: translateX(100%); opacity: 0; }
            to   { transform: translateX(0); opacity: 1; }
        }
        [data-testid="stToast"] {
            backdrop-filter: blur(16px) saturate(1.5) !important;
            -webkit-backdrop-filter: blur(16px) saturate(1.5) !important;
            border-radius: 12px !important;
            border: 1px solid var(--glass-border) !important;
            background: var(--surface-raised) !important;
            box-shadow: 0 12px 40px rgba(0,0,0,0.2) !important;
            animation: toastSlideIn 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94) !important;
        }

        /* ═══════════════ 6. EMPTY STATE STYLING ═══════════════ */
        @keyframes emptyPulse {
            0%, 100% { transform: scale(1); opacity: 0.7; }
            50%      { transform: scale(1.08); opacity: 1; }
        }
        .empty-state {
            text-align: center;
            padding: 40px 24px;
            border-radius: 16px;
            border: 2px dashed var(--glass-border);
            background: var(--glass-bg);
            animation: floatIn 0.5s ease-out both;
        }
        .empty-state .empty-icon {
            font-size: 3rem;
            margin-bottom: 12px;
            /* no pulse animation — static */
        }
        .empty-state .empty-title {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .empty-state .empty-subtitle {
            font-size: 12px;
            opacity: 0.55;
            max-width: 280px;
            margin: 0 auto;
            line-height: 1.5;
        }

        /* ═══════════════ 7. RESPONSIVE LAYOUT ═══════════════ */

        /* Tab overflow — horizontal scroll for groups with many tabs */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            overflow-y: hidden;
            scrollbar-width: thin;
            -webkit-overflow-scrolling: touch;
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { height: 3px; }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
            background: var(--accent-dim);
            border-radius: 3px;
        }

        /* Mobile breakpoints */
        @media (max-width: 768px) {
            [data-testid="stSidebar"] { min-width: 220px !important; max-width: 260px !important; }
            h1 { font-size: 1.5rem !important; }
            .hero-title { font-size: 1.6rem !important; }
            .glass-stat-card { padding: 14px 16px; }
            .glass-stat-card .stat-value { font-size: 1.4rem; }
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
            }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width: 100% !important;
                flex: 1 1 100% !important;
            }
        }
        @media (max-width: 480px) {
            .stTabs [data-baseweb="tab"] { font-size: 11px; padding: 0 10px; height: 32px; }
        }

        /* ═══════════════ 8. UPLOAD DROP ZONE ═══════════════ */
        .upload-zone {
            border: 2px dashed var(--accent-dim);
            border-radius: 16px;
            padding: 28px 24px;
            text-align: center;
            transition: all 0.3s ease;
            background: var(--glass-bg);
            position: relative;
        }
        .upload-zone:hover {
            border-color: var(--accent-bright);
            background: rgba(99,102,241,0.04);
            transform: scale(1.005);
        }
        .upload-zone .drop-icon {
            font-size: 2.2rem;
            margin-bottom: 8px;
            /* no pulse animation — static */
        }
        .upload-zone .drop-label {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .upload-zone .drop-hint {
            font-size: 11px;
            opacity: 0.5;
        }
        .upload-zone .file-types {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 12px;
            flex-wrap: wrap;
        }
        .upload-zone .file-type-chip {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 500;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
        }

        /* ═══════════════ 9. DASHBOARD COMPONENTS ═══════════════ */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin: 12px 0;
        }
        .module-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .module-pill.done {
            background: rgba(34,197,94,0.12);
            color: #22c55e;
            border: 1px solid rgba(34,197,94,0.2);
        }
        .module-pill.empty {
            background: rgba(148,163,184,0.08);
            color: #94a3b8;
            border: 1px solid rgba(148,163,184,0.15);
        }
        .module-pill.stale {
            background: rgba(234,179,8,0.12);
            color: #eab308;
            border: 1px solid rgba(234,179,8,0.2);
        }

        /* ═══════════════ 10. NOTIFICATION BANNERS ═══════════════ */
        .notif-banner {
            border-radius: 12px;
            padding: 12px 18px;
            margin: 8px 0;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 13px;
            font-weight: 500;
            animation: floatIn 0.4s ease-out both;
        }
        .notif-banner.warning {
            background: rgba(234,179,8,0.08);
            border: 1px solid rgba(234,179,8,0.2);
            color: #eab308;
        }
        .notif-banner.danger {
            background: rgba(239,68,68,0.08);
            border: 1px solid rgba(239,68,68,0.2);
            color: #ef4444;
        }
        .notif-banner.info {
            background: rgba(99,102,241,0.08);
            border: 1px solid rgba(99,102,241,0.2);
            color: #818cf8;
        }
        .notif-banner .notif-icon { font-size: 1.2rem; }

        /* ═══════════════ 11. PRINT RULES ═══════════════ */
        @media print {
            [data-testid="stSidebar"] { display: none !important; }
            .stButton, .stDownloadButton { display: none !important; }
            .stSpinner, .stProgress { display: none !important; }
            [data-testid="stToast"] { display: none !important; }
            .stTabs [data-baseweb="tab-list"] { display: none !important; }
            header[data-testid="stHeader"] { display: none !important; }
            .stApp { background: white !important; color: black !important; }
            h1, h2, h3, h4 { color: black !important; -webkit-text-fill-color: black !important; }
            p, li, span, .stMarkdown { color: #333 !important; }
            [data-testid="stExpander"] {
                border: 1px solid #ddd !important;
                background: white !important;
                backdrop-filter: none !important;
            }
        }
    """

    if theme == "dark":
        return f"<style>{shared}" + """
            /* ── CSS Variables — Dark ────────────────────── */
            :root {
                --accent-start: #6366f1;
                --accent-end: #a78bfa;
                --accent-bright: #c4b5fd;
                --accent-dim: rgba(99,102,241,0.3);
                --accent-glow: rgba(99,102,241,0.4);
                --glass-bg: rgba(17,24,39,0.6);
                --glass-border: rgba(148,163,184,0.08);
                --card-hover-shadow: rgba(99,102,241,0.15);
                --text-primary: #f1f5f9;
                --text-secondary: #94a3b8;
                --text-muted: #64748b;
                --surface: #111827;
                --surface-raised: rgba(26,32,53,0.8);
            }
            .stApp { background: linear-gradient(135deg, #060b18 0%, #0c1225 40%, #111827 100%); }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(17,24,39,0.95) 0%, rgba(6,11,24,0.98) 100%) !important;
                border-right: 1px solid rgba(99,102,241,0.1);
            }
            h1, h2, h3, h4 { color: #f1f5f9; }
            p, li, span, label, .stMarkdown { color: #94a3b8; }
            [data-testid="stExpander"], .stForm {
                background: rgba(26,32,53,0.6) !important;
                border: 1px solid rgba(148,163,184,0.08) !important;
                box-shadow: 0 4px 24px rgba(0,0,0,0.2);
            }
            [data-testid="stExpander"]:hover {
                border-color: rgba(99,102,241,0.2) !important;
                box-shadow: 0 8px 32px rgba(99,102,241,0.1);
            }
            /* Primary buttons — indigo glow */
            .stButton>button[kind="primary"] {
                background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
                color: #ffffff;
                box-shadow: 0 2px 12px rgba(99,102,241,0.3);
            }
            .stButton>button[kind="primary"]:hover {
                background: linear-gradient(135deg, #818cf8 0%, #a5b4fc 100%);
                box-shadow: 0 6px 28px rgba(99,102,241,0.45);
            }
            /* Secondary buttons */
            .stButton>button {
                background: rgba(26,32,53,0.7);
                color: #94a3b8;
                border: 1px solid rgba(148,163,184,0.1);
            }
            .stButton>button:hover {
                background: rgba(31,40,71,0.8);
                color: #f1f5f9;
                border-color: rgba(99,102,241,0.3);
                box-shadow: 0 4px 20px rgba(99,102,241,0.15);
            }
            /* Tabs — pill with glow */
            .stTabs [data-baseweb="tab-list"] {
                background: rgba(17,24,39,0.5);
            }
            .stTabs [data-baseweb="tab"] {
                background: transparent;
                color: #64748b;
            }
            .stTabs [data-baseweb="tab"]:hover {
                color: #94a3b8;
                background: rgba(99,102,241,0.08);
            }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #6366f1, #818cf8) !important;
                color: #ffffff !important;
                font-weight: 600;
                box-shadow: 0 2px 16px rgba(99,102,241,0.35);
            }
            /* Metrics */
            div[data-testid="stMetricValue"] { color: #f1f5f9; }
            div[data-testid="stMetricLabel"] { color: #64748b; }
            /* Inputs — dark glass */
            .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div {
                background: rgba(17,24,39,0.8) !important;
                border-color: rgba(148,163,184,0.1) !important;
                color: #f1f5f9 !important;
                border-radius: 10px !important;
            }
            .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
                border-color: rgba(99,102,241,0.5) !important;
                box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
            }
            .stTextInput>div>div>input::placeholder, .stTextArea>div>div>textarea::placeholder {
                color: #64748b !important;
                opacity: 1 !important;
            }
            /* Scrollbar — indigo tint */
            ::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.25); }
            ::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.4); }
            /* Container borders */
            [data-testid="stVerticalBlockBorderWrapper"] > div {
                border-color: rgba(148,163,184,0.08) !important;
            }
            /* Code / Citations */
            code {
                background-color: rgba(99,102,241,0.12);
                color: #a5b4fc;
                padding: 2px 8px;
                border-radius: 6px;
                font-size: 0.8em;
            }
            .stAlert [data-testid="stMarkdownContainer"] { color: #f1f5f9; }
            /* Custom stat card text */
            .glass-stat-card .stat-value { color: #f1f5f9; }
            .glass-stat-card .stat-label { color: #64748b; }
            .gauge-ring .gauge-value { color: #f1f5f9; }
        </style>"""

    elif theme == "grey":
        return f"<style>{shared}" + """
            /* ── CSS Variables — Slate ───────────────────── */
            :root {
                --accent-start: #2dd4bf;
                --accent-end: #14b8a6;
                --accent-bright: #5eead4;
                --accent-dim: rgba(45,212,191,0.3);
                --accent-glow: rgba(45,212,191,0.4);
                --glass-bg: rgba(49,51,56,0.6);
                --glass-border: rgba(63,65,71,0.6);
                --card-hover-shadow: rgba(45,212,191,0.1);
                --text-primary: #f2f3f5;
                --text-secondary: #dbdee1;
                --text-muted: #949ba4;
                --surface: #313338;
                --surface-raised: rgba(56,58,64,0.8);
            }
            .stApp { background: linear-gradient(135deg, #232529 0%, #2b2d31 40%, #313338 100%); }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(49,51,56,0.95) 0%, rgba(35,37,41,0.98) 100%) !important;
                border-right: 1px solid rgba(45,212,191,0.1);
            }
            h1, h2, h3, h4 { color: #f2f3f5; }
            p, li, span, label, .stMarkdown { color: #dbdee1; }
            [data-testid="stExpander"], .stForm {
                background: rgba(49,51,56,0.6) !important;
                border: 1px solid rgba(63,65,71,0.6) !important;
                box-shadow: 0 4px 24px rgba(0,0,0,0.15);
            }
            [data-testid="stExpander"]:hover {
                border-color: rgba(45,212,191,0.2) !important;
                box-shadow: 0 8px 32px rgba(45,212,191,0.08);
            }
            .stButton>button[kind="primary"] {
                background: linear-gradient(135deg, #14b8a6 0%, #2dd4bf 100%);
                color: #ffffff;
                box-shadow: 0 2px 12px rgba(45,212,191,0.3);
            }
            .stButton>button[kind="primary"]:hover {
                background: linear-gradient(135deg, #2dd4bf 0%, #5eead4 100%);
                box-shadow: 0 6px 28px rgba(45,212,191,0.4);
            }
            .stButton>button {
                background: rgba(56,58,64,0.7);
                color: #dbdee1;
                border: 1px solid rgba(78,80,88,0.6);
            }
            .stButton>button:hover {
                background: rgba(78,80,88,0.8);
                color: #f2f3f5;
                border-color: rgba(45,212,191,0.3);
                box-shadow: 0 4px 20px rgba(45,212,191,0.12);
            }
            .stTabs [data-baseweb="tab-list"] { background: rgba(43,45,49,0.5); }
            .stTabs [data-baseweb="tab"] { background: transparent; color: #949ba4; }
            .stTabs [data-baseweb="tab"]:hover { color: #dbdee1; background: rgba(45,212,191,0.08); }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #14b8a6, #2dd4bf) !important;
                color: #ffffff !important;
                font-weight: 600;
                box-shadow: 0 2px 16px rgba(45,212,191,0.3);
            }
            div[data-testid="stMetricValue"] { color: #f2f3f5; }
            div[data-testid="stMetricLabel"] { color: #949ba4; }
            .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div {
                background: rgba(30,31,34,0.8) !important;
                border-color: rgba(78,80,88,0.5) !important;
                color: #dbdee1 !important;
                border-radius: 10px !important;
            }
            .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
                border-color: rgba(45,212,191,0.5) !important;
                box-shadow: 0 0 0 3px rgba(45,212,191,0.12) !important;
            }
            .stTextInput>div>div>input::placeholder, .stTextArea>div>div>textarea::placeholder {
                color: #949ba4 !important;
                opacity: 1 !important;
            }
            ::-webkit-scrollbar-thumb { background: rgba(45,212,191,0.2); }
            ::-webkit-scrollbar-thumb:hover { background: rgba(45,212,191,0.35); }
            [data-testid="stVerticalBlockBorderWrapper"] > div { border-color: rgba(63,65,71,0.5) !important; }
            .glass-stat-card .stat-value { color: #f2f3f5; }
            .glass-stat-card .stat-label { color: #949ba4; }
            .gauge-ring .gauge-value { color: #f2f3f5; }
        </style>"""

    else:  # light
        return f"<style>{shared}" + """
            /* ── CSS Variables — Light ───────────────────── */
            :root {
                --accent-start: #059669;
                --accent-end: #10b981;
                --accent-bright: #34d399;
                --accent-dim: rgba(5,150,105,0.2);
                --accent-glow: rgba(5,150,105,0.25);
                --glass-bg: rgba(255,255,255,0.7);
                --glass-border: rgba(0,0,0,0.06);
                --card-hover-shadow: rgba(5,150,105,0.1);
                --text-primary: #1f2328;
                --text-secondary: #424a53;
                --text-muted: #656d76;
                --surface: #f6f8fa;
                --surface-raised: rgba(255,255,255,0.9);
            }
            .stApp { background: linear-gradient(135deg, #f8fafc 0%, #ffffff 40%, #f0fdf4 100%); }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(246,248,250,0.97) 0%, rgba(255,255,255,0.99) 100%) !important;
                border-right: 1px solid rgba(5,150,105,0.1);
            }
            h1, h2, h3, h4 { color: #1f2328; }
            p, li, span, label, .stMarkdown { color: #424a53; }
            [data-testid="stExpander"], .stForm {
                background: rgba(255,255,255,0.7) !important;
                border: 1px solid rgba(0,0,0,0.06) !important;
                box-shadow: 0 2px 16px rgba(0,0,0,0.04);
            }
            [data-testid="stExpander"]:hover {
                border-color: rgba(5,150,105,0.2) !important;
                box-shadow: 0 8px 32px rgba(5,150,105,0.08);
            }
            .stButton>button[kind="primary"] {
                background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                color: white;
                box-shadow: 0 2px 12px rgba(5,150,105,0.25);
            }
            .stButton>button[kind="primary"]:hover {
                background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
                box-shadow: 0 6px 28px rgba(5,150,105,0.35);
            }
            .stButton>button {
                background: rgba(255,255,255,0.8);
                color: #424a53;
                border: 1px solid rgba(0,0,0,0.08);
            }
            .stButton>button:hover {
                background: rgba(240,253,244,0.9);
                color: #1f2328;
                border-color: rgba(5,150,105,0.3);
                box-shadow: 0 4px 20px rgba(5,150,105,0.1);
            }
            .stTabs [data-baseweb="tab-list"] { background: rgba(246,248,250,0.6); }
            .stTabs [data-baseweb="tab"] { background: transparent; color: #656d76; }
            .stTabs [data-baseweb="tab"]:hover { color: #424a53; background: rgba(5,150,105,0.05); }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #059669, #10b981) !important;
                color: white !important;
                font-weight: 600;
                box-shadow: 0 2px 16px rgba(5,150,105,0.25);
            }
            div[data-testid="stMetricValue"] { color: #1f2328; }
            div[data-testid="stMetricLabel"] { color: #656d76; }
            .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div {
                background: rgba(255,255,255,0.9) !important;
                border-color: rgba(0,0,0,0.08) !important;
                color: #1f2328 !important;
                border-radius: 10px !important;
            }
            .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
                border-color: rgba(5,150,105,0.4) !important;
                box-shadow: 0 0 0 3px rgba(5,150,105,0.1) !important;
            }
            .stTextInput>div>div>input::placeholder, .stTextArea>div>div>textarea::placeholder {
                color: #9ca3af !important;
                opacity: 1 !important;
            }
            ::-webkit-scrollbar-thumb { background: rgba(5,150,105,0.15); }
            ::-webkit-scrollbar-thumb:hover { background: rgba(5,150,105,0.3); }
            .glass-stat-card .stat-value { color: #1f2328; }
            .glass-stat-card .stat-label { color: #656d76; }
            .gauge-ring .gauge-value { color: #1f2328; }
            code {
                background-color: rgba(5,150,105,0.08);
                color: #059669;
                padding: 2px 8px;
                border-radius: 6px;
                font-size: 0.8em;
            }
        </style>"""
