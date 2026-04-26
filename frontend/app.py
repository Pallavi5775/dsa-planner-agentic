# -*- coding: utf-8 -*-
import os
import calendar as cal_lib
import streamlit as st
import requests
from datetime import datetime, timedelta, date
import pandas as pd
import time

# Set BACKEND_URL env var to override (e.g. for local dev: http://localhost:8000)
_BACKEND = os.getenv("BACKEND_URL", "https://dsa-planner.co.in")
API_URL = f"{_BACKEND}/api"

st.set_page_config(layout="wide", page_title="DSA Revision Planner", page_icon="🎯")


# ── AUTH PERSISTENCE via URL query params ─────────────────────────────────────
# st.query_params are part of the URL so they survive page reloads automatically.
# We write them on login and read them on every cold start.

def _save_auth_qparams(token, username, user_id, role):
    st.query_params["tok"] = token
    st.query_params["usr"] = username
    st.query_params["uid"] = str(user_id)
    st.query_params["rol"] = role


def _restore_auth_from_qparams():
    tok = st.query_params.get("tok", "")
    if not tok:
        return
    try:
        r = requests.get(f"{API_URL}/auth/me",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=5)
        if r.status_code == 200:
            me = r.json()
            st.session_state.token          = tok
            st.session_state.username       = me.get("username", st.query_params.get("usr", ""))
            st.session_state.user_id        = me.get("id", int(st.query_params.get("uid", "0") or "0"))
            st.session_state.role           = me.get("role", st.query_params.get("rol", "user"))
            st.session_state.oauth_provider = me.get("oauth_provider")
            st.session_state.github_username= me.get("github_username")
            st.session_state.avatar_url     = me.get("avatar_url")
            st.rerun()
        else:
            # Token expired or invalid — clear it
            st.query_params.clear()
    except Exception:
        pass


# Restore session on every cold start (session_state wiped on reload)
if not st.session_state.get("token"):
    _restore_auth_from_qparams()


# ── AUTH HELPERS ──────────────────────────────────────────────────────────────
def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


BACKEND_URL = "http://localhost:8000"


def show_auth_page():
    """Full-screen OAuth login page."""
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] { background: #faf5ff !important; }
    .auth-btn {
        display: flex; align-items: center; justify-content: center; gap: 10px;
        width: 100%; padding: 13px 20px; border-radius: 12px; font-size: 1em;
        font-weight: 600; text-decoration: none; margin-bottom: 12px;
        border: 1.5px solid; cursor: pointer; transition: opacity .15s;
    }
    .auth-btn:hover { opacity: .85; }
    .btn-google { background:#fff; color:#3c4043; border-color:#dadce0; }
    .btn-github { background:#24292e; color:#fff; border-color:#24292e; }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        st.markdown(
            '<div style="font-size:2.2em;text-align:center;margin-bottom:4px">🎯</div>'
            '<div style="text-align:center;font-size:1.5em;font-weight:800;'
            'background:linear-gradient(135deg,#7c3aed,#db2777);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'margin-bottom:2px">DSA Revision Planner</div>'
            '<div style="text-align:center;color:#a78bfa;font-size:.85em;margin-bottom:28px">'
            'Track · Practice · Master</div>',
            unsafe_allow_html=True,
        )

        google_url = f"{_BACKEND}/api/auth/google"
        github_url = f"{_BACKEND}/api/auth/github"

        st.markdown(
            f'<a class="auth-btn btn-google" href="{google_url}" target="_self">'
            '<svg width="20" height="20" viewBox="0 0 48 48">'
            '<path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.2l6.7-6.7C35.8 2.5 30.2 0 24 0 14.8 0 6.9 5.4 3 13.3l7.8 6C12.7 13 17.9 9.5 24 9.5z"/>'
            '<path fill="#4285F4" d="M46.6 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4 6.9-10 6.9-17z"/>'
            '<path fill="#FBBC05" d="M10.8 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7L2.5 13.3A24 24 0 0 0 0 24c0 3.8.9 7.4 2.5 10.6l8.3-5.9z"/>'
            '<path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.2-8.4 2.2-6.1 0-11.3-3.6-13.2-8.8l-8.3 5.9C6.9 42.6 14.8 48 24 48z"/>'
            '</svg>Continue with Google</a>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<a class="auth-btn btn-github" href="{github_url}" target="_self">'
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="white">'
            '<path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.2 11.38.6.1.82-.26.82-.58v-2.17c-3.34.72-4.04-1.6-4.04-1.6-.54-1.38-1.33-1.75-1.33-1.75-1.09-.74.08-.73.08-.73 1.2.09 1.83 1.24 1.83 1.24 1.07 1.83 2.8 1.3 3.48.99.1-.78.42-1.3.76-1.6-2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 3-.4c1.02 0 2.04.13 3 .4 2.28-1.55 3.29-1.23 3.29-1.23.66 1.65.24 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58C20.56 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z"/>'
            '</svg>Continue with GitHub</a>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<p style="text-align:center;color:#a78bfa;font-size:.78em;margin-top:16px">'
            'We only read your public profile and email address.</p>',
            unsafe_allow_html=True,
        )

    st.stop()  # don't render the main app

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #faf5ff !important;
    font-family: 'Inter','Segoe UI',sans-serif;
    font-size: 17px !important;
}
.block-container { padding-top: 1.6rem !important; }

[data-testid="metric-container"] {
    background: #fff !important;
    border: 1.5px solid #ede9fe !important;
    border-radius: 16px !important;
    padding: 18px 22px !important;
    box-shadow: 0 2px 8px rgba(124,58,237,.08) !important;
}
[data-testid="stMetricLabel"] p {
    color: #7c3aed !important;
    font-size: .72em !important;
    font-weight: 700 !important;
    letter-spacing: .8px !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.9em !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg,#7c3aed,#db2777) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}

[data-testid="stTabs"] [role="tab"] {
    font-weight: 600; color: #9ca3af; font-size: .9em;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #7c3aed !important;
    border-bottom: 2.5px solid #7c3aed !important;
}

[data-testid="stSelectbox"] > div > div {
    border-radius: 10px !important;
    border-color: #ede9fe !important;
    background: #fff !important;
    font-size: .9em !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #1e0b38 !important;
    border-right: 1px solid #2d1457 !important;
}
[data-testid="stSidebar"] > div { padding-top: .8rem; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label { color: #e2d9f3 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #f3e8ff !important; }
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] input {
    background: #2a1050 !important;
    border: 1px solid #3d1a72 !important;
    color: #e9d5ff !important;
    border-radius: 10px !important;
    font-size: .92em !important;
}
[data-testid="stSidebar"] textarea:focus,
[data-testid="stSidebar"] input:focus {
    border-color: #a855f7 !important;
    box-shadow: 0 0 0 2px rgba(168,85,247,.25) !important;
}
[data-testid="stSidebar"] .stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: .9em !important;
}
[data-testid="stSidebar"] [data-testid="baseButton-primary"] > button {
    background: linear-gradient(135deg,#7c3aed,#db2777) !important;
    border: none !important; color: #fff !important;
    box-shadow: 0 2px 8px rgba(124,58,237,.35) !important;
}
</style>
""", unsafe_allow_html=True)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def fetch_activity():
    try:
        r = requests.get(f"{API_URL}/activity", headers=auth_headers(), timeout=8)
        return r.json() if r.status_code == 200 else {}
    except:
        return {}


def build_heatmap_html(sessions_by_date: dict, weeks: int = 16) -> str:
    from datetime import date as d_type, timedelta as td
    today = d_type.today()
    start = today - td(days=today.weekday() + 7 * (weeks - 1))

    def cell_color(n):
        if n == 0:   return "#f0ebff"
        if n == 1:   return "#ddd6fe"
        if n == 2:   return "#a78bfa"
        if n == 3:   return "#7c3aed"
        return "#4c1d95"

    day_labels = ["Mon","","Wed","","Fri","","Sun"]

    # left day-name column
    day_col = "".join(
        f'<div style="height:13px;line-height:13px;font-size:.6em;color:#a78bfa;'
        f'text-align:right;padding-right:4px;margin-bottom:2px;">{l}</div>'
        for l in day_labels
    )

    # week columns
    week_cols = ""
    cur = start
    prev_month = None
    month_labels = ""
    col_idx = 0

    while cur <= today:
        # month label
        if cur.month != prev_month:
            left_px = col_idx * 15
            month_labels += (
                f'<span style="position:absolute;left:{left_px}px;'
                f'font-size:.6em;color:#7c3aed;font-weight:600;">'
                f'{cur.strftime("%b")}</span>'
            )
            prev_month = cur.month

        col = ""
        for dow in range(7):
            day = cur + td(days=dow)
            if day > today:
                col += '<div style="height:13px;margin-bottom:2px;"></div>'
                continue
            n     = sessions_by_date.get(day.strftime("%Y-%m-%d"), 0)
            bg    = cell_color(n)
            tip   = f"{day.strftime('%b %d')}: {n} session{'s' if n!=1 else ''}"
            is_today = day == today
            border = "border:1.5px solid #7c3aed;" if is_today else ""
            col += (
                f'<div title="{tip}" style="width:11px;height:11px;border-radius:3px;'
                f'background:{bg};{border}margin-bottom:2px;"></div>'
            )
        week_cols += f'<div style="display:flex;flex-direction:column;margin-right:2px;">{col}</div>'
        cur += td(days=7)
        col_idx += 1

    return (
        f'<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:16px;'
        f'padding:18px 20px;box-shadow:0 2px 8px rgba(124,58,237,.06);">'
        f'<div style="font-size:.7em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
        f'color:#7c3aed;margin-bottom:10px;">Activity Heatmap — last {weeks} weeks</div>'
        f'<div style="display:flex;align-items:flex-start;gap:0;">'
        f'  <div style="margin-top:12px;">{day_col}</div>'
        f'  <div style="position:relative;">'
        f'    <div style="position:relative;height:14px;margin-bottom:4px;">{month_labels}</div>'
        f'    <div style="display:flex;">{week_cols}</div>'
        f'  </div>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:4px;margin-top:10px;">'
        f'  <span style="font-size:.65em;color:#a78bfa;">Less</span>'
        + "".join(f'<div style="width:10px;height:10px;border-radius:2px;background:{cell_color(i)};"></div>' for i in range(5))
        + f'  <span style="font-size:.65em;color:#a78bfa;">More</span>'
        f'</div>'
        f'</div>'
    )


def fetch_questions():
    try:
        r = requests.get(f"{API_URL}/questions", headers=auth_headers(), timeout=8)
        if r.status_code == 401:
            st.session_state.pop('token', None)
            st.rerun()
        return r.json() if r.status_code == 200 else []
    except:
        return []


def badge_html(label, bg, color):
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;'
        f'font-size:.68em;font-weight:700;letter-spacing:.5px;text-transform:uppercase;'
        f'background:{bg};color:{color};margin-right:4px;">{label}</span>'
    )


def coverage_badge(cs):
    return badge_html(cs, "#fce7f3", "#9d174d") if cs == "Covered" else badge_html(cs, "#f5f3ff", "#6d28d9")


def revision_badge(rs):
    cfg = {
        "Mastered":   ("#ede9fe", "#5b21b6"),
        "Needs Work": ("#fff1f2", "#be123c"),
        "Pending":    ("#fdf4ff", "#a21caf"),
    }
    bg, col = cfg.get(rs, ("#fdf4ff", "#a21caf"))
    return badge_html(rs, bg, col)


def acc_bar_html(acc):
    acc = acc or 0
    grad = (
        "linear-gradient(90deg,#22c55e,#86efac)" if acc >= 80
        else "linear-gradient(90deg,#f59e0b,#fcd34d)" if acc >= 60
        else "linear-gradient(90deg,#ec4899,#f9a8d4)"
    )
    col = "#22c55e" if acc >= 80 else "#f59e0b" if acc >= 60 else "#ec4899"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;">'
        f'<span style="display:inline-block;background:#f5f3ff;border-radius:6px;height:6px;width:80px;vertical-align:middle;">'
        f'<span style="display:block;height:6px;border-radius:6px;width:{min(acc,100):.0f}%;background:{grad};"></span></span>'
        f'<span style="font-size:.78em;color:{col};font-weight:600;">{acc:.0f}%</span>'
        f'</span>'
    )


def build_calendar(questions, year, month):
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    due_map = {}
    for q in questions:
        nr = q.get('next_revision')
        if nr:
            due_map.setdefault(nr, []).append(q)

    headers = "".join(
        f'<div style="text-align:center;font-size:.6em;font-weight:700;color:#a78bfa;'
        f'letter-spacing:.8px;text-transform:uppercase;padding:4px 0 8px;">{d}</div>'
        for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    )

    cells = ""
    for week in cal_lib.monthcalendar(year, month):
        for day in week:
            if day == 0:
                cells += '<div></div>'
                continue
            ds = f"{year}-{month:02d}-{day:02d}"
            qs = due_map.get(ds, [])
            is_today   = ds == today_str
            is_overdue = ds < today_str and bool(qs)
            is_due     = bool(qs)

            if is_today:
                bg, border = "linear-gradient(135deg,#7c3aed,#db2777)", "transparent"
                dn_col = "#fff"
            elif is_overdue:
                bg, border = "#fff1f2", "#fca5a5"
                dn_col = "#be123c"
            elif is_due:
                bg, border = "#faf5ff", "#c4b5fd"
                dn_col = "#4c1d95"
            else:
                bg, border = "#faf5ff", "transparent"
                dn_col = "#6b7280"

            badge = ""
            if qs:
                dot_bg = "#ef4444" if is_overdue else "linear-gradient(135deg,#7c3aed,#db2777)"
                badge = (
                    f'<span style="display:inline-block;background:{dot_bg};color:#fff;'
                    f'border-radius:10px;font-size:.58em;font-weight:700;padding:1px 5px;'
                    f'margin-top:2px;">{len(qs)}</span>'
                )

            cells += (
                f'<div style="background:{bg};border:1px solid {border};border-radius:10px;'
                f'padding:6px 4px 4px;text-align:center;min-height:48px;display:flex;'
                f'flex-direction:column;align-items:center;gap:2px;">'
                f'<span style="font-size:.78em;color:{dn_col};font-weight:600;">{day}</span>'
                f'{badge}</div>'
            )

    return (
        f'<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:20px;'
        f'padding:20px;box-shadow:0 4px 16px rgba(124,58,237,.08);">'
        f'<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;">'
        f'{headers}{cells}'
        f'</div></div>'
    )


# ── AUTH GATE ─────────────────────────────────────────────────────────────────
if not st.session_state.get('token'):
    show_auth_page()

# ── INIT ──────────────────────────────────────────────────────────────────────
for key, val in [("active_qid", None), ("cal_year", datetime.now().year), ("cal_month", datetime.now().month)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── TOP BAR ───────────────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([0.75, 0.25])
with hdr_left:
    st.markdown(
        '<h1 style="color:#3b0764;font-weight:800;letter-spacing:-1px;margin-bottom:0;">🎯 DSA Revision Planner</h1>'
        '<p style="color:#a78bfa;font-size:.88em;font-weight:500;margin-bottom:1.2rem;">Track · Practice · Master</p>',
        unsafe_allow_html=True,
    )
with hdr_right:
    username = st.session_state.get('username', '')
    role     = st.session_state.get('role', 'user')
    is_admin = role == 'admin'

    role_icon  = "👑" if is_admin else "👤"
    role_label = "Admin" if is_admin else "User"
    role_bg    = "linear-gradient(135deg,#7c3aed,#db2777)" if is_admin else "linear-gradient(135deg,#6366f1,#8b5cf6)"

    st.markdown(
        f'<div style="text-align:right;padding-top:10px;display:flex;justify-content:flex-end;gap:8px;align-items:center;">'
        f'<span style="background:{role_bg};color:#fff;border-radius:20px;'
        f'padding:4px 14px;font-size:.82em;font-weight:700;">{role_icon} {username}</span>'
        f'<span style="background:#f3e8ff;color:#7c3aed;border-radius:20px;'
        f'padding:3px 10px;font-size:.72em;font-weight:700;letter-spacing:.5px;text-transform:uppercase;">{role_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("Logout", key="logout_btn", use_container_width=True):
        st.query_params.clear()
        for k in ['token', 'username', 'user_id', 'role', 'active_qid', 'start_timestamp']:
            st.session_state.pop(k, None)
        st.rerun()

questions = fetch_questions()
df = pd.DataFrame(questions) if questions else pd.DataFrame()

is_admin   = st.session_state.get('role', 'user') == 'admin'
has_github = st.session_state.get('oauth_provider') == 'github'

# Build tab list dynamically — Journal only for GitHub users, Add Questions only for admins
tab_labels = ["📋 Questions", "📅 Calendar", "⚡ Activity", "⚙ Settings"]
if has_github:
    tab_labels.append("📖 Journal")
if is_admin:
    tab_labels.append("➕ Add Questions")

JOURNAL_IDX = tab_labels.index("📖 Journal") if has_github else None
ADMIN_IDX   = tab_labels.index("➕ Add Questions") if is_admin else None

tabs = st.tabs(tab_labels)

# Persist active tab across reloads via ?tab=N in the URL
st.markdown("""
<script>
(function() {
    function getTabParam() {
        return parseInt(new URLSearchParams(window.parent.location.search).get('tab') || '0');
    }
    function setTabParam(idx) {
        const url = new URL(window.parent.location);
        url.searchParams.set('tab', idx);
        window.parent.history.replaceState({}, '', url);
    }
    function activate() {
        const tabEls = window.parent.document.querySelectorAll('[data-testid="stTabs"] [role="tab"]');
        if (!tabEls.length) { setTimeout(activate, 150); return; }
        const idx = getTabParam();
        if (idx > 0 && tabEls[idx]) tabEls[idx].click();
        tabEls.forEach((t, i) => t.addEventListener('click', () => setTabParam(i), { once: false }));
    }
    // Re-attach on every Streamlit re-run
    if (document.readyState === 'complete') activate();
    else window.addEventListener('load', activate);
    setTimeout(activate, 300);
})();
</script>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 0 — QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    if df.empty:
        st.info("No problems found. Upload a markdown file to get started.")
    else:
        today_str = datetime.now().strftime("%Y-%m-%d")
        week_str  = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        # ── Metrics ──────────────────────────────────────────────────────────
        covered  = len(df[df['coverage_status'] == 'Covered'])
        due_ct   = len(df[df['next_revision'].fillna('9999') <= today_str])
        mastered = len(df[df['revision_status'] == 'Mastered']) if 'revision_status' in df.columns else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total",      len(df))
        m2.metric("Covered",    covered)
        m3.metric("Due Today",  due_ct)
        m4.metric("Mastered",   mastered)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Filter panel (no split HTML — pure native widgets) ────────────────
        st.markdown(
            '<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:14px;'
            'padding:14px 18px 2px;margin-bottom:14px;box-shadow:0 1px 4px rgba(124,58,237,.05);">'
            '<span style="font-size:.65em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bfa;">🔎 Filters</span>'
            '</div>',
            unsafe_allow_html=True
        )

        fc1, fc2, fc3, fc4 = st.columns(4)
        patterns   = ["All"] + sorted(df['pattern'].dropna().unique().tolist())
        pat_filter = fc1.selectbox("Pattern",         patterns,                                     label_visibility="visible")
        rev_filter = fc2.selectbox("Revision Status", ["All","Pending","Needs Work","Mastered"],    label_visibility="visible")
        acc_filter = fc3.selectbox("Accuracy",        ["All","High ≥80%","Medium 60–79%","Low <60%"], label_visibility="visible")
        due_filter = fc4.selectbox("Due",             ["All","Due Today","Due This Week","Overdue"], label_visibility="visible")

        fc5, fc6, _, _ = st.columns(4)
        cov_filter = fc5.selectbox("Coverage", ["All","Covered","Not Covered"], label_visibility="visible")
        sort_by    = fc6.selectbox("Sort By",   ["Default","Accuracy ↑","Accuracy ↓","Next Revision ↑"], label_visibility="visible")

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ── Apply filters ─────────────────────────────────────────────────────
        flt = df.copy()
        flt['accuracy']      = flt['accuracy'].fillna(0)
        flt['next_revision'] = flt['next_revision'].fillna('9999-12-31')

        if pat_filter != "All":               flt = flt[flt['pattern'] == pat_filter]
        if rev_filter != "All":               flt = flt[flt['revision_status'] == rev_filter]
        if cov_filter != "All":               flt = flt[flt['coverage_status'] == cov_filter]
        if acc_filter == "High ≥80%":         flt = flt[flt['accuracy'] >= 80]
        elif acc_filter == "Medium 60–79%":   flt = flt[(flt['accuracy'] >= 60) & (flt['accuracy'] < 80)]
        elif acc_filter == "Low <60%":        flt = flt[flt['accuracy'] < 60]
        if due_filter == "Due Today":         flt = flt[flt['next_revision'] <= today_str]
        elif due_filter == "Due This Week":   flt = flt[flt['next_revision'] <= week_str]
        elif due_filter == "Overdue":         flt = flt[flt['next_revision'] < today_str]
        if sort_by == "Accuracy ↑":           flt = flt.sort_values('accuracy', ascending=True)
        elif sort_by == "Accuracy ↓":         flt = flt.sort_values('accuracy', ascending=False)
        elif sort_by == "Next Revision ↑":    flt = flt.sort_values('next_revision', ascending=True)

        st.markdown(
            f'<p style="font-size:.78em;color:#a78bfa;font-weight:600;margin-bottom:8px;">'
            f'Showing {len(flt)} of {len(df)} problems</p>',
            unsafe_allow_html=True
        )

        # ── Question cards ────────────────────────────────────────────────────
        for _, row in flt.iterrows():
            cs       = row.get('coverage_status', 'Not Covered')
            rs       = row.get('revision_status', 'Pending')
            acc_val  = float(row.get('accuracy') or 0)
            next_rev = str(row.get('next_revision') or '—').replace('9999-12-31', '—')
            total_t  = int(row.get('total_time_spent') or 0)
            is_due   = next_rev != '—' and next_rev <= today_str

            due_badge = badge_html("⚠ Due", "#ffe4e6", "#be123c") if is_due else ""

            acc_col   = "#16a34a" if acc_val >= 80 else "#d97706" if acc_val >= 60 else "#db2777"
            acc_bg    = "#dcfce7" if acc_val >= 80 else "#fef3c7" if acc_val >= 60 else "#fce7f3"
            card_html = (
                f'<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:16px;'
                f'padding:16px 20px;margin-bottom:10px;box-shadow:0 1px 6px rgba(219,39,119,.04);">'
                f'  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:7px;">'
                f'    <div style="display:flex;flex-wrap:wrap;gap:4px;">'
                f'      {badge_html(row["pattern"],"#ede9fe","#5b21b6")}'
                f'      {coverage_badge(cs)}'
                f'      {revision_badge(rs)}'
                f'      {due_badge}'
                f'    </div>'
                f'    <div style="background:{acc_bg};border-radius:20px;padding:3px 10px;'
                f'    font-size:.82em;font-weight:800;color:{acc_col};white-space:nowrap;'
                f'    border:1.5px solid {acc_col}22;">🎯 {acc_val:.0f}%</div>'
                f'  </div>'
                f'  <div style="font-weight:700;font-size:.97em;color:#1e1b4b;margin-bottom:8px;">{row["title"]}</div>'
                f'  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">'
                f'    <span>{acc_bar_html(acc_val)}</span>'
                f'    <span style="font-size:.77em;color:#6b7280;">📅 {next_rev}</span>'
                f'    <span style="font-size:.77em;color:#6b7280;">⏱ {total_t}m</span>'
                f'  </div>'
                f'</div>'
            )

            col_card, col_btn = st.columns([0.84, 0.16])
            with col_card:
                st.markdown(card_html, unsafe_allow_html=True)
            with col_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Practice →", key=f"sel_{row['id']}", use_container_width=True):
                    st.session_state.active_qid = int(row['id'])
                    if 'start_timestamp' in st.session_state:
                        del st.session_state.start_timestamp
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    today_str = datetime.now().strftime("%Y-%m-%d")

    nav_l, nav_m, nav_r = st.columns([0.1, 0.8, 0.1])
    if nav_l.button("◀", key="cal_prev", use_container_width=True):
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12; st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
        st.rerun()

    nav_m.markdown(
        f'<div style="text-align:center;font-size:1.15em;font-weight:800;'
        f'background:linear-gradient(135deg,#7c3aed,#db2777);'
        f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;padding-top:5px;">'
        f'{cal_lib.month_name[st.session_state.cal_month]} {st.session_state.cal_year}</div>',
        unsafe_allow_html=True
    )
    if nav_r.button("▶", key="cal_next", use_container_width=True):
        if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1; st.session_state.cal_year += 1
        else:
            st.session_state.cal_month += 1
        st.rerun()

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown(build_calendar(questions, st.session_state.cal_year, st.session_state.cal_month), unsafe_allow_html=True)
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Revision list for month ───────────────────────────────────────────────
    yr, mo = st.session_state.cal_year, st.session_state.cal_month
    m_start = f"{yr}-{mo:02d}-01"
    m_end   = f"{yr}-{mo:02d}-{cal_lib.monthrange(yr, mo)[1]:02d}"
    month_qs = sorted(
        [q for q in questions if q.get('next_revision') and m_start <= q['next_revision'] <= m_end],
        key=lambda q: q['next_revision']
    )

    st.markdown(
        f'<p style="font-size:.75em;font-weight:700;color:#a78bfa;letter-spacing:.8px;'
        f'text-transform:uppercase;margin-bottom:10px;">Revisions this month — {len(month_qs)} problems</p>',
        unsafe_allow_html=True
    )

    if not month_qs:
        st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No revisions scheduled this month.</p>', unsafe_allow_html=True)
    else:
        for q in month_qs:
            nr         = q['next_revision']
            is_over    = nr < today_str
            row_bg     = "#fff1f2" if is_over else "#fff"
            row_border = "#fca5a5" if is_over else "#ede9fe"
            date_col   = "#be123c" if is_over else "#7c3aed"
            ov_tag     = ' <span style="color:#be123c;font-size:.7em;font-weight:700;">⚠ OVERDUE</span>' if is_over else ""
            rs         = q.get('revision_status', 'Pending')

            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;background:{row_bg};'
                f'border:1px solid {row_border};border-radius:10px;padding:9px 14px;margin-bottom:6px;">'
                f'  <span style="color:{date_col};font-weight:700;font-size:.75em;min-width:70px;">📅 {nr}</span>'
                f'  <span style="color:#1e1b4b;font-weight:600;font-size:.84em;flex:1;">{q["title"]}{ov_tag}</span>'
                f'  {revision_badge(rs)}'
                f'  <span style="font-size:.78em;font-weight:800;color:{"#16a34a" if (q.get("accuracy") or 0)>=80 else "#d97706" if (q.get("accuracy") or 0)>=60 else "#db2777"};">🎯 {q.get("accuracy") or 0:.0f}%</span>'
                f'</div>',
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    act = fetch_activity()
    sbd = act.get("sessions_by_date", {})

    # ── Stat cards ────────────────────────────────────────────────────────────
    def stat_card(icon, label, value, sub="", grad="linear-gradient(135deg,#7c3aed,#db2777)"):
        return (
            f'<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:16px;'
            f'padding:18px 20px;box-shadow:0 2px 8px rgba(124,58,237,.07);text-align:center;">'
            f'  <div style="font-size:1.6em;margin-bottom:4px;">{icon}</div>'
            f'  <div style="font-size:.65em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#a78bfa;">{label}</div>'
            f'  <div style="font-size:2em;font-weight:800;background:{grad};-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2;">{value}</div>'
            f'  <div style="font-size:.72em;color:#6b7280;margin-top:2px;">{sub}</div>'
            f'</div>'
        )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(stat_card("🔥", "Streak",          f'{act.get("streak_days", 0)}d',  "days in a row"), unsafe_allow_html=True)
    c2.markdown(stat_card("📅", "Today",            act.get("today_sessions", 0),     f'{act.get("today_time_minutes", 0)}m spent'), unsafe_allow_html=True)
    c3.markdown(stat_card("📆", "This Week",        act.get("weekly_sessions", 0),    "sessions", "linear-gradient(135deg,#6366f1,#a855f7)"), unsafe_allow_html=True)
    c4.markdown(stat_card("🎯", "Total Sessions",   act.get("total_sessions", 0),     "all time",  "linear-gradient(135deg,#db2777,#f97316)"), unsafe_allow_html=True)
    c5.markdown(stat_card("⏱", "Total Time",       f'{act.get("total_time_minutes",0)}m', "practiced", "linear-gradient(135deg,#0ea5e9,#6366f1)"), unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Heatmap ───────────────────────────────────────────────────────────────
    st.markdown(build_heatmap_html(sbd), unsafe_allow_html=True)
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Feed + Pattern chart ──────────────────────────────────────────────────
    feed_col, chart_col = st.columns([0.58, 0.42])

    with feed_col:
        st.markdown(
            '<div style="font-size:.7em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
            'color:#7c3aed;margin-bottom:10px;">📋 Recent Sessions</div>',
            unsafe_allow_html=True
        )
        recent = act.get("recent_sessions", [])
        if not recent:
            st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No sessions yet — start practicing!</p>', unsafe_allow_html=True)
        else:
            # Group by date
            from itertools import groupby
            grouped = {}
            for s in recent:
                grouped.setdefault(s["date"], []).append(s)

            for day, sessions in list(grouped.items())[:7]:
                try:
                    day_fmt = datetime.strptime(day, "%Y-%m-%d").strftime("%a, %b %d")
                except:
                    day_fmt = day
                st.markdown(
                    f'<div style="font-size:.72em;font-weight:700;color:#a78bfa;'
                    f'letter-spacing:.5px;text-transform:uppercase;margin:10px 0 5px;">{day_fmt}</div>',
                    unsafe_allow_html=True
                )
                for s in sessions:
                    ok        = s.get("correct", True)
                    ok_icon   = "✅" if ok else "❌"
                    ok_col    = "#15803d" if ok else "#be123c"
                    ok_bg     = "#dcfce7" if ok else "#fee2e2"
                    mins      = max(1, (s.get("time_taken") or 0) // 60)
                    pattern   = s.get("pattern", "")
                    title     = s.get("question_title", "")
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;background:#fff;'
                        f'border:1px solid #ede9fe;border-radius:10px;padding:9px 14px;margin-bottom:5px;">'
                        f'  <span style="background:{ok_bg};color:{ok_col};border-radius:6px;'
                        f'    padding:2px 7px;font-size:.7em;font-weight:700;">{ok_icon}</span>'
                        f'  <div style="flex:1;min-width:0;">'
                        f'    <div style="font-weight:600;font-size:.84em;color:#1e1b4b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{title}</div>'
                        f'    <div style="font-size:.72em;color:#a78bfa;margin-top:1px;">{pattern}</div>'
                        f'  </div>'
                        f'  <span style="font-size:.75em;color:#6b7280;white-space:nowrap;">⏱ {mins}m</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

    with chart_col:
        st.markdown(
            '<div style="font-size:.7em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
            'color:#7c3aed;margin-bottom:10px;">📊 Practice by Pattern</div>',
            unsafe_allow_html=True
        )
        pc = act.get("pattern_counts", {})
        if not pc:
            st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No data yet.</p>', unsafe_allow_html=True)
        else:
            max_count = max(pc.values()) or 1
            grads = [
                "linear-gradient(90deg,#7c3aed,#db2777)",
                "linear-gradient(90deg,#6366f1,#a855f7)",
                "linear-gradient(90deg,#db2777,#f97316)",
                "linear-gradient(90deg,#0ea5e9,#6366f1)",
                "linear-gradient(90deg,#a855f7,#ec4899)",
            ]
            for i, (pattern, count) in enumerate(list(pc.items())[:12]):
                pct  = count / max_count * 100
                grad = grads[i % len(grads)]
                short = pattern if len(pattern) <= 20 else pattern[:18] + "…"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">'
                    f'  <span style="font-size:.75em;color:#4c1d95;font-weight:500;min-width:130px;'
                    f'    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{short}</span>'
                    f'  <div style="flex:1;background:#f0ebff;border-radius:6px;height:9px;">'
                    f'    <div style="width:{pct:.0f}%;background:{grad};height:9px;border-radius:6px;"></div>'
                    f'  </div>'
                    f'  <span style="font-size:.72em;color:#7c3aed;font-weight:700;min-width:22px;text-align:right;">{count}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown(
        '<p style="font-size:.7em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
        'color:#7c3aed;margin-bottom:16px;">Practice Schedule</p>',
        unsafe_allow_html=True
    )

    # Load current practice_days from API
    if 'practice_days_loaded' not in st.session_state:
        try:
            r = requests.get(f"{API_URL}/me/practice-days", headers=auth_headers(), timeout=5)
            if r.status_code == 200:
                st.session_state.practice_days_str = r.json().get("practice_days", "")
            else:
                st.session_state.practice_days_str = ""
        except:
            st.session_state.practice_days_str = ""
        st.session_state.practice_days_loaded = True

    current_days = set(
        int(d) for d in st.session_state.get("practice_days_str", "").split(",")
        if d.strip().isdigit()
    )

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    st.markdown(
        '<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:16px;'
        'padding:24px 28px;max-width:460px;box-shadow:0 2px 8px rgba(124,58,237,.07);">',
        unsafe_allow_html=True
    )
    st.markdown(
        '<p style="font-size:.85em;color:#6b7280;margin-bottom:16px;">'
        'Choose the days you practice each week. Leave all unchecked for daily mode.</p>',
        unsafe_allow_html=True
    )

    selected = []
    cols = st.columns(2)
    for i, name in enumerate(DAY_NAMES):
        with cols[i % 2]:
            if st.checkbox(name, value=(i in current_days), key=f"day_{i}"):
                selected.append(i)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    if st.button("💾 Save Schedule", type="primary", key="save_schedule_btn"):
        new_val = ",".join(str(d) for d in sorted(selected))
        try:
            r = requests.patch(
                f"{API_URL}/me/practice-days",
                json={"practice_days": new_val},
                headers=auth_headers(),
                timeout=5,
            )
            if r.status_code == 200:
                st.session_state.practice_days_str = new_val
                st.session_state.practice_days_loaded = True
                if new_val:
                    day_labels = [DAY_NAMES[int(d)] for d in new_val.split(",")]
                    st.success(f"Schedule saved: {', '.join(day_labels)}")
                else:
                    st.success("Schedule set to daily (every day).")
            else:
                st.error("Failed to save schedule.")
        except Exception as e:
            st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB — PRACTICE JOURNAL  (GitHub-connected users only)
# ══════════════════════════════════════════════════════════════════════════════
if has_github and JOURNAL_IDX is not None:
    with tabs[JOURNAL_IDX]:
        st.markdown("## 📖 Practice Journal")
        st.caption("Your sessions are stored in a private GitHub repo — only you can see them.")

        gh_user  = st.session_state.get("github_username", "")
        repo_url = f"https://github.com/{gh_user}/dsa-planner-data"
        st.markdown(
            f'<a href="{repo_url}" target="_blank" style="color:#7c3aed;font-size:.85em">'
            f'🔗 View raw repo: {gh_user}/dsa-planner-data</a>',
            unsafe_allow_html=True,
        )

        # Ensure the private repo exists (silently, on first visit)
        if not st.session_state.get("gh_repo_ensured"):
            try:
                requests.post(f"{API_URL}/github/setup",
                              headers=auth_headers(), timeout=15)
                st.session_state.gh_repo_ensured = True
            except Exception:
                pass

        st.divider()

        load_col, filter_col1, filter_col2 = st.columns([1, 2, 2])
        with load_col:
            if st.button("🔄 Load / Refresh", type="primary"):
                st.session_state.pop("gh_journal", None)

        # Fetch from API (cached in session_state until refresh)
        if "gh_journal" not in st.session_state:
            with st.spinner("Fetching sessions from GitHub…"):
                try:
                    r = requests.get(f"{API_URL}/github/history",
                                     headers=auth_headers(), timeout=30)
                    if r.status_code == 200:
                        st.session_state.gh_journal = r.json().get("sessions", [])
                    else:
                        st.session_state.gh_journal = []
                        st.error("Could not load sessions from GitHub.")
                except Exception as e:
                    st.session_state.gh_journal = []
                    st.error(f"Error: {e}")

        sessions = st.session_state.get("gh_journal", [])

        if not sessions:
            st.info("No practice sessions yet. Complete a session to start tracking!")
        else:
            with filter_col1:
                search_q = st.text_input("🔍 Search question", "", key="jrn_search",
                                         placeholder="e.g. Two Sum")
            with filter_col2:
                result_filter = st.selectbox("Filter by result",
                                             ["All", "Correct ✅", "Incorrect ❌"],
                                             key="jrn_filter")

            filtered = sessions
            if search_q:
                filtered = [s for s in filtered
                            if search_q.lower() in s.get("question", "").lower()]
            if result_filter == "Correct ✅":
                filtered = [s for s in filtered if s.get("correct")]
            elif result_filter == "Incorrect ❌":
                filtered = [s for s in filtered if not s.get("correct")]

            st.markdown(f"**{len(filtered)} session(s)**")
            st.divider()

            current_date = None
            for s in filtered:
                date = s.get("date", "Unknown date")
                if date != current_date:
                    st.markdown(f"### 📅 {date}")
                    current_date = date

                correct    = s.get("correct", True)
                mins       = s.get("time_taken_seconds", 0) // 60
                secs       = s.get("time_taken_seconds", 0) % 60
                time_label = f"{mins}m {secs}s" if mins else f"{secs}s"
                badge      = "✅" if correct else "❌"
                label      = (f"{badge} **{s.get('question','')}** · "
                              f"{s.get('pattern','?')} · {s.get('difficulty','?')} · ⏱ {time_label}")

                with st.expander(label, expanded=False):
                    inner = st.tabs(["💡 Logic", "💻 Code", "🤖 AI Insight"])

                    with inner[0]:
                        logic = (s.get("logic") or "").strip()
                        st.markdown(logic) if logic else st.caption("No logic recorded.")

                    with inner[1]:
                        code = (s.get("code") or "").strip()
                        st.code(code, language="python") if code else st.caption("No code recorded.")

                    with inner[2]:
                        insight = (s.get("insight") or "").strip()
                        if insight:
                            st.markdown(insight)
                        else:
                            st.caption("No AI insight yet. Ensure ANTHROPIC_API_KEY is set on the server.")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB — ADD QUESTIONS  (admin only)
# ══════════════════════════════════════════════════════════════════════════════
if is_admin and ADMIN_IDX is not None:
    with tabs[ADMIN_IDX]:
        st.markdown(
            '<div style="background:#fff;border:2px dashed #c4b5fd;border-radius:16px;'
            'padding:28px 28px 12px;text-align:center;margin-bottom:16px;">'
            '<div style="font-size:1.5em;margin-bottom:6px;">📄</div>'
            '<div style="font-weight:700;font-size:1.05em;color:#3b0764;margin-bottom:4px;">Upload Markdown File</div>'
            '<div style="font-size:.85em;color:#7c3aed;margin-bottom:8px;">Parse DSA questions directly from your notes</div>'
            '</div>',
            unsafe_allow_html=True
        )
        uploaded_md = st.file_uploader("Choose a .md file", type=["md"], label_visibility="collapsed")
        upload_btn  = st.button("⬆ Upload and Add Questions", disabled=uploaded_md is None, type="primary")

        if upload_btn and uploaded_md:
            with st.spinner("Processing..."):
                try:
                    resp = requests.post(
                        f"{API_URL}/upload_md",
                        files={"file": (uploaded_md.name, uploaded_md.getvalue(), "text/markdown")},
                        headers=auth_headers(),
                    )
                    if resp.status_code == 200:
                        r = resp.json()
                        st.success(f"✅ Added **{r['added']}** new questions. Total: **{r['total']}**")
                        st.rerun()
                    elif resp.status_code == 403:
                        st.error("Admin access required.")
                    else:
                        st.error(f"Upload failed: {resp.text}")
                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — PRACTICE PANEL
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.active_qid:
    if 'start_timestamp' not in st.session_state:
        st.session_state.start_timestamp = time.time()

    elapsed = int(time.time() - st.session_state.start_timestamp)
    mins, secs = divmod(elapsed, 60)

    q = next((item for item in questions if item['id'] == st.session_state.active_qid), None)
    if q:
        acc_val   = float(q.get('accuracy') or 0)
        ef_val    = float(q.get('ease_factor') or 2.5)
        iv_val    = int(q.get('interval_days') or 0)
        acc_color = "#86efac" if acc_val >= 80 else "#fcd34d" if acc_val >= 60 else "#f9a8d4"

        with st.sidebar:
            # Header
            st.markdown(
                f'<div style="font-size:1em;font-weight:800;padding:6px 0 10px;'
                f'border-bottom:1px solid #2d1457;margin-bottom:12px;'
                f'background:linear-gradient(90deg,#c084fc,#f472b6);'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
                f'📝 {q["title"]}</div>',
                unsafe_allow_html=True
            )

            # Timer
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#2d1457,#4a1060);'
                f'border:1px solid #5b21b6;border-radius:14px;padding:10px 14px;'
                f'text-align:center;margin-bottom:10px;">'
                f'<div style="font-size:.6em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a78bfa;">Session Time</div>'
                f'<div style="font-size:2em;font-weight:800;letter-spacing:3px;'
                f'background:linear-gradient(135deg,#c084fc,#f472b6);'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
                f'{mins:02d}:{secs:02d}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Stats grid
            st.markdown(
                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:12px;">'
                f'  <div style="background:#2a1050;border:1px solid #3d1a72;border-radius:10px;padding:8px 6px;text-align:center;">'
                f'    <div style="font-size:.58em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#7c3aed;">Accuracy</div>'
                f'    <div style="font-size:.95em;font-weight:700;color:{acc_color};margin-top:2px;">{acc_val:.0f}%</div>'
                f'  </div>'
                f'  <div style="background:#2a1050;border:1px solid #3d1a72;border-radius:10px;padding:8px 6px;text-align:center;">'
                f'    <div style="font-size:.58em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#7c3aed;">Interval</div>'
                f'    <div style="font-size:.95em;font-weight:700;color:#e9d5ff;margin-top:2px;">{iv_val}d</div>'
                f'  </div>'
                f'  <div style="background:#2a1050;border:1px solid #3d1a72;border-radius:10px;padding:8px 6px;text-align:center;">'
                f'    <div style="font-size:.58em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#7c3aed;">EF</div>'
                f'    <div style="font-size:.95em;font-weight:700;color:#e9d5ff;margin-top:2px;">{ef_val:.2f}</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True
            )

            if q.get('suggestions'):
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#2d1457,#4a1060);'
                    f'border-left:3px solid #c084fc;border-radius:0 10px 10px 0;'
                    f'padding:8px 12px;font-size:.8em;color:#e9d5ff;margin-bottom:8px;line-height:1.6;">'
                    f'💡 {q["suggestions"]}</div>',
                    unsafe_allow_html=True
                )
            if q.get('my_gap_analysis'):
                st.markdown(
                    f'<div style="background:#2a1050;border-left:3px solid #f472b6;'
                    f'border-radius:0 10px 10px 0;padding:7px 12px;font-size:.8em;'
                    f'color:#fce7f3;margin-bottom:8px;line-height:1.6;">'
                    f'🔍 {q["my_gap_analysis"]}</div>',
                    unsafe_allow_html=True
                )

            # ── Input fields ─────────────────────────────────────────────────
            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">Logic &amp; Code</p>', unsafe_allow_html=True)
            new_logic = st.text_area("logic", value=q.get('logic',''), key="logic_input",    height=90,  label_visibility="collapsed", placeholder="Describe your approach step by step...")
            new_code  = st.text_area("code",  value=q.get('code',''),  key="code_input",     height=110, label_visibility="collapsed", placeholder="Paste or type your solution...")

            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">📝 Notes</p>', unsafe_allow_html=True)
            new_notes = st.text_area("notes", value=q.get('notes') or '', key="notes_input", height=80,  label_visibility="collapsed", placeholder="Key insight, pattern trick, edge case...")

            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">🔍 My Gap Analysis</p>', unsafe_allow_html=True)
            new_gap   = st.text_area("gap",   value=q.get('my_gap_analysis') or '', key="gap_input", height=80, label_visibility="collapsed", placeholder="Where did my thinking break down?")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # ── Buttons ──────────────────────────────────────────────────────
            col_save, col_close = st.columns(2)
            if col_save.button("💾 Save", type="primary", use_container_width=True):
                requests.post(f"{API_URL}/questions/{q['id']}/log",
                              json={"logic": new_logic, "code": new_code, "time_taken": elapsed},
                              headers=auth_headers())
                requests.patch(f"{API_URL}/questions/{q['id']}/notes",
                               json={"notes": new_notes, "my_gap_analysis": new_gap},
                               headers=auth_headers())
                st.success("Saved!")
                st.rerun()

            if col_close.button("✖ Close", use_container_width=True):
                st.session_state.active_qid = None
                st.session_state.pop('start_timestamp', None)
                st.rerun()

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("🤖 Validate with AI", key="ai_btn", use_container_width=True):
                with st.spinner("Analysing..."):
                    try:
                        resp = requests.post(f"{API_URL}/questions/{q['id']}/validate",
                                            headers=auth_headers())
                        if resp.status_code == 200:
                            res = resp.json()
                            uf  = res.get("updated_fields", {})
                            ok  = res.get("correct", False)
                            verdict_col = "#86efac" if ok else "#f9a8d4"
                            verdict_txt = "✅ Correct" if ok else "❌ Needs Work"
                            new_acc = uf.get('accuracy', '')
                            ac = "#86efac" if (new_acc or 0) >= 80 else "#fcd34d" if (new_acc or 0) >= 60 else "#f9a8d4"

                            st.markdown(
                                f'<div style="background:#2a1050;border:1px solid #3d1a72;border-radius:14px;padding:14px;margin-top:8px;">'
                                f'  <div style="font-weight:700;font-size:.95em;color:{verdict_col};margin-bottom:10px;">{verdict_txt}</div>'
                                f'  <div style="font-size:.6em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a855f7;margin-bottom:5px;">Gap Analysis</div>'
                                f'  <div style="font-size:.83em;color:#d8b4fe;margin-bottom:10px;line-height:1.6;">{res.get("gap_analysis","")}</div>'
                                f'  <div style="font-size:.6em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a855f7;margin-bottom:5px;">Suggestion</div>'
                                f'  <div style="border-left:3px solid #f472b6;padding:7px 10px;background:#3d1a72;border-radius:0 8px 8px 0;font-size:.83em;color:#fce7f3;margin-bottom:10px;">{res.get("correction_suggestion","")}</div>'
                                f'  <div style="font-size:.6em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#a855f7;margin-bottom:6px;">Updated Metrics</div>'
                                f'  <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #3d1a72;font-size:.8em;"><span style="color:#9ca3af;">Accuracy</span><span style="color:{ac};font-weight:600;">{new_acc}%</span></div>'
                                f'  <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #3d1a72;font-size:.8em;"><span style="color:#9ca3af;">Status</span><span style="color:#e9d5ff;font-weight:600;">{uf.get("revision_status","")}</span></div>'
                                f'  <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #3d1a72;font-size:.8em;"><span style="color:#9ca3af;">Next Revision</span><span style="color:#e9d5ff;font-weight:600;">{uf.get("next_revision","")}</span></div>'
                                f'  <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #3d1a72;font-size:.8em;"><span style="color:#9ca3af;">Ease Factor</span><span style="color:#e9d5ff;font-weight:600;">{uf.get("ease_factor","")}</span></div>'
                                f'  <div style="display:flex;justify-content:space-between;padding:5px 0;font-size:.8em;"><span style="color:#9ca3af;">Interval</span><span style="color:#e9d5ff;font-weight:600;">{uf.get("interval_days","")}d</span></div>'
                                f'  <div style="margin-top:8px;font-size:.8em;color:#c084fc;line-height:1.5;">{uf.get("suggestions","")}</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                        else:
                            st.error("AI validation failed.")
                    except Exception as e:
                        st.error(f"Error: {e}")
