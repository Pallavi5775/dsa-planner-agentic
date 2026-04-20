# --- Optimized DSA Tracker Frontend ---

import streamlit as st
import requests
import os
import json
import time
from datetime import datetime

# ✅ Use relative API (works with Nginx)
API_URL = "/api"

st.set_page_config(layout="wide", page_title="DSA Revision Planner")

# --- Styling ---
st.markdown("""
<style>
.stMetric { background: #f3f3fa; padding: 12px; border-radius: 10px; border: 1px solid #eebbc3; }
.question-card { background: #f3f3fa; padding: 10px; border-radius: 8px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- CACHED API CALL ---
@st.cache_data(ttl=10)
def fetch_questions():
    try:
        r = requests.get(f"{API_URL}/questions", timeout=5)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        return []

# --- CACHED FILE LOAD ---
@st.cache_data
def load_questions_file():
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(BASE_DIR, "..", "backend", "data.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def get_question_by_qid(qid):
    data = load_questions_file()
    return next((q for q in data if q["id"] == qid), {})

# --- INIT STATE ---
if "active_qid" not in st.session_state:
    st.session_state.active_qid = None

if "start_time" not in st.session_state:
    st.session_state.start_time = None

st.title("🎯 DSA Revision Planner")

questions = fetch_questions()

# --- CLOCK ---
st.markdown(f"### 🕒 {datetime.now().strftime('%H:%M:%S')}")

# --- TABS ---
tab1, tab2 = st.tabs(["View Questions", "Add Questions"])

# --- ADD TAB ---
with tab2:
    uploaded = st.file_uploader("Upload Markdown (.md)", type=["md"])
    if st.button("Upload", disabled=uploaded is None):
        files = {"file": (uploaded.name, uploaded.getvalue())}
        try:
            r = requests.post(f"{API_URL}/upload_md", files=files, timeout=10)
            if r.status_code == 200:
                st.success("Questions added!")
                st.cache_data.clear()
                st.rerun()
        except Exception as e:
            st.error(str(e))

# --- VIEW TAB ---
with tab1:
    if not questions:
        st.info("No data available")
    else:
        total = len(questions)
        covered = sum(1 for q in questions if q["coverage_status"] == "Covered")
        due = sum(
            1 for q in questions
            if q.get("next_revision", "") <= datetime.now().strftime("%Y-%m-%d")
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", total)
        c2.metric("Covered", covered)
        c3.metric("Revision Due", due)
        c4.metric("Success", f"{(covered/total*100):.0f}%" if total else "0%")

        # --- FILTER ---
        patterns = sorted(set(q["pattern"] for q in questions))
        selected = st.selectbox("Filter", ["All"] + patterns)

        filtered = [q for q in questions if selected == "All" or q["pattern"] == selected]

        # --- DISPLAY ---
        for q in filtered:
            col1, col2 = st.columns([0.8, 0.2])
            col1.markdown(f"**{q['title']}** `{q['pattern']}`")
            col1.caption(f"{q['coverage_status']} | {q.get('accuracy',0)}%")

            if col2.button("Edit", key=f"btn_{q['id']}"):
                st.session_state.active_qid = q["id"]
                st.session_state.start_time = time.time()
                st.rerun()

# --- SIDEBAR ---
if st.session_state.active_qid:
    qid = st.session_state.active_qid
    q = next((x for x in questions if x["id"] == qid), None)

    if q:
        elapsed = int(time.time() - st.session_state.start_time)
        mins, secs = divmod(elapsed, 60)

        with st.sidebar:
            st.header(q["title"])
            st.metric("Timer", f"{mins:02}:{secs:02}")

            q_latest = get_question_by_qid(qid)

            st.markdown(f"""
            **Status:** {q_latest.get('coverage_status','')}  
            **Next:** {q_latest.get('next_revision','')}  
            **Accuracy:** {q_latest.get('accuracy',0)}%
            """)

            logic = st.text_area("Logic", value=q.get("logic",""))
            code = st.text_area("Code", value=q.get("code",""))

            if st.button("💾 Save"):
                payload = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "logic": logic,
                    "code": code,
                    "time_taken": elapsed
                }
                try:
                    requests.post(f"{API_URL}/questions/{qid}/log", json=payload, timeout=5)
                    st.success("Saved")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if st.button("Close"):
                st.session_state.active_qid = None
                st.session_state.start_time = None
                st.rerun()

            if st.button("🤖 AI Validate"):
                try:
                    r = requests.post(f"{API_URL}/questions/{qid}/validate", timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        st.success("AI Done")
                        st.write(data.get("gap_analysis",""))
                        st.info(data.get("correction_suggestion",""))
                except Exception as e:
                    st.error(str(e))