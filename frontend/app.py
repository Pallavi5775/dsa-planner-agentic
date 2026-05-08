# -*- coding: utf-8 -*-
import os
import calendar as cal_lib
import streamlit as st
import requests
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh

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

# ── Code editor (streamlit-ace) — graceful fallback to styled textarea ────────
try:
    from streamlit_ace import st_ace
    _ACE_AVAILABLE = True
except ImportError:
    _ACE_AVAILABLE = False


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
    min-width: 440px !important;
    max-width: 440px !important;
}
[data-testid="stSidebar"] > div:first-child {
    min-width: 440px !important;
    padding-top: .8rem;
}
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
    font-size: .95em !important;
    line-height: 1.6 !important;
    padding: 10px 12px !important;
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

/* ── Code editor fallback textarea ── */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
textarea[data-testid="stTextArea"],
.code-editor-area textarea {
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace !important;
    font-size: 13px !important;
    background: #1e1e1e !important;
    color: #d4d4d4 !important;
    border: 1.5px solid #3c3c3c !important;
    border-radius: 8px !important;
    line-height: 1.65 !important;
    caret-color: #c084fc !important;
}
textarea[data-testid="stTextArea"]:focus,
.code-editor-area textarea:focus {
    border-color: #7c3aed !important;
    box-shadow: 0 0 0 2px rgba(124,58,237,.3) !important;
    outline: none !important;
}

/* Ace editor container */
.ace-editor-wrap .ace_editor {
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
}
</style>
""", unsafe_allow_html=True)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def fetch_activity():
    try:
        tz_name = st.query_params.get("tz", "UTC")
        r = requests.get(f"{API_URL}/activity", headers=auth_headers(),
                         params={"tz": tz_name}, timeout=8)
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

# ── TIMEZONE DETECTION ────────────────────────────────────────────────────────
# JS writes the browser's IANA timezone into ?tz= so Python can read it on the
# next rerun (any button click, etc.).  Falls back to UTC if unavailable.
st.markdown("""
<script>
(function() {
    var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    var url = new URL(window.parent.location);
    if (url.searchParams.get('tz') !== tz) {
        url.searchParams.set('tz', tz);
        window.parent.history.replaceState({}, '', url);
    }
})();
</script>
""", unsafe_allow_html=True)


def _user_tz() -> ZoneInfo:
    tz_name = st.query_params.get("tz", "UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _local_now() -> datetime:
    return datetime.now(_user_tz())


def _local_today() -> str:
    return _local_now().strftime("%Y-%m-%d")


# ── INIT ──────────────────────────────────────────────────────────────────────
for key, val in [("active_qid", None), ("view_last_qid", None), ("cal_year", _local_now().year), ("cal_month", _local_now().month)]:
    if key not in st.session_state:
        st.session_state[key] = val


# ── NOTIFICATION HELPERS ───────────────────────────────────────────────────────
def _fetch_notifications():
    """Fetch in-app notifications from the API (cached per session until invalidated)."""
    if "notifs_cache" not in st.session_state:
        try:
            r = requests.get(f"{API_URL}/me/notifications", headers=auth_headers(), timeout=5)
            st.session_state.notifs_cache = r.json() if r.status_code == 200 else []
        except Exception:
            st.session_state.notifs_cache = []
    return st.session_state.notifs_cache


def _show_in_app_toasts():
    """Show st.toast() for unread notifications once per session load."""
    if st.session_state.get("toasts_shown"):
        return
    notifs = _fetch_notifications()
    unread = [n for n in notifs if not n.get("is_read")]
    icons = {"revisions": "📚", "streak": "🔥", "mastery": "🏆"}
    for n in unread[:3]:  # cap at 3 to avoid flooding
        icon = icons.get(n.get("type", ""), "🔔")
        st.toast(f"{icon} {n['message']}", icon=icon)
    st.session_state.toasts_shown = True


_show_in_app_toasts()


def _notification_bell():
    notifs = _fetch_notifications()
    unread_count = sum(1 for n in notifs if not n.get("is_read"))

    label = f"🔔  {unread_count} new" if unread_count else "🔔  Inbox"
    if st.button(label, key="notif_bell_btn", use_container_width=True):
        st.session_state.show_notif_panel = not st.session_state.get("show_notif_panel", False)

    if st.session_state.get("show_notif_panel"):
        _render_notification_panel(notifs)


def _render_notification_panel(notifs: list):
    type_icons = {"revisions": "📚", "streak": "🔥", "mastery": "🏆", "info": "ℹ️"}
    unread_count = sum(1 for n in notifs if not n.get("is_read"))

    rows_html = ""
    for n in notifs[:10]:
        icon  = type_icons.get(n.get("type", "info"), "🔔")
        unread = not n.get("is_read")
        ts    = n.get("created_at", "")[:16].replace("T", " ")
        dot   = (
            '<span style="display:inline-block;width:7px;height:7px;background:#a855f7;'
            'border-radius:50%;flex-shrink:0;margin-top:5px;"></span>'
            if unread else
            '<span style="display:inline-block;width:7px;height:7px;flex-shrink:0;"></span>'
        )
        row_bg   = "background:#2a0a4a;" if unread else ""
        msg_col  = "#e9d5ff" if unread else "#7c5cbc"
        rows_html += (
            f'<div style="display:flex;align-items:flex-start;gap:10px;padding:11px 16px;'
            f'border-bottom:1px solid #2d1457;{row_bg}">'
            f'  <span style="font-size:1.1em;margin-top:1px;">{icon}</span>'
            f'  <div style="flex:1;min-width:0;">'
            f'    <div style="font-size:.82em;color:{msg_col};line-height:1.55;">{n["message"]}</div>'
            f'    <div style="font-size:.65em;color:#4c1d95;margin-top:3px;">{ts} UTC</div>'
            f'  </div>'
            f'  {dot}'
            f'</div>'
        )

    if not rows_html:
        rows_html = (
            '<div style="padding:28px 16px;text-align:center;color:#6d28d9;font-size:.85em;">'
            '🎉 All caught up — no notifications yet.</div>'
        )

    st.markdown(
        f'<div style="background:#1a0933;border:1.5px solid #3d1a72;border-radius:16px;'
        f'overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.5);margin-top:6px;">'
        f'  <div style="padding:12px 16px;border-bottom:1px solid #2d1457;'
        f'              display:flex;justify-content:space-between;align-items:center;">'
        f'    <span style="color:#f3e8ff;font-weight:700;font-size:.88em;letter-spacing:.2px;">'
        f'      🔔 Notifications</span>'
        f'    <span style="background:#3d1a72;color:#c084fc;border-radius:20px;'
        f'                 padding:2px 10px;font-size:.72em;font-weight:700;">'
        f'      {unread_count} unread</span>'
        f'  </div>'
        f'  {rows_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if unread_count:
        if st.button("✓ Mark all as read", key="notif_clear_all", use_container_width=True):
            try:
                requests.patch(f"{API_URL}/me/notifications/read-all", headers=auth_headers(), timeout=5)
                st.session_state.pop("notifs_cache", None)
                st.session_state.show_notif_panel = False
                st.rerun()
            except Exception:
                pass


# ── BROWSER PUSH NOTIFICATION REQUEST ─────────────────────────────────────────
# Requests the Notification API permission once; shows browser alerts for unread items
# Only fires when there are unread notifications so the popup isn't annoying on every load.
_unread_msgs = [n["message"] for n in _fetch_notifications() if not n.get("is_read")][:3]
if _unread_msgs and not st.session_state.get("browser_notif_requested"):
    _msgs_js = str(_unread_msgs).replace("'", "\\'").replace('"', '\\"')
    st.markdown(f"""
<script>
(function() {{
    var msgs = {_unread_msgs};
    function showNotifs() {{
        msgs.forEach(function(m) {{
            new Notification("🎯 DSA Revision Planner", {{ body: m, icon: "" }});
        }});
    }}
    if (Notification.permission === "granted") {{
        showNotifs();
    }} else if (Notification.permission !== "denied") {{
        Notification.requestPermission().then(function(p) {{
            if (p === "granted") showNotifs();
        }});
    }}
}})();
</script>
""", unsafe_allow_html=True)
    st.session_state.browser_notif_requested = True


# ── TOP BAR ───────────────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([0.65, 0.35])
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
    btn_left, btn_right = st.columns(2)
    with btn_left:
        _notification_bell()
    with btn_right:
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
tab_labels = ["📋 Questions", "📅 Calendar", "⚡ Activity", "⚙ Settings", "📚 Patterns"]
if has_github:
    tab_labels.append("📖 Journal")
if is_admin:
    tab_labels.append("➕ Add Questions")

JOURNAL_IDX  = tab_labels.index("📖 Journal") if has_github else None
ADMIN_IDX    = tab_labels.index("➕ Add Questions") if is_admin else None
PATTERNS_IDX = tab_labels.index("📚 Patterns")

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
        today_str = _local_today()
        week_str  = (_local_now() + timedelta(days=7)).strftime("%Y-%m-%d")

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
            hint_icon = '<span title="Hint available" style="font-size:.75em;margin-left:4px;">💡</span>' if row.get('hint') else ""
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
                f'  <div style="font-weight:700;font-size:.97em;color:#1e1b4b;margin-bottom:8px;">{row["title"]}{hint_icon}</div>'
                f'  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">'
                f'    <span>{acc_bar_html(acc_val)}</span>'
                f'    <span style="font-size:.77em;color:#6b7280;">📅 {next_rev}</span>'
                f'    <span style="font-size:.77em;color:#6b7280;">⏱ {total_t}m</span>'
                f'  </div>'
                f'</div>'
            )

            col_card, col_p, col_v = st.columns([0.72, 0.14, 0.14])
            with col_card:
                st.markdown(card_html, unsafe_allow_html=True)
            with col_p:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Practice →", key=f"sel_{row['id']}", use_container_width=True):
                    st.session_state.active_qid   = int(row['id'])
                    st.session_state.view_last_qid = None
                    st.session_state.pop('start_timestamp', None)
                    st.rerun()
            with col_v:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Last Record", key=f"last_{row['id']}", use_container_width=True):
                    st.session_state.view_last_qid = int(row['id'])
                    st.session_state.active_qid    = None
                    st.session_state.pop('start_timestamp', None)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    today_str = _local_today()

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

    # ── Charts row 1: Sessions over time + Accuracy trend ────────────────────
    import plotly.graph_objects as go

    PURPLE_PALETTE = ["#7c3aed", "#a855f7", "#db2777", "#6366f1", "#ec4899",
                      "#0ea5e9", "#f97316", "#10b981", "#f59e0b", "#14b8a6"]

    def _chart_layout(fig, title):
        fig.update_layout(
            title=dict(text=title, font=dict(size=13, color="#4c1d95", family="Inter,sans-serif"), x=0),
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=8, r=8, t=36, b=8),
            font=dict(family="Inter,sans-serif", size=11, color="#4c1d95"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=10)),
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="#f0ebff", zeroline=False, tickfont=dict(size=10)),
        )
        return fig

    ch1, ch2 = st.columns(2)

    # Chart 1 — Sessions over time (area chart, last 60 days)
    with ch1:
        if sbd:
            from datetime import date as _date, timedelta as _td
            day60 = (_date.today() - _td(days=59)).strftime("%Y-%m-%d")
            dates_sorted = sorted(d for d in sbd if d >= day60)
            # fill gaps with 0
            if dates_sorted:
                all_dates, all_counts = [], []
                cur_d = _date.fromisoformat(dates_sorted[0])
                end_d = _date.today()
                while cur_d <= end_d:
                    s = cur_d.strftime("%Y-%m-%d")
                    all_dates.append(s)
                    all_counts.append(sbd.get(s, 0))
                    cur_d += _td(days=1)
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=all_dates, y=all_counts, mode="lines",
                    fill="tozeroy",
                    line=dict(color="#7c3aed", width=2),
                    fillcolor="rgba(124,58,237,0.12)",
                    name="Sessions",
                ))
                fig1 = _chart_layout(fig1, "Sessions over time (last 60 days)")
                st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No session data yet.</p>', unsafe_allow_html=True)

    # Chart 2 — Accuracy trend (correct vs wrong per day)
    with ch2:
        dc = act.get("daily_correct", {})
        dw = act.get("daily_wrong", {})
        all_ac_dates = sorted(set(dc) | set(dw))
        if all_ac_dates:
            correct_vals = [dc.get(d, 0) for d in all_ac_dates]
            wrong_vals   = [dw.get(d, 0) for d in all_ac_dates]
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=all_ac_dates, y=correct_vals, mode="lines+markers",
                name="Correct", line=dict(color="#10b981", width=2),
                marker=dict(size=5),
            ))
            fig2.add_trace(go.Scatter(
                x=all_ac_dates, y=wrong_vals, mode="lines+markers",
                name="Wrong", line=dict(color="#db2777", width=2),
                marker=dict(size=5),
            ))
            fig2 = _chart_layout(fig2, "Accuracy trend — correct vs wrong per day")
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No accuracy data yet.</p>', unsafe_allow_html=True)

    # ── Charts row 2: Pattern donut + Time per pattern ────────────────────────
    ch3, ch4 = st.columns(2)

    # Chart 3 — Pattern distribution donut
    with ch3:
        pc = act.get("pattern_counts", {})
        if pc:
            top_pc = dict(list(pc.items())[:10])
            fig3 = go.Figure(go.Pie(
                labels=list(top_pc.keys()),
                values=list(top_pc.values()),
                hole=0.5,
                marker=dict(colors=PURPLE_PALETTE),
                textfont=dict(size=10),
                hovertemplate="%{label}: %{value} sessions<extra></extra>",
            ))
            fig3 = _chart_layout(fig3, "Practice by pattern (top 10)")
            fig3.update_layout(
                showlegend=True,
                legend=dict(orientation="v", font=dict(size=9), x=1, y=0.5),
            )
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No pattern data yet.</p>', unsafe_allow_html=True)

    # Chart 4 — Time spent per pattern (horizontal bar, top 10)
    with ch4:
        tbp = act.get("time_by_pattern", {})
        if tbp:
            top_tbp = dict(list(tbp.items())[:10])
            patterns = list(reversed(list(top_tbp.keys())))
            minutes  = [round(top_tbp[p] / 60, 1) for p in patterns]
            fig4 = go.Figure(go.Bar(
                x=minutes, y=patterns, orientation="h",
                marker=dict(
                    color=minutes,
                    colorscale=[[0, "#ddd6fe"], [0.5, "#a855f7"], [1, "#7c3aed"]],
                    showscale=False,
                ),
                text=[f"{m}m" for m in minutes],
                textposition="outside",
                hovertemplate="%{y}: %{x}m<extra></extra>",
            ))
            fig4 = _chart_layout(fig4, "Time spent per pattern (minutes, top 10)")
            fig4.update_layout(
                yaxis=dict(showgrid=False, tickfont=dict(size=10)),
                xaxis_title="minutes",
                margin=dict(l=8, r=40, t=36, b=8),
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No time data yet.</p>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Recent sessions feed ──────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:.7em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
        'color:#7c3aed;margin-bottom:10px;">📋 Recent Sessions</div>',
        unsafe_allow_html=True
    )
    recent = act.get("recent_sessions", [])
    if not recent:
        st.markdown('<p style="color:#c4b5fd;font-size:.88em;">No sessions yet — start practicing!</p>', unsafe_allow_html=True)
    else:
        feed_col, _ = st.columns([0.6, 0.4])
        with feed_col:
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
                    ok      = s.get("correct", True)
                    ok_icon = "✅" if ok else "❌"
                    ok_col  = "#15803d" if ok else "#be123c"
                    ok_bg   = "#dcfce7" if ok else "#fee2e2"
                    mins    = max(1, (s.get("time_taken") or 0) // 60)
                    pattern = s.get("pattern", "")
                    title   = s.get("question_title", "")
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

    # ── Notification Settings ─────────────────────────────────────────────────
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:.7em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
        'color:#7c3aed;margin-bottom:16px;">Notification Settings</p>',
        unsafe_allow_html=True
    )

    # Load existing settings once
    if "notif_settings_loaded" not in st.session_state:
        try:
            _ns = requests.get(f"{API_URL}/me/notification-settings", headers=auth_headers(), timeout=5)
            if _ns.status_code == 200:
                _nsd = _ns.json()
                st.session_state.notif_email_enabled = _nsd.get("email_notif_enabled", False)
                st.session_state.notif_tg_enabled = _nsd.get("telegram_notif_enabled", False)
                st.session_state.notif_tg_chat_id = _nsd.get("telegram_chat_id") or ""
                st.session_state.notif_hour = _nsd.get("notify_hour", 8)
        except Exception:
            pass
        st.session_state.notif_settings_loaded = True

    st.markdown(
        '<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:16px;'
        'padding:24px 28px;max-width:520px;box-shadow:0 2px 8px rgba(124,58,237,.07);">',
        unsafe_allow_html=True
    )

    st.markdown(
        '<p style="font-size:.82em;color:#6b7280;margin-bottom:18px;">'
        'Get reminders for pending revisions, streak warnings, and mastery updates.</p>',
        unsafe_allow_html=True
    )

    # --- Daily digest hour ---
    notif_hour = st.slider(
        "Daily digest time (UTC hour)", min_value=0, max_value=23,
        value=int(st.session_state.get("notif_hour", 8)),
        key="notif_hour_slider",
        help="The UTC hour at which your daily digest is sent (e.g. 8 = 08:00 UTC)"
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # --- Email toggle ---
    email_enabled = st.toggle(
        "📧 Email notifications",
        value=bool(st.session_state.get("notif_email_enabled", False)),
        key="notif_email_toggle",
    )

    # --- Telegram toggle + chat ID ---
    tg_enabled = st.toggle(
        "✈️ Telegram notifications",
        value=bool(st.session_state.get("notif_tg_enabled", False)),
        key="notif_tg_toggle",
    )
    tg_chat_id = ""
    if tg_enabled:
        tg_chat_id = st.text_input(
            "Telegram Chat ID",
            value=st.session_state.get("notif_tg_chat_id", ""),
            key="notif_tg_chat_id_input",
            placeholder="e.g. 123456789",
        )
        st.markdown(
            '<div style="background:#2a1050;border-left:3px solid #a855f7;border-radius:0 8px 8px 0;'
            'padding:10px 14px;font-size:.76em;color:#e9d5ff;line-height:1.8;margin-top:2px;">'
            '<b style="color:#c084fc;">How to find your Chat ID:</b><br>'
            '1. Open Telegram → search <b>@dsa_planner_bot</b> → send <code>/start</code><br>'
            '2. Then open <b>@userinfobot</b> → send <code>/start</code><br>'
            '3. It replies with <b>Your user ID: 123456789</b> — paste that number above'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    if st.button("💾 Save Notification Settings", type="primary", key="save_notif_btn"):
        payload = {
            "email_notif_enabled": email_enabled,
            "telegram_notif_enabled": tg_enabled,
            "telegram_chat_id": tg_chat_id if tg_enabled else "",
            "notify_hour": notif_hour,
        }
        try:
            _r = requests.patch(
                f"{API_URL}/me/notification-settings",
                json=payload,
                headers=auth_headers(),
                timeout=5,
            )
            if _r.status_code == 200:
                st.session_state.notif_email_enabled = email_enabled
                st.session_state.notif_tg_enabled = tg_enabled
                st.session_state.notif_tg_chat_id = tg_chat_id
                st.session_state.notif_hour = notif_hour
                st.success("Notification settings saved!")
            else:
                st.error("Failed to save notification settings.")
        except Exception as e:
            st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — PATTERN NOTES  (first-time study reference)
# ══════════════════════════════════════════════════════════════════════════════
with tabs[PATTERNS_IDX]:

    # ── load saved pattern notes once per session ─────────────────────────────
    if "pattern_notes_loaded" not in st.session_state:
        try:
            _pn_r = requests.get(f"{API_URL}/pattern-notes", headers=auth_headers(), timeout=6)
            st.session_state.pattern_notes = _pn_r.json() if _pn_r.status_code == 200 else {}
        except Exception:
            st.session_state.pattern_notes = {}
        st.session_state.pattern_notes_loaded = True

    # ── helpers ───────────────────────────────────────────────────────────────
    def _sec(title):
        st.markdown(
            f'<p style="font-size:.62em;font-weight:700;letter-spacing:1px;'
            f'text-transform:uppercase;color:#7c3aed;margin:18px 0 6px;">{title}</p>',
            unsafe_allow_html=True,
        )

    def _bullets(items, color="#4c1d95"):
        html = "".join(
            f'<li style="margin-bottom:4px;color:#374151;">{it}</li>' for it in items
        )
        st.markdown(
            f'<ul style="padding-left:18px;margin:0;font-size:.88em;line-height:1.7;">{html}</ul>',
            unsafe_allow_html=True,
        )

    def _overview(tagline, mental_model, complexity):
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#ede9fe,#fce7f3);'
            f'border:1.5px solid #c4b5fd;border-radius:14px;padding:16px 20px;margin-bottom:6px;">'
            f'<div style="font-size:.82em;font-style:italic;color:#5b21b6;margin-bottom:8px;">{tagline}</div>'
            f'<div style="font-size:.88em;color:#1e1b4b;line-height:1.7;">{mental_model}</div>'
            f'<div style="margin-top:10px;font-size:.78em;color:#7c3aed;font-weight:600;">'
            f'⏱ Typical complexity: {complexity}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    def _technique(icon, name, steps, code, insight, complexity=""):
        with st.expander(f"{icon}  {name}", expanded=False):
            _sec("Algorithm Steps")
            _bullets(steps)
            _sec("Code Template")
            st.code(code, language="python")
            if insight:
                st.markdown(
                    f'<div style="background:#fdf4ff;border-left:3px solid #a855f7;'
                    f'border-radius:0 8px 8px 0;padding:8px 12px;font-size:.83em;'
                    f'color:#581c87;line-height:1.6;margin-top:6px;">💡 {insight}</div>',
                    unsafe_allow_html=True,
                )
            if complexity:
                st.markdown(
                    f'<p style="font-size:.75em;color:#6b7280;margin-top:6px;">⏱ {complexity}</p>',
                    unsafe_allow_html=True,
                )

    def _pattern_footer(pattern_name):
        saved = st.session_state.get("pattern_notes", {}).get(pattern_name, {})
        saved_memo  = saved.get("memory_techniques", "")
        saved_notes = saved.get("notes", "")

        st.markdown("<hr style='border:none;border-top:1px solid #ede9fe;margin:20px 0 4px;'>", unsafe_allow_html=True)

        # ── Memory Tricks ─────────────────────────────────────────────────────
        _sec("🧠 Memory Tricks")

        if saved_memo:
            st.markdown(
                f'<div style="background:#fdf4ff;border:1.5px solid #e9d5ff;border-radius:12px;'
                f'padding:12px 16px;font-size:.86em;color:#3b0764;line-height:1.8;'
                f'white-space:pre-wrap;">{saved_memo}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p style="font-size:.82em;color:#a78bfa;font-style:italic;">No memory tricks saved yet — generate some below.</p>',
                unsafe_allow_html=True,
            )

        gen_col, _ = st.columns([0.35, 0.65])
        if gen_col.button("✨ Generate Memory Tricks", key=f"gen_memo_{pattern_name}", use_container_width=True):
            with st.spinner("Generating..."):
                try:
                    resp = requests.post(
                        f"{API_URL}/pattern-chat",
                        json={"pattern": pattern_name, "message": "", "generate_memo": True},
                        headers=auth_headers(), timeout=20,
                    )
                    memo = resp.json().get("reply", "") if resp.status_code == 200 else "AI unavailable."
                    requests.patch(
                        f"{API_URL}/pattern-notes",
                        json={"pattern": pattern_name, "memory_techniques": memo},
                        headers=auth_headers(), timeout=8,
                    )
                    pn = st.session_state.get("pattern_notes", {})
                    pn.setdefault(pattern_name, {})["memory_techniques"] = memo
                    st.session_state.pattern_notes = pn
                    st.session_state.pop("pattern_notes_loaded", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # ── My Notes ──────────────────────────────────────────────────────────
        _sec("📝 My Notes")
        new_notes = st.text_area(
            f"my_notes_{pattern_name}", value=saved_notes,
            key=f"pnotes_{pattern_name}", height=130,
            label_visibility="collapsed",
            placeholder=f"Write your own observations, tricks, or reminders for the {pattern_name} pattern…",
        )
        save_col, _ = st.columns([0.22, 0.78])
        if save_col.button("💾 Save Notes", key=f"save_pnotes_{pattern_name}", use_container_width=True):
            try:
                requests.patch(
                    f"{API_URL}/pattern-notes",
                    json={"pattern": pattern_name, "notes": new_notes},
                    headers=auth_headers(), timeout=8,
                )
                pn = st.session_state.get("pattern_notes", {})
                pn.setdefault(pattern_name, {})["notes"] = new_notes
                st.session_state.pattern_notes = pn
                st.success("Notes saved!")
            except Exception as e:
                st.error(f"Error: {e}")

        # ── AI Chat ───────────────────────────────────────────────────────────
        _sec("🤖 Ask AI Tutor")
        chat_key = f"pchat_{pattern_name}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []
        chat_msgs = st.session_state[chat_key]

        if chat_msgs:
            bubbles = ""
            for msg in chat_msgs[-8:]:
                if msg["role"] == "user":
                    bubbles += (
                        f'<div style="display:flex;justify-content:flex-end;margin-bottom:6px;">'
                        f'<div style="background:#4c1d95;color:#e9d5ff;border-radius:14px 14px 2px 14px;'
                        f'padding:7px 12px;font-size:.82em;max-width:80%;line-height:1.5;">'
                        f'{msg["content"]}</div></div>'
                    )
                else:
                    bubbles += (
                        f'<div style="display:flex;justify-content:flex-start;margin-bottom:6px;">'
                        f'<div style="background:#f5f3ff;border:1px solid #c4b5fd;color:#1e1b4b;'
                        f'border-radius:14px 14px 14px 2px;'
                        f'padding:7px 12px;font-size:.82em;max-width:80%;line-height:1.5;white-space:pre-wrap;">'
                        f'{msg["content"]}</div></div>'
                    )
            st.markdown(
                f'<div style="background:#fafafa;border:1.5px solid #ede9fe;border-radius:12px;'
                f'padding:12px;margin-bottom:8px;max-height:260px;overflow-y:auto;">'
                f'{bubbles}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<p style="font-size:.8em;color:#a78bfa;font-style:italic;margin-bottom:6px;">'
                f'Ask anything about the {pattern_name} pattern — concepts, edge cases, when to use it…</p>',
                unsafe_allow_html=True,
            )

        ci_col, cb_col = st.columns([0.78, 0.22])
        user_q = ci_col.text_input(
            "pchat_in", key=f"pchat_input_{pattern_name}",
            label_visibility="collapsed",
            placeholder="e.g. When should I prefer BFS over DFS?",
        )
        ask = cb_col.button("Ask", key=f"pchat_ask_{pattern_name}", use_container_width=True)

        if ask and user_q.strip():
            chat_msgs.append({"role": "user", "content": user_q.strip()})
            try:
                resp = requests.post(
                    f"{API_URL}/pattern-chat",
                    json={"pattern": pattern_name, "message": user_q.strip(), "generate_memo": False},
                    headers=auth_headers(), timeout=20,
                )
                reply = resp.json().get("reply", "Sorry, no response.") if resp.status_code == 200 else "AI unavailable."
            except Exception:
                reply = "Could not reach AI. Check your connection."
            chat_msgs.append({"role": "assistant", "content": reply})
            st.rerun()

    # ── pattern tabs ─────────────────────────────────────────────────────────
    p_tabs = st.tabs(["🔢 Array", "🧮 DP", "🕸 Graphs", "💰 Greedy", "⛰ Heap", "📚 Stack", "🔤 String"])

    # ═══════════════════════════════════════════════════════
    #  ARRAY
    # ═══════════════════════════════════════════════════════
    with p_tabs[0]:
        _overview(
            "Arrays are the backbone of DSA — master these four core techniques and 60% of problems become solvable.",
            "Most array problems reduce to one of: shrinking a window, moving pointers inward, precomputing prefix info, or binary-searching on a sorted/monotone answer space.",
            "O(n) for most patterns; O(n log n) when sorting is needed first",
        )
        _sec("Recognition Clues")
        _bullets([
            "Subarray / substring with a property (sum, distinct count) → <b>Sliding Window</b>",
            "Find pair / remove duplicates in sorted array → <b>Two Pointers</b>",
            "Range sum queries, equilibrium point → <b>Prefix Sum</b>",
            "Search in sorted / rotated array, find first/last occurrence → <b>Binary Search</b>",
            "Max sum contiguous subarray, max profit → <b>Kadane's</b>",
        ])
        _sec("Techniques")
        _technique(
            "🪟", "Sliding Window",
            [
                "Use when you need a contiguous subarray satisfying a condition.",
                "Fixed-size window: move both left and right together (right − left == k).",
                "Variable window: expand right freely; shrink left when the window violates the condition.",
                "Track the answer at every valid window state.",
            ],
            '''\
def max_sum_subarray_k(arr, k):
    window_sum = sum(arr[:k])
    best = window_sum
    for i in range(k, len(arr)):
        window_sum += arr[i] - arr[i - k]   # slide
        best = max(best, window_sum)
    return best

# Variable window — longest subarray with sum <= target
def longest_subarray(arr, target):
    left = total = best = 0
    for right in range(len(arr)):
        total += arr[right]
        while total > target:          # shrink until valid
            total -= arr[left]; left += 1
        best = max(best, right - left + 1)
    return best''',
            "The window shrinks from the left only when the invariant breaks — never skip ahead.",
            "Time O(n), Space O(1)",
        )
        _technique(
            "👉👈", "Two Pointers",
            [
                "Works on SORTED arrays (or arrays you can sort without losing info).",
                "Place one pointer at start, one at end.",
                "If arr[l] + arr[r] < target → move l right (need larger).",
                "If arr[l] + arr[r] > target → move r left (need smaller).",
                "Stop when l >= r.",
            ],
            '''\
def two_sum_sorted(arr, target):
    l, r = 0, len(arr) - 1
    while l < r:
        s = arr[l] + arr[r]
        if s == target:   return [l, r]
        elif s < target:  l += 1
        else:             r -= 1
    return []

# Remove duplicates in-place (slow/fast pointer variant)
def remove_duplicates(arr):
    if not arr: return 0
    slow = 0
    for fast in range(1, len(arr)):
        if arr[fast] != arr[slow]:
            slow += 1
            arr[slow] = arr[fast]
    return slow + 1''',
            "For 3Sum: fix one element with a loop, then run two-pointer on the rest. Sort first — O(n²) total.",
            "Time O(n) after O(n log n) sort",
        )
        _technique(
            "➕", "Prefix Sum",
            [
                "Build prefix[] where prefix[i] = sum of arr[0..i-1].",
                "Range sum [l, r] = prefix[r+1] - prefix[l] in O(1).",
                "For 2D grids, build a 2D prefix sum table.",
                "Combine with a hash map to find subarrays with a target sum.",
            ],
            '''\
# 1-D prefix sum
prefix = [0] * (len(arr) + 1)
for i, v in enumerate(arr):
    prefix[i+1] = prefix[i] + v
range_sum = lambda l, r: prefix[r+1] - prefix[l]

# Count subarrays with sum == k  (hash map trick)
def subarray_sum_k(arr, k):
    count = 0
    running = 0
    seen = {0: 1}          # prefix_sum → frequency
    for v in arr:
        running += v
        count += seen.get(running - k, 0)
        seen[running] = seen.get(running, 0) + 1
    return count''',
            "The hash map trick turns O(n²) brute-force subarray search into O(n).",
            "Time O(n), Space O(n)",
        )
        _technique(
            "🔍", "Binary Search",
            [
                "Classic: sorted array, find target → O(log n).",
                "Rotated array: decide which half is sorted; search there.",
                "'Binary search on answer': if answer space is monotone (feasible/not), binary search on it.",
                "Template: lo=0, hi=n-1; while lo<=hi; mid=(lo+hi)//2.",
            ],
            '''\
# Classic
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:   return mid
        elif arr[mid] < target:  lo = mid + 1
        else:                    hi = mid - 1
    return -1

# Binary search on answer — "minimum max pages" style
def feasible(arr, k, mid): ...   # True if mid is achievable with k splits

def min_max_split(arr, k):
    lo, hi = max(arr), sum(arr)
    ans = hi
    while lo <= hi:
        mid = (lo + hi) // 2
        if feasible(arr, k, mid):
            ans = mid; hi = mid - 1
        else:
            lo = mid + 1
    return ans''',
            "When asked for 'minimum of maximums' or 'maximum of minimums', binary search on the answer.",
        )
        _technique(
            "📈", "Kadane's Algorithm",
            [
                "Maximum sum contiguous subarray in O(n).",
                "At each index, decide: extend the current subarray or start fresh.",
                "current = max(arr[i], current + arr[i])",
                "Track global best = max(best, current).",
            ],
            '''\
def kadane(arr):
    current = best = arr[0]
    for v in arr[1:]:
        current = max(v, current + v)
        best = max(best, current)
    return best

# Variant: also return start/end indices
def kadane_with_indices(arr):
    best = current = arr[0]
    start = end = temp_start = 0
    for i in range(1, len(arr)):
        if arr[i] > current + arr[i]:
            current = arr[i]; temp_start = i
        else:
            current += arr[i]
        if current > best:
            best = current; start = temp_start; end = i
    return best, start, end''',
            "If all elements are negative, Kadane correctly returns the single largest element.",
            "Time O(n), Space O(1)",
        )
        _sec("Common Pitfalls")
        _bullets([
            "Sliding window on unsorted arrays: can't use two-pointer — values don't shrink monotonically.",
            "Off-by-one in binary search: use <code>lo <= hi</code> for exact match; <code>lo < hi</code> when converging to a boundary.",
            "Prefix sum index shift: prefix[0]=0, so range sum is prefix[r+1]−prefix[l], not prefix[r]−prefix[l].",
            "Kadane with all negatives: initialise both <code>current</code> and <code>best</code> to arr[0], not 0.",
        ])
        _pattern_footer("Array")

    # ═══════════════════════════════════════════════════════
    #  DYNAMIC PROGRAMMING
    # ═══════════════════════════════════════════════════════
    with p_tabs[1]:
        _overview(
            "DP = recursion + memoisation. If a brute-force recursion recomputes the same subproblem, cache it.",
            "The art of DP is defining the <b>state</b>: what exactly does dp[i] (or dp[i][j]) represent? "
            "Once that's clear, write the recurrence, set base cases, and decide top-down (memo) or bottom-up (table).",
            "Usually O(n²) or O(n·W) time, O(n) or O(n²) space",
        )
        _sec("Recognition Clues")
        _bullets([
            "Problem asks for <b>count / maximum / minimum</b> of ways to reach a goal.",
            "You make a sequence of choices and later choices depend on earlier ones.",
            "Brute-force recursion has <b>overlapping subproblems</b> (same args seen twice).",
            "Optimal substructure: optimal solution built from optimal sub-solutions.",
            "Keywords: 'how many ways', 'minimum cost', 'longest', 'can you reach'.",
        ])
        _sec("Techniques")
        _technique(
            "🪜", "1-D DP (Climbing Stairs / Fibonacci-like)",
            [
                "State: dp[i] = answer for the first i elements.",
                "Recurrence: look back 1 or 2 steps (or k steps).",
                "Base cases: dp[0], dp[1] set by hand.",
                "Often space-optimisable to O(1) using two variables.",
            ],
            '''\
# Climbing stairs — distinct ways to reach step n
def climb_stairs(n):
    if n <= 2: return n
    a, b = 1, 2
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b

# Minimum cost to reach top (pay cost[i] to leave step i)
def min_cost_climbing(cost):
    n = len(cost)
    dp = [0] * (n + 1)
    for i in range(2, n + 1):
        dp[i] = min(dp[i-1] + cost[i-1], dp[i-2] + cost[i-2])
    return dp[n]''',
            "Space-optimise by keeping only the last 1-2 dp values — draw the dependency arrow first.",
        )
        _technique(
            "🗂", "2-D DP (Grid / String Pairs)",
            [
                "State: dp[i][j] = answer considering first i rows/chars and first j cols/chars.",
                "Fill the table row by row (or column by column).",
                "Transitions usually look left (dp[i][j-1]), up (dp[i-1][j]), or diagonal (dp[i-1][j-1]).",
                "Common problems: unique grid paths, minimum path sum, edit distance, LCS.",
            ],
            '''\
# Unique paths in m×n grid (only right/down moves)
def unique_paths(m, n):
    dp = [[1] * n for _ in range(m)]
    for i in range(1, m):
        for j in range(1, n):
            dp[i][j] = dp[i-1][j] + dp[i][j-1]
    return dp[m-1][n-1]

# Longest Common Subsequence
def lcs(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]''',
            "LCS diagonal = match; left/up = skip. Edit Distance: replace=diagonal+1, insert=left+1, delete=up+1.",
            "Time O(m·n), Space O(m·n) or O(n) with rolling array",
        )
        _technique(
            "🎒", "0/1 Knapsack",
            [
                "State: dp[i][w] = max value using first i items with capacity w.",
                "Choice per item: skip it (dp[i-1][w]) or take it (dp[i-1][w-wt[i]] + val[i]) if wt[i]<=w.",
                "Take the max of the two choices.",
                "1-D optimisation: iterate weights in REVERSE so each item is used at most once.",
            ],
            '''\
# 0/1 Knapsack — space-optimised to 1-D
def knapsack(weights, values, W):
    dp = [0] * (W + 1)
    for w, v in zip(weights, values):
        for cap in range(W, w - 1, -1):   # reverse!
            dp[cap] = max(dp[cap], dp[cap - w] + v)
    return dp[W]

# Unbounded knapsack (same item multiple times) → iterate FORWARD
def unbounded_knapsack(weights, values, W):
    dp = [0] * (W + 1)
    for w, v in zip(weights, values):
        for cap in range(w, W + 1):        # forward
            dp[cap] = max(dp[cap], dp[cap - w] + v)
    return dp[W]''',
            "Reverse iteration = 0/1 (each item once). Forward iteration = unbounded (item reusable). This single direction flip is the entire difference.",
            "Time O(n·W), Space O(W)",
        )
        _technique(
            "📏", "Longest Increasing Subsequence (LIS)",
            [
                "O(n²) DP: dp[i] = LIS ending at index i. For each i, look back at all j<i where arr[j]<arr[i].",
                "O(n log n) Patience Sorting: maintain 'piles' list — binary search for insertion position.",
                "len(piles) at the end = LIS length.",
            ],
            '''\
# O(n²) — also reconstructable
def lis_n2(arr):
    n = len(arr)
    dp = [1] * n
    for i in range(1, n):
        for j in range(i):
            if arr[j] < arr[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)

# O(n log n) — patience sorting (length only)
from bisect import bisect_left
def lis_nlogn(arr):
    piles = []
    for v in arr:
        pos = bisect_left(piles, v)
        if pos == len(piles): piles.append(v)
        else: piles[pos] = v
    return len(piles)''',
            "Patience sorting gives length, not the actual subsequence. Use the O(n²) version if you need to reconstruct the sequence.",
        )
        _sec("Common Pitfalls")
        _bullets([
            "Defining state ambiguously — write out <code>dp[i] means …</code> in English before coding.",
            "Missing base cases (dp[0] / dp[0][0]) or accessing negative indices.",
            "0/1 knapsack iterating forward → same item counted multiple times.",
            "LCS confusion: diagonal move ONLY when characters match; left/up otherwise.",
        ])
        _pattern_footer("Dynamic Programming")

    # ═══════════════════════════════════════════════════════
    #  GRAPHS
    # ═══════════════════════════════════════════════════════
    with p_tabs[2]:
        _overview(
            "Graphs model relationships. Everything is either BFS (layer-by-layer) or DFS (go deep, backtrack).",
            "Build the adjacency list first. Choose BFS for shortest paths (unweighted) and level-order problems; "
            "DFS for reachability, cycle detection, and topological ordering. "
            "Dijkstra when edges have non-negative weights.",
            "BFS/DFS O(V+E), Dijkstra O((V+E) log V), Union-Find O(α(n)) ≈ O(1)",
        )
        _sec("Recognition Clues")
        _bullets([
            "Shortest path, minimum steps → <b>BFS</b> (unweighted) or <b>Dijkstra</b> (weighted).",
            "Flood fill, connected components, islands → <b>DFS / BFS</b> with visited set.",
            "Scheduling with prerequisites, course order → <b>Topological Sort</b>.",
            "Detect cycle in undirected graph → <b>Union-Find</b> or DFS back-edge.",
            "Detect cycle in directed graph → DFS with colour states (white/grey/black).",
            "Minimum spanning tree → <b>Kruskal</b> (sort edges + Union-Find) or <b>Prim</b> (greedy + heap).",
        ])
        _sec("Techniques")
        _technique(
            "🌊", "BFS — Shortest Path / Level Order",
            [
                "Use a deque. Push start node; mark visited immediately on enqueue (not dequeue).",
                "Process layer by layer; increment distance after each layer.",
                "For grid problems, store (row, col) as state; explore 4 directions.",
            ],
            '''\
from collections import deque

def bfs_shortest(graph, start, end):
    visited = {start}
    q = deque([(start, 0)])       # (node, distance)
    while q:
        node, dist = q.popleft()
        if node == end: return dist
        for nb in graph[node]:
            if nb not in visited:
                visited.add(nb)   # mark on ENQUEUE
                q.append((nb, dist + 1))
    return -1

# Grid BFS template
DIRS = [(0,1),(0,-1),(1,0),(-1,0)]
def bfs_grid(grid, sr, sc):
    rows, cols = len(grid), len(grid[0])
    visited = {(sr, sc)}
    q = deque([(sr, sc, 0)])
    while q:
        r, c, d = q.popleft()
        for dr, dc in DIRS:
            nr, nc = r+dr, c+dc
            if 0<=nr<rows and 0<=nc<cols and (nr,nc) not in visited and grid[nr][nc]!=\'#\':
                visited.add((nr, nc))
                q.append((nr, nc, d+1))''',
            "Mark visited when you ENQUEUE, not dequeue — otherwise you'll enqueue the same node many times.",
            "Time O(V+E)",
        )
        _technique(
            "🌀", "DFS — Connectivity & Cycle Detection",
            [
                "Recursive DFS: mark visited, recurse on unvisited neighbours, unmark on backtrack (for path problems).",
                "Directed cycle detection: use three colours — 0=unvisited, 1=in-stack (grey), 2=done (black).",
                "Undirected cycle: pass parent to avoid false back-edges.",
            ],
            '''\
# DFS — number of connected components
def count_components(n, edges):
    graph = [[] for _ in range(n)]
    for u, v in edges:
        graph[u].append(v); graph[v].append(u)
    visited = set()
    def dfs(node):
        for nb in graph[node]:
            if nb not in visited:
                visited.add(nb); dfs(nb)
    count = 0
    for i in range(n):
        if i not in visited:
            visited.add(i); dfs(i); count += 1
    return count

# Directed cycle detection (colour DFS)
def has_cycle(n, edges):
    graph = [[] for _ in range(n)]
    for u, v in edges: graph[u].append(v)
    color = [0] * n
    def dfs(u):
        color[u] = 1
        for v in graph[u]:
            if color[v] == 1: return True    # back-edge → cycle
            if color[v] == 0 and dfs(v): return True
        color[u] = 2
        return False
    return any(dfs(i) for i in range(n) if color[i] == 0)''',
            "Recursive DFS can hit Python's recursion limit on large graphs. Use an explicit stack for safety.",
        )
        _technique(
            "📐", "Topological Sort (Kahn's BFS)",
            [
                "Build in-degree count for every node.",
                "Seed the queue with all zero-in-degree nodes.",
                "Pop a node, add to result, decrement neighbours' in-degree; enqueue any that reach 0.",
                "If result length < n, a cycle exists.",
            ],
            '''\
from collections import deque

def topo_sort(n, prereqs):
    graph = [[] for _ in range(n)]
    indegree = [0] * n
    for a, b in prereqs:
        graph[b].append(a)
        indegree[a] += 1
    q = deque(i for i in range(n) if indegree[i] == 0)
    order = []
    while q:
        node = q.popleft()
        order.append(node)
        for nb in graph[node]:
            indegree[nb] -= 1
            if indegree[nb] == 0:
                q.append(nb)
    return order if len(order) == n else []   # [] = cycle detected''',
            "Kahn's naturally detects cycles: if the output order is shorter than n, a cycle prevented some nodes from reaching in-degree 0.",
            "Time O(V+E)",
        )
        _technique(
            "🗺", "Dijkstra's Algorithm",
            [
                "Min-heap of (distance, node). Start with (0, source).",
                "Pop the smallest distance node; skip if already finalised.",
                "Relax all outgoing edges: if dist[node] + weight < dist[nb], push (new_dist, nb).",
                "Only works with NON-NEGATIVE edge weights.",
            ],
            '''\
import heapq

def dijkstra(n, edges, src):
    graph = [[] for _ in range(n)]
    for u, v, w in edges:
        graph[u].append((v, w))
    dist = [float("inf")] * n
    dist[src] = 0
    heap = [(0, src)]                    # (distance, node)
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]: continue         # stale entry — skip
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(heap, (dist[v], v))
    return dist''',
            "The 'stale entry' check (<code>if d > dist[u]: continue</code>) is essential — without it you'll reprocess nodes with outdated distances.",
            "Time O((V+E) log V)",
        )
        _technique(
            "🔗", "Union-Find (DSU)",
            [
                "Two operations: find(x) — which component does x belong to; union(x, y) — merge components.",
                "Path compression: point every node directly to its root during find.",
                "Union by rank: always attach the smaller tree under the larger.",
                "Use for: Kruskal's MST, detecting cycles in undirected graphs, grouping problems.",
            ],
            '''\
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.components = n

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])   # path compression
        return self.parent[x]

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry: return False        # already connected
        if self.rank[rx] < self.rank[ry]: rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]: self.rank[rx] += 1
        self.components -= 1
        return True''',
            "If union() returns False for an edge in an undirected graph, that edge creates a cycle.",
            "Time O(α(n)) ≈ O(1) per operation",
        )
        _sec("Common Pitfalls")
        _bullets([
            "BFS: marking visited on dequeue instead of enqueue → exponential re-enqueueing.",
            "Dijkstra with negative weights → use Bellman-Ford instead (O(VE)).",
            "Topological sort on undirected graphs → always use directed graph formulation.",
            "DFS recursion depth: Python default is 1000; set <code>sys.setrecursionlimit()</code> or use iterative DFS.",
        ])
        _pattern_footer("Graphs")

    # ═══════════════════════════════════════════════════════
    #  GREEDY
    # ═══════════════════════════════════════════════════════
    with p_tabs[3]:
        _overview(
            "Greedy makes the locally optimal choice at each step — and it works when local optimum = global optimum.",
            "Greedy is hard to identify but fast to code. The key is the <b>exchange argument</b>: prove that swapping "
            "any two adjacent choices in your greedy order can only make things worse (or equal). "
            "If you can prove that, greedy is correct.",
            "Usually O(n log n) due to sorting; O(n) processing after",
        )
        _sec("Recognition Clues")
        _bullets([
            "Intervals / scheduling: maximize activities or minimize overlaps → sort by finish time.",
            "Optimal merge / Huffman: combine smallest items first → use min-heap.",
            "'Minimize maximum' or 'maximize minimum' → try binary search on the answer instead.",
            "Coin change with specific denominations (e.g., real currency) → greedy by largest coin.",
            "Jump game, gas station — local feasibility implies global feasibility.",
        ])
        _sec("Techniques")
        _technique(
            "📅", "Interval Scheduling / Activity Selection",
            [
                "Goal: select the maximum number of non-overlapping intervals.",
                "Sort ALL intervals by their END time (finish time).",
                "Greedily pick the first interval; then pick the next one whose start >= last end.",
                "Proof: finishing earliest leaves the most room for future activities.",
            ],
            '''\
def max_activities(intervals):
    intervals.sort(key=lambda x: x[1])     # sort by finish time
    count = 0
    last_end = float("-inf")
    for start, end in intervals:
        if start >= last_end:
            count += 1
            last_end = end
    return count

# Minimum number of meeting rooms needed
import heapq
def min_meeting_rooms(intervals):
    intervals.sort(key=lambda x: x[0])     # sort by start
    heap = []                               # min-heap of end times
    for start, end in intervals:
        if heap and heap[0] <= start:
            heapq.heapreplace(heap, end)    # reuse a room
        else:
            heapq.heappush(heap, end)       # new room
    return len(heap)''',
            "Sort by FINISH time for 'max non-overlapping'. Sort by START time for 'min rooms needed'. These are different problems.",
        )
        _technique(
            "🐸", "Jump Game",
            [
                "Track the furthest reachable index so far.",
                "At each position, update max_reach = max(max_reach, i + jumps[i]).",
                "If i ever exceeds max_reach, you're stuck — return False.",
                "Variant: minimum jumps — greedily jump to the position that maximises next reach.",
            ],
            '''\
def can_jump(nums):
    max_reach = 0
    for i, jump in enumerate(nums):
        if i > max_reach: return False
        max_reach = max(max_reach, i + jump)
    return True

def min_jumps(nums):
    jumps = curr_end = farthest = 0
    for i in range(len(nums) - 1):
        farthest = max(farthest, i + nums[i])
        if i == curr_end:          # end of current jump range
            jumps += 1
            curr_end = farthest
    return jumps''',
            "Min jumps: you don't commit to a specific jump — you wait until you MUST jump (when you hit curr_end), then jump to the farthest reachable point.",
        )
        _technique(
            "🏗", "Optimal Merge / Huffman-style",
            [
                "Problem: merge N items with minimum total cost, where cost = sum of the two merged.",
                "Always merge the two smallest items first.",
                "Use a min-heap: push all items, repeatedly pop two, merge, push result.",
            ],
            '''\
import heapq

def min_cost_merge(stones):
    heapq.heapify(stones)
    total = 0
    while len(stones) > 1:
        a = heapq.heappop(stones)
        b = heapq.heappop(stones)
        cost = a + b
        total += cost
        heapq.heappush(stones, cost)
    return total''',
            "This works because the exchange argument holds: merging smaller items first reduces the number of times each element's cost is 'counted'.",
        )
        _sec("Common Pitfalls")
        _bullets([
            "Greedy coin change only works for canonical coin systems (e.g., USD). For arbitrary denominations, use DP.",
            "Sorting by start time instead of finish time in activity selection — a classic mistake.",
            "Assuming greedy works without proof — always sketch the exchange argument.",
        ])
        _pattern_footer("Greedy")

    # ═══════════════════════════════════════════════════════
    #  HEAP
    # ═══════════════════════════════════════════════════════
    with p_tabs[4]:
        _overview(
            "A heap gives you the min (or max) element in O(1) and insertion/deletion in O(log n). Use it when you repeatedly need the extreme element.",
            "Python's <code>heapq</code> is a min-heap. For max-heap, negate values. "
            "Heaps shine in problems involving 'top K', streaming data, or repeatedly merging sorted sequences.",
            "Push/pop O(log n), peek O(1), heapify O(n)",
        )
        _sec("Recognition Clues")
        _bullets([
            "K-th largest / smallest element in array or stream.",
            "Merge K sorted lists or arrays.",
            "Sliding window maximum (use deque) or minimum.",
            "Median of a stream → two heaps.",
            "Task scheduling with cooldowns / priorities.",
        ])
        _sec("Techniques")
        _technique(
            "🏆", "K-th Largest / Top K Elements",
            [
                "Maintain a min-heap of size K.",
                "For each element: push to heap; if heap grows beyond K, pop the minimum.",
                "After processing all elements, heap[0] is the K-th largest.",
                "Alternative: heapify all, then pop K times — O(n + k log n).",
            ],
            '''\
import heapq

def kth_largest(nums, k):
    heap = []
    for v in nums:
        heapq.heappush(heap, v)
        if len(heap) > k:
            heapq.heappop(heap)        # evict the smallest
    return heap[0]                     # K-th largest

# Top K frequent elements
from collections import Counter
def top_k_frequent(nums, k):
    freq = Counter(nums)
    # min-heap on frequency; keep K largest
    heap = []
    for num, cnt in freq.items():
        heapq.heappush(heap, (cnt, num))
        if len(heap) > k: heapq.heappop(heap)
    return [num for _, num in heap]''',
            "Size-K min-heap for K largest is O(n log k), beating the O(n log n) sort when k << n.",
        )
        _technique(
            "🔀", "Merge K Sorted Lists",
            [
                "Push the first element of each list into a min-heap as (value, list_index, elem_index).",
                "Pop the minimum; add it to the result; push the next element from the same list.",
                "Stop when heap is empty.",
            ],
            '''\
import heapq

def merge_k_sorted(lists):
    heap = []
    for i, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst[0], i, 0))
    result = []
    while heap:
        val, i, j = heapq.heappop(heap)
        result.append(val)
        if j + 1 < len(lists[i]):
            heapq.heappush(heap, (lists[i][j+1], i, j+1))
    return result''',
            "The heap always holds exactly one element per non-exhausted list — so its size never exceeds K.",
            "Time O(N log K) where N = total elements",
        )
        _technique(
            "⚖", "Find Median from Data Stream (Two Heaps)",
            [
                "Keep a max-heap for the lower half, min-heap for the upper half.",
                "Balance so that max_heap has at most 1 more element than min_heap.",
                "Median = max_heap top (odd total) or average of both tops (even total).",
            ],
            '''\
import heapq

class MedianFinder:
    def __init__(self):
        self.lo = []   # max-heap (negate for Python)
        self.hi = []   # min-heap

    def add_num(self, num):
        heapq.heappush(self.lo, -num)
        # ensure every lo element <= every hi element
        heapq.heappush(self.hi, -heapq.heappop(self.lo))
        # balance sizes: lo may have 1 extra
        if len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def find_median(self):
        if len(self.lo) > len(self.hi):
            return -self.lo[0]
        return (-self.lo[0] + self.hi[0]) / 2''',
            "Negate values for the max-heap since Python only has min-heap. The two-heap invariant guarantees O(log n) add and O(1) median.",
        )
        _sec("Common Pitfalls")
        _bullets([
            "Python max-heap: negate all values when pushing; negate again when reading.",
            "K-th largest ≠ K-th from top of a sorted array — double-check the definition.",
            "Sliding window max with a heap still includes stale elements — use a <code>deque</code> (monotonic queue) instead.",
        ])
        _pattern_footer("Heap")

    # ═══════════════════════════════════════════════════════
    #  STACK
    # ═══════════════════════════════════════════════════════
    with p_tabs[5]:
        _overview(
            "A stack remembers history in LIFO order — perfect when the answer for the current element depends on the nearest un-resolved previous element.",
            "The monotonic stack is the most powerful stack pattern: maintain an increasing or decreasing stack "
            "and whenever the invariant breaks, the popped element's answer is the current element. "
            "Recognize it when you see 'next greater', 'previous smaller', or 'largest rectangle'.",
            "All stack patterns run in O(n) — each element is pushed and popped at most once",
        )
        _sec("Recognition Clues")
        _bullets([
            "Next greater / next smaller element → <b>Monotonic stack</b>.",
            "Largest rectangle in histogram / maximal rectangle → monotonic stack.",
            "Balanced parentheses / valid expression → plain stack.",
            "Evaluate expression with precedence (calculator) → two stacks (ops + nums).",
            "Iterative DFS / backtracking → explicit stack.",
        ])
        _sec("Techniques")
        _technique(
            "📉", "Monotonic Stack — Next Greater Element",
            [
                "Maintain a stack of indices whose 'next greater' hasn't been found yet.",
                "For each element: while stack top < current element, pop — current element IS the answer for popped index.",
                "Push current index onto stack.",
                "Remaining indices in stack have no next greater element (answer = -1).",
            ],
            '''\
def next_greater(arr):
    n = len(arr)
    result = [-1] * n
    stack = []                      # indices of unresolved elements
    for i, v in enumerate(arr):
        while stack and arr[stack[-1]] < v:
            idx = stack.pop()
            result[idx] = v         # v is the next greater for idx
        stack.append(i)
    return result

# Previous smaller element (mirror — scan left to right, keep increasing stack)
def prev_smaller(arr):
    result = [-1] * len(arr)
    stack = []
    for i, v in enumerate(arr):
        while stack and arr[stack[-1]] >= v:
            stack.pop()
        result[i] = arr[stack[-1]] if stack else -1
        stack.append(i)
    return result''',
            "Decreasing stack → next greater. Increasing stack → next smaller. Circular array: iterate 2×n with index % n.",
        )
        _technique(
            "📊", "Largest Rectangle in Histogram",
            [
                "For each bar, the rectangle width extends left and right until a shorter bar is hit.",
                "Use a monotonic increasing stack of indices.",
                "When you pop index i (because current bar is shorter), width = current_idx − stack_top − 1.",
                "Sentinel: append height 0 at end to flush all remaining bars.",
            ],
            '''\
def largest_rectangle(heights):
    heights = heights + [0]          # sentinel flushes the stack
    stack = [-1]                     # sentinel index
    max_area = 0
    for i, h in enumerate(heights):
        while stack[-1] != -1 and heights[stack[-1]] >= h:
            height = heights[stack.pop()]
            width  = i - stack[-1] - 1
            max_area = max(max_area, height * width)
        stack.append(i)
    return max_area''',
            "The -1 sentinel avoids an empty-stack check. When you pop, the new stack top is the 'previous smaller bar' — so width = i − prev_smaller − 1.",
            "Time O(n), Space O(n)",
        )
        _technique(
            "()", "Valid Parentheses & Expression Evaluation",
            [
                "Parentheses: push open brackets; on close bracket, check stack top matches.",
                "Calculator: two stacks — one for numbers, one for operators. Apply operators in precedence order.",
                "Simpler calc: evaluate left-to-right; use stack to handle '+'/'-' with parentheses.",
            ],
            '''\
# Valid parentheses
def is_valid(s):
    match = {")": "(", "]": "[", "}": "{"}
    stack = []
    for c in s:
        if c in "([{": stack.append(c)
        elif not stack or stack[-1] != match[c]: return False
        else: stack.pop()
    return not stack

# Basic calculator (+, -, parentheses)
def calculate(s):
    stack, num, sign, result = [], 0, 1, 0
    for c in s:
        if c.isdigit():
            num = num * 10 + int(c)
        elif c in "+-":
            result += sign * num
            num = 0
            sign = 1 if c == "+" else -1
        elif c == "(":
            stack.append(result); stack.append(sign)
            result = 0; sign = 1
        elif c == ")":
            result += sign * num; num = 0
            result *= stack.pop()          # sign before "("
            result += stack.pop()          # result before "("
    return result + sign * num''',
            "The key insight for calculator: on '(' save current (result, sign) onto stack; on ')' restore and combine.",
        )
        _sec("Common Pitfalls")
        _bullets([
            "Monotonic stack direction: decreasing stack for next-GREATER, increasing for next-SMALLER. Drawing it out prevents confusion.",
            "Forgetting the sentinel in histogram — some bars at the end never get popped without it.",
            "Parentheses: check <code>not stack</code> before <code>stack[-1]</code> to avoid IndexError on unmatched close brackets.",
        ])
        _pattern_footer("Stack")

    # ═══════════════════════════════════════════════════════
    #  STRING
    # ═══════════════════════════════════════════════════════
    with p_tabs[6]:
        _overview(
            "String problems usually reduce to array problems once you recognise the right abstraction — character frequency, hashing, or pointer movement.",
            "Sliding window and two-pointer work on strings just like arrays. "
            "Hashing (character frequency maps) enables O(1) comparison of substrings. "
            "KMP eliminates the need for backtracking in pattern matching.",
            "Most string patterns: O(n) time, O(1) or O(Σ) space (Σ = alphabet size, often 26)",
        )
        _sec("Recognition Clues")
        _bullets([
            "Shortest/longest substring with condition (distinct chars, all of pattern) → <b>Sliding Window</b>.",
            "Check if two strings are anagrams, or find all anagram positions → <b>Frequency map</b>.",
            "Is string a palindrome / find longest palindromic substring → <b>Two Pointers / Expand Around Centre</b>.",
            "Find pattern in text efficiently → <b>KMP</b> or built-in <code>str.find()</code>.",
            "Encode/decode or hash substrings for fast comparison → <b>Rolling Hash</b>.",
        ])
        _sec("Techniques")
        _technique(
            "🪟", "Sliding Window for Substrings",
            [
                "Maintain a window [left, right] and a frequency map of characters inside.",
                "Expand right freely; shrink left when the window violates the condition.",
                "Track 'have' vs 'need' counts to know when the window is valid in O(1).",
            ],
            '''\
from collections import Counter

# Minimum window substring containing all chars of t
def min_window(s, t):
    need = Counter(t)
    have, formed = {}, 0
    l = res_len = float("inf")
    res = (0, 0)
    left = 0
    for right, c in enumerate(s):
        have[c] = have.get(c, 0) + 1
        if c in need and have[c] == need[c]:
            formed += 1
        while formed == len(need):           # valid window
            if right - left + 1 < res_len:
                res_len = right - left + 1
                res = (left, right)
            lc = s[left]
            have[lc] -= 1
            if lc in need and have[lc] < need[lc]:
                formed -= 1
            left += 1
    return s[res[0]:res[1]+1] if res_len != float("inf") else ""''',
            "'formed' tracks how many unique characters in t have been satisfied in the current window. Shrink only when formed == len(need).",
            "Time O(|s| + |t|), Space O(|t|)",
        )
        _technique(
            "🔤", "Anagram Detection via Frequency Map",
            [
                "Two strings are anagrams iff their character frequency maps are identical.",
                "For 'find all anagram start positions': use a fixed-size sliding window of length len(p).",
                "Slide window by 1: remove leftmost char, add new right char, compare maps.",
                "Optimise: track a 'matches' counter instead of comparing entire maps each step.",
            ],
            '''\
from collections import Counter

def find_anagrams(s, p):
    p_count = Counter(p)
    w_count = Counter(s[:len(p)])
    result = []
    if w_count == p_count: result.append(0)

    for i in range(len(p), len(s)):
        # slide window
        new_c, old_c = s[i], s[i - len(p)]
        w_count[new_c] += 1
        w_count[old_c] -= 1
        if w_count[old_c] == 0: del w_count[old_c]
        if w_count == p_count:
            result.append(i - len(p) + 1)
    return result''',
            "Comparing two Counter objects is O(Σ), not O(n) — so the overall algorithm is O(n·Σ). For Σ=26 this is effectively O(n).",
        )
        _technique(
            "🪞", "Palindrome — Expand Around Centre",
            [
                "For each centre (n centres for odd-length, n-1 for even), expand outward while chars match.",
                "Track the longest expansion found.",
                "Also works as two-pointer from both ends for 'is palindrome' check.",
            ],
            '''\
def longest_palindrome(s):
    def expand(l, r):
        while l >= 0 and r < len(s) and s[l] == s[r]:
            l -= 1; r += 1
        return s[l+1:r]            # last valid window

    best = ""
    for i in range(len(s)):
        odd  = expand(i, i)        # odd-length centres
        even = expand(i, i + 1)    # even-length centres
        if len(odd)  > len(best): best = odd
        if len(even) > len(best): best = even
    return best

# Check palindrome with two pointers
def is_palindrome(s):
    l, r = 0, len(s) - 1
    while l < r:
        if s[l] != s[r]: return False
        l += 1; r -= 1
    return True''',
            "There are 2n−1 possible centres (n odd, n−1 even). Expanding from each is O(n) per centre → O(n²) total. Manacher's algorithm achieves O(n) but is rarely needed in interviews.",
        )
        _technique(
            "🔎", "KMP Pattern Matching",
            [
                "Build a 'failure function' (LPS array) for the pattern: lps[i] = length of longest proper prefix of pattern[0..i] that is also a suffix.",
                "Use lps to skip re-comparisons on mismatch instead of restarting from position 0.",
                "Search: two pointers i (text), j (pattern). Mismatch → j = lps[j-1]. Match → both advance; if j==len(pattern), found.",
            ],
            '''\
def kmp_search(text, pattern):
    # Build LPS (failure function)
    lps = [0] * len(pattern)
    length, i = 0, 1
    while i < len(pattern):
        if pattern[i] == pattern[length]:
            length += 1; lps[i] = length; i += 1
        elif length:
            length = lps[length - 1]      # backtrack in pattern
        else:
            lps[i] = 0; i += 1

    # Search
    matches = []
    i = j = 0
    while i < len(text):
        if text[i] == pattern[j]:
            i += 1; j += 1
        if j == len(pattern):
            matches.append(i - j)
            j = lps[j - 1]
        elif i < len(text) and text[i] != pattern[j]:
            j = lps[j - 1] if j else (i := i + 1) or 0
    return matches''',
            "KMP avoids O(n·m) brute-force by never moving the text pointer backward. In practice, Python's <code>str.find()</code> is already O(n) for most inputs.",
            "Time O(n + m), Space O(m)",
        )
        _sec("Common Pitfalls")
        _bullets([
            "Modifying a string in place — Python strings are immutable; work with a list and join at the end.",
            "Sliding window on strings: remember to delete keys with count 0 from the frequency map, or comparisons will fail.",
            "KMP LPS build: on mismatch, set <code>length = lps[length-1]</code>, NOT <code>length = 0</code>.",
        ])
        _pattern_footer("String")

# ══════════════════════════════════════════════════════════════════════════════
#  TAB — PRACTICE JOURNAL  (GitHub-connected users only)
# ══════════════════════════════════════════════════════════════════════════════
if has_github and JOURNAL_IDX is not None:
    with tabs[JOURNAL_IDX]:

        gh_user  = st.session_state.get("github_username", "")
        repo_url = f"https://github.com/{gh_user}/dsa-planner-data"

        # ── Top bar ───────────────────────────────────────────────────────────
        jh1, jh2, jh3, jh4, jh5 = st.columns([2, 1.5, 1, 1, 0.7])
        with jh1:
            search_q = st.text_input("", "", key="jrn_search",
                                     placeholder="🔍 Search question…",
                                     label_visibility="collapsed")
        with jh2:
            result_filter = st.selectbox("", ["All", "Correct ✅", "Incorrect ❌"],
                                         key="jrn_filter", label_visibility="collapsed")
        with jh3:
            pat_opts = ["All patterns"]
            _raw = st.session_state.get("gh_journal", [])
            pat_opts += sorted({s.get("pattern","") for s in _raw if s.get("pattern")})
            pat_filter = st.selectbox("", pat_opts, key="jrn_pat", label_visibility="collapsed")
        with jh4:
            page_size = st.selectbox("", [25, 50, 100], key="jrn_pgsz",
                                     label_visibility="collapsed",
                                     format_func=lambda x: f"{x} / page")
        with jh5:
            if st.button("🔄", help="Refresh from GitHub", use_container_width=True):
                st.session_state.pop("gh_journal", None)
                st.session_state.jrn_page = 0
                st.rerun()

        # ── Ensure repo exists ────────────────────────────────────────────────
        if not st.session_state.get("gh_repo_ensured"):
            try:
                requests.post(f"{API_URL}/github/setup", headers=auth_headers(), timeout=15)
                st.session_state.gh_repo_ensured = True
            except Exception:
                pass

        # ── Fetch ─────────────────────────────────────────────────────────────
        if "gh_journal" not in st.session_state:
            with st.spinner("Fetching sessions from GitHub…"):
                try:
                    r = requests.get(f"{API_URL}/github/history",
                                     headers=auth_headers(), timeout=30)
                    st.session_state.gh_journal = (
                        r.json().get("sessions", []) if r.status_code == 200 else []
                    )
                    if r.status_code != 200:
                        st.error("Could not load sessions from GitHub.")
                except Exception as e:
                    st.session_state.gh_journal = []
                    st.error(f"Error: {e}")

        sessions = st.session_state.get("gh_journal", [])

        if not sessions:
            st.info("No practice sessions yet. Complete a session to start tracking!")
        else:
            # ── Filter ────────────────────────────────────────────────────────
            filtered = sessions
            if search_q:
                filtered = [s for s in filtered
                            if search_q.lower() in s.get("question", "").lower()]
            if result_filter == "Correct ✅":
                filtered = [s for s in filtered if s.get("correct")]
            elif result_filter == "Incorrect ❌":
                filtered = [s for s in filtered if not s.get("correct")]
            if pat_filter != "All patterns":
                filtered = [s for s in filtered if s.get("pattern") == pat_filter]

            total      = len(filtered)
            correct_ct = sum(1 for s in filtered if s.get("correct"))
            avg_sec    = (sum(s.get("time_taken_seconds", 0) for s in filtered)
                          // max(1, total))
            avg_min, avg_s = divmod(avg_sec, 60)
            acc_pct = round(correct_ct / total * 100) if total else 0
            acc_col = "#22c55e" if acc_pct >= 80 else "#f59e0b" if acc_pct >= 60 else "#ec4899"

            # Stats bar
            st.markdown(
                f'<div style="display:flex;gap:20px;align-items:center;'
                f'background:#fff;border:1.5px solid #ede9fe;border-radius:12px;'
                f'padding:8px 16px;margin:6px 0 10px;flex-wrap:wrap;">'
                f'<span style="font-size:.78em;color:#6b7280;">'
                f'  <b style="color:#1e1b4b;">{total}</b> session{"s" if total!=1 else ""}'
                f'</span>'
                f'<span style="font-size:.78em;color:#6b7280;">·</span>'
                f'<span style="font-size:.78em;color:{acc_col};font-weight:700;">'
                f'  {correct_ct} correct ({acc_pct}%)'
                f'</span>'
                f'<span style="font-size:.78em;color:#6b7280;">·</span>'
                f'<span style="font-size:.78em;color:#6b7280;">'
                f'  avg ⏱ {avg_min}m {avg_s}s'
                f'</span>'
                f'<span style="margin-left:auto;font-size:.72em;color:#a78bfa;">'
                f'  <a href="{repo_url}" target="_blank" style="color:#a78bfa;text-decoration:none;">'
                f'  🔗 {gh_user}/dsa-planner-data</a>'
                f'</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Pagination ────────────────────────────────────────────────────
            if "jrn_page" not in st.session_state:
                st.session_state.jrn_page = 0
            # clamp page if filter narrowed the list
            total_pages = max(1, (total + page_size - 1) // page_size)
            if st.session_state.jrn_page >= total_pages:
                st.session_state.jrn_page = 0
            page = st.session_state.jrn_page
            page_sessions = filtered[page * page_size: (page + 1) * page_size]

            # ── Session rows ──────────────────────────────────────────────────
            current_date = None
            for s in page_sessions:
                s_date = s.get("date", "")

                # Compact date group divider
                if s_date != current_date:
                    try:
                        d_fmt = datetime.strptime(s_date, "%Y-%m-%d").strftime("%a, %d %b %Y")
                    except Exception:
                        d_fmt = s_date
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;'
                        f'margin:14px 0 4px;">'
                        f'<span style="font-size:.68em;font-weight:700;color:#7c3aed;'
                        f'white-space:nowrap;">📅 {d_fmt}</span>'
                        f'<div style="flex:1;height:1px;background:#ede9fe;"></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    current_date = s_date

                correct    = s.get("correct", True)
                mins       = s.get("time_taken_seconds", 0) // 60
                secs_rem   = s.get("time_taken_seconds", 0) % 60
                time_label = f"{mins}m {secs_rem}s" if mins else f"{secs_rem}s"
                icon       = "✅" if correct else "❌"
                diff       = s.get("difficulty", "")
                diff_col   = {"Easy": "#16a34a", "Medium": "#d97706", "Hard": "#dc2626"}.get(diff, "#6b7280")
                label      = (
                    f'{icon}  {s.get("question", "")}   ·   '
                    f'{s.get("pattern", "?")}   ·   '
                    f'{diff}   ·   ⏱ {time_label}'
                )

                with st.expander(label, expanded=False):
                    gap_text    = (s.get("gap_analysis") or "").strip()
                    insight_txt = (s.get("insight") or "").strip()
                    logic       = (s.get("logic") or "").strip()
                    code        = (s.get("code") or "").strip()

                    # Logic + Code side by side
                    lc, rc = st.columns(2, gap="medium")
                    with lc:
                        st.markdown(
                            '<p style="font-size:.62em;font-weight:700;letter-spacing:.8px;'
                            'text-transform:uppercase;color:#7c3aed;margin:0 0 4px;">💡 Logic</p>',
                            unsafe_allow_html=True)
                        if logic:
                            st.markdown(
                                f'<div style="font-size:.82em;line-height:1.6;color:#374151;'
                                f'background:#f9f7ff;border-radius:8px;padding:8px 10px;">'
                                f'{logic}</div>',
                                unsafe_allow_html=True)
                        else:
                            st.caption("—")

                    with rc:
                        st.markdown(
                            '<p style="font-size:.62em;font-weight:700;letter-spacing:.8px;'
                            'text-transform:uppercase;color:#7c3aed;margin:0 0 4px;">💻 Code</p>',
                            unsafe_allow_html=True)
                        if code:
                            st.code(code, language="python")
                        else:
                            st.caption("—")

                    # Gap analysis card (full width, below)
                    if gap_text:
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg,#1a0533,#2d1457);'
                            f'border-left:3px solid #f472b6;border-radius:0 10px 10px 0;'
                            f'padding:10px 14px;margin-top:8px;">'
                            f'<div style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                            f'text-transform:uppercase;color:#f472b6;margin-bottom:6px;">🔍 Gap Analysis</div>'
                            f'<div style="font-size:.82em;color:#fce7f3;line-height:1.7;">{gap_text}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    # AI insight — collapsed inside to save space
                    if insight_txt:
                        with st.expander("🤖 AI Insight", expanded=False):
                            st.markdown(insight_txt)

                    # Link back to chat area for revision
                    q_title = s.get("question", "")
                    matched_q = next(
                        (q for q in questions if q.get("title", "") == q_title), None
                    )
                    if matched_q:
                        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                        if st.button(
                            "↩ Revise in Chat",
                            key=f"jrn_revise_{s.get('date','')}_{q_title[:30]}",
                            help="Open this question in the practice & chat area",
                        ):
                            st.session_state.active_qid    = int(matched_q["id"])
                            st.session_state.view_last_qid = None
                            st.session_state.pop("start_timestamp", None)
                            st.rerun()

            # ── Pagination controls ───────────────────────────────────────────
            if total_pages > 1:
                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                pg1, pg2, pg3, pg4, pg5 = st.columns([1, 1, 2, 1, 1])
                if pg1.button("⏮ First", use_container_width=True, disabled=(page == 0)):
                    st.session_state.jrn_page = 0; st.rerun()
                if pg2.button("◀ Prev",  use_container_width=True, disabled=(page == 0)):
                    st.session_state.jrn_page -= 1; st.rerun()
                pg3.markdown(
                    f'<div style="text-align:center;padding-top:6px;font-size:.82em;'
                    f'color:#7c3aed;font-weight:600;">Page {page+1} / {total_pages}</div>',
                    unsafe_allow_html=True)
                if pg4.button("Next ▶",  use_container_width=True, disabled=(page >= total_pages-1)):
                    st.session_state.jrn_page += 1; st.rerun()
                if pg5.button("Last ⏭",  use_container_width=True, disabled=(page >= total_pages-1)):
                    st.session_state.jrn_page = total_pages - 1; st.rerun()


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
#  SIDEBAR — LAST RECORD PANEL
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("view_last_qid") and not st.session_state.get("active_qid"):
    with st.sidebar:
        qid_lr = st.session_state.view_last_qid

        # Fetch last log from API (cache in session_state to avoid repeated calls)
        cache_key = f"last_log_{qid_lr}"
        if cache_key not in st.session_state:
            try:
                r = requests.get(f"{API_URL}/questions/{qid_lr}/last-log",
                                 headers=auth_headers(), timeout=8)
                st.session_state[cache_key] = r.json() if r.status_code == 200 else None
            except Exception:
                st.session_state[cache_key] = None

        rec = st.session_state.get(cache_key)

        if rec is None:
            st.markdown(
                '<div style="font-size:.88em;color:#f472b6;padding:20px 0;">'
                '📭 No practice record found for this question yet.<br>'
                'Hit <b>Practice →</b> to create your first session!</div>',
                unsafe_allow_html=True,
            )
            if st.button("✖ Close", use_container_width=True, key="lr_close_empty"):
                st.session_state.view_last_qid = None
                st.rerun()
        else:
            # Header
            st.markdown(
                f'<div style="font-size:1em;font-weight:800;padding:6px 0 6px;'
                f'border-bottom:1px solid #2d1457;margin-bottom:10px;'
                f'background:linear-gradient(90deg,#c084fc,#f472b6);'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
                f'📖 {rec["question_title"]}</div>',
                unsafe_allow_html=True,
            )

            # Meta strip: date · correct/wrong · time
            mins_lr = (rec.get("time_taken") or 0) // 60
            secs_lr = (rec.get("time_taken") or 0) % 60
            ok_lr   = rec.get("correct", True)
            st.markdown(
                f'<div style="background:#2a1050;border:1px solid #3d1a72;border-radius:12px;'
                f'padding:10px 14px;margin-bottom:12px;display:flex;gap:16px;flex-wrap:wrap;">'
                f'  <span style="font-size:.78em;color:#a78bfa;">📅 {rec.get("date","—")}</span>'
                f'  <span style="font-size:.78em;color:{"#86efac" if ok_lr else "#f9a8d4"};">'
                f'    {"✅ Correct" if ok_lr else "❌ Needs Work"}</span>'
                f'  <span style="font-size:.78em;color:#a78bfa;">⏱ {mins_lr}m {secs_lr}s</span>'
                f'  <span style="font-size:.78em;color:#7c3aed;">{rec.get("pattern","")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Editable fields
            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:10px 0 4px;">💡 Logic / Approach</p>', unsafe_allow_html=True)
            lr_logic = st.text_area("lr_logic", value=rec.get("logic", ""), key="lr_logic_input",
                                    height=160, label_visibility="collapsed",
                                    placeholder="Describe your approach step by step...")

            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">💻 Code</p>', unsafe_allow_html=True)
            lr_code = st.text_area("lr_code", value=rec.get("code", ""), key="lr_code_input",
                                   height=240, label_visibility="collapsed",
                                   placeholder="Your solution code...")

            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">📝 Notes</p>', unsafe_allow_html=True)
            lr_notes = st.text_area("lr_notes", value=rec.get("notes", "") or "", key="lr_notes_input",
                                    height=110, label_visibility="collapsed",
                                    placeholder="Key insight, pattern trick, edge case to remember...")

            st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">🔍 My Gap Analysis</p>', unsafe_allow_html=True)
            lr_gap = st.text_area("lr_gap", value=rec.get("my_gap_analysis", "") or "", key="lr_gap_input",
                                  height=110, label_visibility="collapsed",
                                  placeholder="Where did my thinking break down?")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            lr_save, lr_close = st.columns(2)
            if lr_save.button("💾 Save", type="primary", use_container_width=True, key="lr_save"):
                try:
                    r = requests.patch(
                        f"{API_URL}/questions/{qid_lr}/last-log",
                        json={"logic": lr_logic, "code": lr_code,
                              "notes": lr_notes, "my_gap_analysis": lr_gap},
                        headers=auth_headers(),
                        timeout=8,
                    )
                    if r.status_code == 200:
                        # Bust the cache so next open re-fetches
                        st.session_state.pop(cache_key, None)
                        st.success("Saved!")
                    else:
                        st.error("Save failed.")
                except Exception as e:
                    st.error(f"Error: {e}")

            if lr_close.button("✖ Close", use_container_width=True, key="lr_close"):
                st.session_state.view_last_qid = None
                st.session_state.pop(cache_key, None)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — PRACTICE PANEL
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.active_qid:
    # Expand sidebar to 85 vw when a question is open for editing
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        min-width: 85vw !important;
        max-width: 85vw !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        min-width: 85vw !important;
    }
    </style>
    """, unsafe_allow_html=True)
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
                sugg_html = q["suggestions"].replace('\n', '<br>')
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#2d1457,#4a1060);'
                    f'border-left:3px solid #c084fc;border-radius:0 10px 10px 0;'
                    f'padding:10px 14px;font-size:.8em;color:#e9d5ff;margin-bottom:8px;line-height:1.7;">'
                    f'<div style="font-size:.65em;font-weight:700;letter-spacing:.8px;text-transform:uppercase;'
                    f'color:#c084fc;margin-bottom:6px;">💡 AI Analysis</div>'
                    f'{sugg_html}</div>',
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

            # ── Problem Statement ─────────────────────────────────────────────
            desc_key = f"desc_{q['id']}"
            with st.expander("📋 Problem Statement & Examples", expanded=not bool(st.session_state.get(desc_key))):
                existing_desc = q.get("description") or st.session_state.get(desc_key)
                if existing_desc:
                    # Render sections with coloured headers
                    def _render_description(text):
                        lines = text.strip().splitlines()
                        out = []
                        for line in lines:
                            stripped = line.strip()
                            if stripped in ("PROBLEM", "EXAMPLE 1", "EXAMPLE 2", "CONSTRAINTS"):
                                out.append(
                                    f'<div style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                                    f'text-transform:uppercase;color:#7c3aed;margin:12px 0 4px;">{stripped}</div>'
                                )
                            elif stripped.startswith(("Input:", "Output:", "Explanation:")):
                                label, _, rest = stripped.partition(":")
                                out.append(
                                    f'<div style="font-size:.83em;line-height:1.6;">'
                                    f'<b style="color:#a78bfa;">{label}:</b>'
                                    f'<code style="background:#2d1457;color:#e9d5ff;padding:1px 6px;'
                                    f'border-radius:4px;font-size:.95em;">{rest.strip()}</code></div>'
                                )
                            elif stripped.startswith("•"):
                                out.append(
                                    f'<div style="font-size:.83em;color:#374151;line-height:1.7;padding-left:4px;">{stripped}</div>'
                                )
                            elif stripped:
                                out.append(f'<div style="font-size:.85em;color:#1e1b4b;line-height:1.7;">{stripped}</div>')
                        return "".join(out)

                    st.markdown(
                        f'<div style="background:#fff;border:1.5px solid #ede9fe;border-radius:12px;'
                        f'padding:14px 18px;">{_render_description(existing_desc)}</div>',
                        unsafe_allow_html=True,
                    )
                    st.session_state[desc_key] = existing_desc
                else:
                    gen_col, _ = st.columns([0.4, 0.6])
                    if gen_col.button("✨ Generate Description", key=f"gen_desc_{q['id']}", type="primary", use_container_width=True):
                        with st.spinner("Generating problem statement…"):
                            try:
                                r = requests.post(
                                    f"{API_URL}/questions/{q['id']}/description",
                                    headers=auth_headers(), timeout=25,
                                )
                                if r.status_code == 200:
                                    st.session_state[desc_key] = r.json().get("description", "")
                                    st.rerun()
                                else:
                                    st.error("Generation failed.")
                            except Exception as e:
                                st.error(f"Error: {e}")
                    st.markdown(
                        '<p style="font-size:.8em;color:#a78bfa;font-style:italic;">'
                        'Click to auto-generate a full problem description with examples.</p>',
                        unsafe_allow_html=True,
                    )

            # ── Hint section ─────────────────────────────────────────────────
            hint_key = f"hint_used_{q['id']}"
            if not st.session_state.get(hint_key):
                st.session_state[hint_key] = False

            if q.get('hint'):
                hint_col, _ = st.columns([1, 3])
                if hint_col.button("💡 Show Hint", key=f"show_hint_{q['id']}", use_container_width=True):
                    st.session_state[hint_key] = True
                if st.session_state[hint_key]:
                    st.markdown(
                        f'<div style="background:#2a1050;border-left:3px solid #f59e0b;'
                        f'border-radius:0 10px 10px 0;padding:10px 14px;font-size:.85em;'
                        f'color:#fef3c7;margin-bottom:10px;line-height:1.7;">'
                        f'<div style="font-size:.6em;font-weight:700;letter-spacing:.8px;'
                        f'text-transform:uppercase;color:#f59e0b;margin-bottom:4px;">💡 Hint'
                        f'<span style="color:#ef4444;margin-left:8px;">'
                        f'(-20% accuracy penalty)</span></div>'
                        f'{q["hint"]}</div>',
                        unsafe_allow_html=True
                    )

            # Admin: edit hint ────────────────────────────────────────────────
            if is_admin:
                with st.expander("✏️ Edit Hint (Admin)", expanded=False):
                    admin_hint = st.text_area(
                        "hint_edit", value=q.get('hint') or '',
                        key=f"hint_edit_{q['id']}", height=80,
                        label_visibility="collapsed",
                        placeholder="Add a hint that users can reveal during practice..."
                    )
                    if st.button("Save Hint", key=f"save_hint_{q['id']}", type="primary"):
                        requests.patch(
                            f"{API_URL}/questions/{q['id']}/hint",
                            json={"hint": admin_hint},
                            headers=auth_headers(),
                        )
                        st.session_state.pop(f"qs_cache", None)
                        st.success("Hint saved!")
                        st.rerun()

            # ── Input fields (two-column layout to use the wide sidebar) ────────
            col_left, col_right = st.columns(2, gap="medium")

            with col_left:
                st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">💡 Logic / Approach</p>', unsafe_allow_html=True)
                new_logic = st.text_area("logic", value=q.get('logic',''), key="logic_input", height=220, label_visibility="collapsed", placeholder="Describe your approach step by step — what data structure, why this algorithm, what edge cases you considered...")

                st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">📝 Notes</p>', unsafe_allow_html=True)
                new_notes = st.text_area("notes", value=q.get('notes') or '', key="notes_input", height=140, label_visibility="collapsed", placeholder="Key insight, pattern trick, edge case to remember...")

            with col_right:
                st.markdown(
                    '<p style="font-size:.62em;font-weight:700;letter-spacing:1px;'
                    'text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">'
                    '💻 Code &nbsp;<span style="font-weight:400;color:#9ca3af;font-size:.85em;text-transform:none;">'
                    '(Python)</span></p>',
                    unsafe_allow_html=True,
                )
                _init_code = q.get('code') or ''
                if _ACE_AVAILABLE:
                    new_code = st_ace(
                        value=_init_code,
                        language="python",
                        theme="monokai",
                        key=f"code_ace_{q['id']}",
                        font_size=13,
                        tab_size=4,
                        show_gutter=True,
                        show_print_margin=False,
                        wrap=False,
                        auto_update=True,
                        height=280,
                        placeholder="# Write your solution here…",
                    )
                else:
                    new_code = st.text_area(
                        "code", value=_init_code, key="code_input",
                        height=280, label_visibility="collapsed",
                        placeholder="# Write your solution here…",
                    )

                st.markdown('<p style="font-size:.62em;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#6d28d9;margin:14px 0 4px;">🔍 My Gap Analysis</p>', unsafe_allow_html=True)
                new_gap = st.text_area("gap", value=q.get('my_gap_analysis') or '', key="gap_input", height=140, label_visibility="collapsed", placeholder="Where did my thinking break down? What would I do differently?")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # ── Buttons ──────────────────────────────────────────────────────
            col_save, col_close = st.columns(2)
            if col_save.button("💾 Save", type="primary", use_container_width=True):
                hint_used_flag = st.session_state.get(f"hint_used_{q['id']}", False)
                requests.post(f"{API_URL}/questions/{q['id']}/log",
                              json={"logic": new_logic, "code": new_code, "time_taken": elapsed,
                                    "date": _local_today(), "hint_used": hint_used_flag},
                              headers=auth_headers())
                requests.patch(f"{API_URL}/questions/{q['id']}/notes",
                               json={"notes": new_notes, "my_gap_analysis": new_gap},
                               headers=auth_headers())
                st.session_state.ai_pending_qid   = q['id']
                st.session_state.ai_pending_since = time.time()
                st.session_state.pop(f"hint_used_{q['id']}", None)
                st.rerun()

            if col_close.button("✖ Close", use_container_width=True):
                st.session_state.active_qid = None
                st.session_state.pop('start_timestamp', None)
                st.session_state.pop('ai_pending_qid', None)
                st.session_state.pop('ai_pending_since', None)
                st.session_state.pop(f"hint_used_{q['id']}", None)
                st.session_state.pop(f"chat_{q['id']}", None)
                st.rerun()

            # ── AI Hint Chat ──────────────────────────────────────────────────
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown(
                '<div style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                'text-transform:uppercase;color:#a78bfa;margin-bottom:6px;">'
                '🤖 Ask AI Tutor</div>',
                unsafe_allow_html=True,
            )

            chat_key = f"chat_{q['id']}"
            if chat_key not in st.session_state:
                st.session_state[chat_key] = []

            chat_msgs = st.session_state[chat_key]

            # ── helper: render markdown bold + newlines inside an HTML bubble ──
            def _fmt_bubble(text):
                import re
                text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
                text = text.replace("\n", "<br>")
                return text

            # ── conversation bubbles ──────────────────────────────────────────
            if chat_msgs:
                bubbles = ""
                for msg in chat_msgs[-10:]:
                    is_variation = msg.get("is_variation", False)
                    if msg["role"] == "user":
                        bubbles += (
                            f'<div style="display:flex;justify-content:flex-end;margin-bottom:7px;">'
                            f'<div style="background:#4c1d95;color:#e9d5ff;'
                            f'border-radius:14px 14px 2px 14px;'
                            f'padding:8px 13px;font-size:.8em;max-width:82%;line-height:1.55;">'
                            f'{_fmt_bubble(msg["content"])}</div></div>'
                        )
                    else:
                        bubble_bg    = "#1a3a2a" if is_variation else "#2a1050"
                        bubble_border = "#22c55e" if is_variation else "#5b21b6"
                        bubble_label  = '<span style="font-size:.65em;color:#86efac;font-weight:700;display:block;margin-bottom:4px;">🔀 VARIATIONS</span>' if is_variation else ""
                        bubbles += (
                            f'<div style="display:flex;justify-content:flex-start;margin-bottom:7px;">'
                            f'<div style="background:{bubble_bg};border:1px solid {bubble_border};'
                            f'color:#f3e8ff;border-radius:14px 14px 14px 2px;'
                            f'padding:8px 13px;font-size:.8em;max-width:88%;line-height:1.6;">'
                            f'{bubble_label}{_fmt_bubble(msg["content"])}</div></div>'
                        )
                st.markdown(
                    f'<div style="background:#1a0a2e;border:1px solid #3d1a72;border-radius:12px;'
                    f'padding:10px;margin-bottom:8px;max-height:280px;overflow-y:auto;">'
                    f'{bubbles}</div>',
                    unsafe_allow_html=True,
                )

            # ── build shared context payload ──────────────────────────────────
            def _chat_context():
                # Ace editor stores value in new_code (local); fall back to session_state key
                code_val = new_code if 'new_code' in dir() else st.session_state.get("code_input", "")
                return {
                    "logic":        st.session_state.get("logic_input", ""),
                    "code":         code_val,
                    "notes":        st.session_state.get("notes_input", ""),
                    "gap_analysis": st.session_state.get("gap_input",   ""),
                    "accuracy":     q.get("accuracy"),
                }

            # ── input row ─────────────────────────────────────────────────────
            chat_col_in, chat_col_btn = st.columns([0.76, 0.24])
            with chat_col_in:
                user_question = st.text_input(
                    "chat_q", key=f"chat_input_{q['id']}",
                    label_visibility="collapsed",
                    placeholder="Ask anything… e.g. which data structure? why O(n log n)?"
                )
            with chat_col_btn:
                ask_clicked = st.button("Ask", key=f"chat_ask_{q['id']}", use_container_width=True)

            var_clicked = st.button(
                "🔀 Get 3 Variations", key=f"chat_var_{q['id']}",
                use_container_width=True,
                help="Ask the AI to generate 3 related problems that practise the same pattern",
            )

            # ── send regular question ─────────────────────────────────────────
            if ask_clicked and user_question.strip():
                history_snapshot = list(chat_msgs)   # capture before appending
                chat_msgs.append({"role": "user", "content": user_question.strip()})
                try:
                    resp = requests.post(
                        f"{API_URL}/questions/{q['id']}/chat",
                        json={
                            "message":  user_question.strip(),
                            "context":  _chat_context(),
                            "history":  history_snapshot,
                            "generate_variations": False,
                        },
                        headers=auth_headers(),
                        timeout=20,
                    )
                    data  = resp.json() if resp.status_code == 200 else {}
                    reply = data.get("reply", "AI unavailable.")
                except Exception:
                    reply = "Could not reach AI. Check your connection."
                chat_msgs.append({"role": "assistant", "content": reply, "is_variation": False})
                st.rerun()

            # ── send variations request ───────────────────────────────────────
            if var_clicked:
                label = f"Give me 3 variations of «{q['title']}»"
                history_snapshot = list(chat_msgs)
                chat_msgs.append({"role": "user", "content": label})
                try:
                    resp = requests.post(
                        f"{API_URL}/questions/{q['id']}/chat",
                        json={
                            "message":  label,
                            "context":  _chat_context(),
                            "history":  history_snapshot,
                            "generate_variations": True,
                        },
                        headers=auth_headers(),
                        timeout=30,
                    )
                    data  = resp.json() if resp.status_code == 200 else {}
                    reply = data.get("reply", "AI unavailable.")
                except Exception:
                    reply = "Could not reach AI. Check your connection."
                chat_msgs.append({"role": "assistant", "content": reply, "is_variation": True})
                st.rerun()

            # ── Variation Practice Panel ──────────────────────────────────────
            var_messages = [m for m in chat_msgs if m.get("is_variation") and m["role"] == "assistant"]
            if var_messages:
                import re as _re

                def _parse_variations(raw):
                    parts = _re.split(r'\*\*Variation \d+:\s*', raw)
                    out = []
                    for part in parts[1:]:
                        end = part.find('**')
                        title = part[:end].strip() if end != -1 else part.split('\n')[0].strip()
                        body  = part[end+2:].strip() if end != -1 else '\n'.join(part.split('\n')[1:]).strip()
                        if title:
                            out.append({"title": title, "description": body})
                    return out

                latest_vars = _parse_variations(var_messages[-1]["content"])

                if latest_vars:
                    st.markdown(
                        '<hr style="border:none;border-top:1px solid #3d1a72;margin:14px 0 10px;">'
                        '<div style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                        'text-transform:uppercase;color:#a78bfa;margin-bottom:8px;">📝 Practice a Variation</div>',
                        unsafe_allow_html=True,
                    )

                    sel_key = f"var_sel_{q['id']}"
                    dropdown_opts = ["— select a variation —"] + [
                        f"Variation {i+1}: {v['title']}" for i, v in enumerate(latest_vars)
                    ]
                    selected_label = st.selectbox(
                        "var_drop", dropdown_opts,
                        key=sel_key, label_visibility="collapsed",
                    )

                    if selected_label != "— select a variation —":
                        sel_idx = dropdown_opts.index(selected_label) - 1
                        sel_var = latest_vars[sel_idx]

                        # ── Description card ─────────────────────────────────
                        desc_html = sel_var["description"].replace("\n", "<br>")
                        desc_html = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', desc_html)
                        desc_html = desc_html.replace("🔑 Twist:", '<span style="color:#fbbf24;font-weight:700;">🔑 Twist:</span>')
                        st.markdown(
                            f'<div style="background:#1a0a2e;border:1.5px solid #5b21b6;'
                            f'border-radius:12px;padding:12px 16px;font-size:.83em;'
                            f'color:#e9d5ff;line-height:1.75;margin-bottom:10px;">'
                            f'{desc_html}</div>',
                            unsafe_allow_html=True,
                        )

                        # ── Two-column: notes + code ──────────────────────────
                        vl, vr = st.columns(2, gap="small")
                        with vl:
                            st.markdown(
                                '<p style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                                'text-transform:uppercase;color:#6d28d9;margin:6px 0 3px;">💡 Approach / Notes</p>',
                                unsafe_allow_html=True,
                            )
                            var_notes = st.text_area(
                                "vn", key=f"var_notes_{q['id']}_{sel_idx}",
                                height=200, label_visibility="collapsed",
                                placeholder="Describe your approach — data structure, algorithm, edge cases…",
                            )

                        with vr:
                            st.markdown(
                                '<p style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                                'text-transform:uppercase;color:#6d28d9;margin:6px 0 3px;">💻 Code</p>',
                                unsafe_allow_html=True,
                            )
                            if _ACE_AVAILABLE:
                                var_code = st_ace(
                                    value="",
                                    language="python",
                                    theme="monokai",
                                    key=f"var_ace_{q['id']}_{sel_idx}",
                                    font_size=12,
                                    tab_size=4,
                                    show_gutter=True,
                                    show_print_margin=False,
                                    auto_update=True,
                                    height=200,
                                    placeholder="# Your solution…",
                                )
                            else:
                                var_code = st.text_area(
                                    "vc", key=f"var_code_{q['id']}_{sel_idx}",
                                    height=200, label_visibility="collapsed",
                                    placeholder="# Your solution…",
                                )

                        # ── Submit button ─────────────────────────────────────
                        rev_key = f"var_result_{q['id']}_{sel_idx}"
                        if st.button(
                            "🎯 Submit for Review",
                            key=f"var_submit_{q['id']}_{sel_idx}",
                            type="primary",
                            use_container_width=True,
                        ):
                            with st.spinner("Evaluating…"):
                                try:
                                    r = requests.post(
                                        f"{API_URL}/questions/{q['id']}/variation-review",
                                        json={
                                            "variation_title":       sel_var["title"],
                                            "variation_description": sel_var["description"],
                                            "code":  var_code  or "",
                                            "notes": var_notes or "",
                                        },
                                        headers=auth_headers(),
                                        timeout=25,
                                    )
                                    st.session_state[rev_key] = r.json() if r.status_code == 200 else {"accuracy": 0, "correct": False, "feedback": "Review failed."}
                                except Exception as e:
                                    st.session_state[rev_key] = {"accuracy": 0, "correct": False, "feedback": f"Error: {e}"}
                            st.rerun()

                        # ── Review result card ────────────────────────────────
                        result = st.session_state.get(rev_key)
                        if result:
                            acc  = float(result.get("accuracy", 0))
                            corr = result.get("correct", False)
                            fb   = result.get("feedback", "")
                            acc_col  = "#86efac" if acc >= 80 else "#fcd34d" if acc >= 60 else "#f9a8d4"
                            verd_col = "#86efac" if corr else "#f9a8d4"
                            verd_txt = "✅ Correct" if corr else "❌ Needs Work"
                            st.markdown(
                                f'<div style="background:#2a1050;border:1px solid #3d1a72;'
                                f'border-radius:12px;padding:12px 16px;margin-top:6px;">'
                                f'<div style="display:flex;justify-content:space-between;'
                                f'align-items:center;margin-bottom:8px;">'
                                f'  <span style="font-weight:700;font-size:.9em;color:{verd_col};">{verd_txt}</span>'
                                f'  <span style="background:{acc_col}22;border:1px solid {acc_col};'
                                f'  border-radius:20px;padding:2px 10px;font-size:.82em;'
                                f'  font-weight:800;color:{acc_col};">🎯 {acc:.0f}%</span>'
                                f'</div>'
                                f'<div style="font-size:.82em;color:#e9d5ff;line-height:1.7;">{fb}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

            # ── AI Analysis Results ───────────────────────────────────────────
            pending_qid = st.session_state.get("ai_pending_qid")
            if pending_qid == q['id']:
                has_results = bool(q.get('suggestions') or q.get('accuracy') is not None)
                elapsed_wait = time.time() - st.session_state.get("ai_pending_since", time.time())

                if has_results:
                    # Results are in DB — show the card
                    st.session_state.pop("ai_pending_qid",   None)
                    st.session_state.pop("ai_pending_since", None)

                    status   = q.get("revision_status", "")
                    accuracy = q.get("accuracy")
                    correct  = status == "Mastered" or (accuracy or 0) >= 80
                    verdict_color = "#86efac" if correct else "#f9a8d4"
                    verdict_text  = "✅ Correct" if correct else "❌ Needs Work"
                    acc_color = (
                        "#86efac" if (accuracy or 0) >= 80
                        else "#fcd34d" if (accuracy or 0) >= 60
                        else "#f9a8d4"
                    )

                    sugg_html = (q.get("suggestions") or "").replace('\n', '<br>')
                    st.markdown(
                        f'<div style="background:#2a1050;border:1px solid #3d1a72;'
                        f'border-radius:14px;padding:14px;margin-top:10px;">'
                        f'<div style="font-size:.6em;font-weight:700;letter-spacing:1px;'
                        f'text-transform:uppercase;color:#a855f7;margin-bottom:8px;">🤖 AI Analysis</div>'
                        f'<div style="font-weight:700;font-size:.95em;color:{verdict_color};'
                        f'margin-bottom:10px;">{verdict_text}</div>'
                        + (
                            f'<div style="display:flex;justify-content:space-between;'
                            f'padding:5px 0;border-bottom:1px solid #3d1a72;font-size:.8em;margin-bottom:2px;">'
                            f'<span style="color:#9ca3af;">Accuracy</span>'
                            f'<span style="color:{acc_color};font-weight:700;">{accuracy}%</span></div>'
                            if accuracy is not None else ""
                        )
                        + (
                            f'<div style="display:flex;justify-content:space-between;'
                            f'padding:5px 0;border-bottom:1px solid #3d1a72;font-size:.8em;margin-bottom:8px;">'
                            f'<span style="color:#9ca3af;">Status</span>'
                            f'<span style="color:#e9d5ff;font-weight:600;">{status}</span></div>'
                            if status else ""
                        )
                        + (
                            f'<div style="border-left:3px solid #f472b6;'
                            f'padding:10px 12px;background:#3d1a72;border-radius:0 8px 8px 0;'
                            f'font-size:.82em;color:#fce7f3;line-height:1.7;">'
                            f'{sugg_html}</div>'
                            if sugg_html else ""
                        )
                        + '</div>',
                        unsafe_allow_html=True,
                    )

                elif elapsed_wait < 20:
                    # Still waiting — auto-refresh every 2.5 s (up to 8 times = 20 s)
                    st.markdown(
                        '<div style="background:#2a1050;border:1px solid #3d1a72;'
                        'border-radius:14px;padding:12px 14px;margin-top:10px;'
                        'font-size:.85em;color:#a78bfa;">⏳ AI analysis running…</div>',
                        unsafe_allow_html=True,
                    )
                    st_autorefresh(interval=2500, limit=8, key="ai_refresh")

                else:
                    # Timed out
                    st.session_state.pop("ai_pending_qid",   None)
                    st.session_state.pop("ai_pending_since", None)
                    st.caption("AI analysis will show on next open.")

