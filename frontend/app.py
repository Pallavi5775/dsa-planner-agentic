import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh

API_URL = "http://localhost:8000"

# --- Configuration ---
st.set_page_config(layout="wide", page_title="DSA Revision Planner")

# --- Custom Styling ---
st.markdown("""
    <style>
    .stMetric { background: #f3f3fa; padding: 15px; border-radius: 10px; border: 1px solid #eebbc3; }
    [data-testid="stSidebar"] {
        background-color: #fff !important;
        border-right: 1px solid #eebbc3;
        color: #111 !important;
    }
    [data-testid="stSidebar"] * {
        color: #111 !important;
    }
    .question-card {
        background: #f3f3fa; padding: 10px; border-radius: 8px; 
        margin-bottom: 5px; border: 1px solid #2d334a;
    }
    </style>
""", unsafe_allow_html=True)

# --- API Helper Functions ---
def fetch_questions():
    try:
        r = requests.get(f"{API_URL}/questions")
        return r.json() if r.status_code == 200 else []
    except: return []

def update_question_api(qid, payload):
    try:
        r = requests.put(f"{API_URL}/questions/{qid}", json=payload)
        return r.status_code == 200
    except: return False

def sync_questions():
    try:
        r = requests.post(f"{API_URL}/sync_questions")
        return r.status_code == 200
    except: return False

# --- App Logic ---
st.title("🎯 DSA Revision Planner")

# Initialize State
if 'active_qid' not in st.session_state:
    st.session_state.active_qid = None

questions = fetch_questions()
df = pd.DataFrame(questions)

# --- ONGOING CLOCK ---
clock_placeholder = st.empty()
clock_placeholder.markdown(f"### 🕒 {datetime.now().strftime('%H:%M:%S')}")

# --- TABS ---
tabs = st.tabs(["View Questions", "Log Practice", "Sync"])

# --- TAB 0: VIEW QUESTIONS ---
with tabs[0]:
    if df.empty:
        st.info("No problems found. Please Sync.")
    else:
        # Metrics
        covered = len(df[df['coverage_status'] == 'Covered'])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(df))
        m2.metric("Covered", covered)
        m3.metric("Revision Due", len(df[df['next_revision'] <= datetime.now().strftime("%Y-%m-%d")]))
        m4.metric("Success", f"{(covered/len(df)*100):.0f}%" if len(df)>0 else "0%")

        st.divider()

        # Filters
        f1, f2 = st.columns(2)
        pat_filter = f1.selectbox("Filter Pattern", ["All"] + sorted(df['pattern'].unique().tolist()))
        
        filtered = df.copy()
        if pat_filter != "All": 
            filtered = filtered[filtered['pattern'] == pat_filter]

        # Display Loop
        for _, row in filtered.iterrows():
            with st.container():
                cols = st.columns([0.8, 0.2])
                with cols[0]:
                    st.markdown(f"**{row['title']}** `{row['pattern']}`")
                    st.caption(f"Status: {row['coverage_status']} | Accuracy: {row.get('accuracy', 0)}%")
                with cols[1]:
                    if st.button("Edit / Details", key=f"sel_{row['id']}"):
                        st.session_state.active_qid = row['id']
                        st.rerun()

# --- SIDEBAR LOGIC ---
if st.session_state.active_qid:
    # Initialize the start time only once per session
    if 'start_timestamp' not in st.session_state:
        st.session_state.start_timestamp = time.time()

    # Calculate duration
    elapsed = int(time.time() - st.session_state.start_timestamp)
    mins, secs = divmod(elapsed, 60)

    # Get current question data
    q = next((item for item in questions if item['id'] == st.session_state.active_qid), None)

    if q:
        with st.sidebar:
            st.markdown(f"## 📝 {q['title']}")
            # Using st.metric prevents the UI from "jumping" during refreshes
            st.metric("⏱️ Session Timer", f"{mins:02d}:{secs:02d}")

            # Use unique keys for text areas to prevent state loss during refresh
            new_logic = st.text_area("Logic", value=q.get('logic', ''), key="logic_input")
            new_code = st.text_area("Code", value=q.get('code', ''), key="code_input")
            
            c1, c2 = st.columns(2)
            with c1:
                new_rev = st.selectbox("Revision", ["Pending", "Weak", "Strong"], 
                                     index=["Pending", "Weak", "Strong"].index(q.get('revision_status', 'Pending')))
            with c2:
                new_cov = st.selectbox("Coverage", ["Not Covered", "Covered"], 
                                     index=["Not Covered", "Covered"].index(q.get('coverage_status', 'Not Covered')))

            st.divider()
            
            # Log Mini-Section inside Sidebar
            st.markdown("### 🚀 Log Session")
            log_time = st.number_input("Mins", 1, 120, 20)
            log_diff = st.slider("Diff (1-5)", 1, 5, 3)
            log_correct = st.checkbox("Solved correctly?", value=True)

            col_save, col_close = st.columns(2)
            
            if col_save.button("💾 Save Everything", type="primary", use_container_width=True):
                # Only log logic, code, and time
                log_entry = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "logic": new_logic,
                    "code": new_code,
                    "time_taken": elapsed
                }
                requests.post(f"{API_URL}/questions/{q['id']}/log", json=log_entry)
                st.success("Progress Saved!")
                st.rerun()
                
            if col_close.button("✖ Close", use_container_width=True):
                st.session_state.active_qid = None
                if 'start_timestamp' in st.session_state:
                    del st.session_state.start_timestamp
                st.rerun()

            # --- AI Validation Button (only if last log within 2 minutes) ---
            show_ai_btn = False
            if q.get('logs') and len(q['logs']) > 0:
                last_log = q['logs'][-1]
                # Try to get the log's timestamp, fallback to session start if not present
                log_time_taken = last_log.get('time_taken')
                # Use session timer as fallback if log_time_taken is not available
                now_ts = int(time.time())
                # If log_time_taken is available, check if it's within 2 minutes (120 seconds)
                if log_time_taken is not None and log_time_taken <= 120:
                    show_ai_btn = True
            if show_ai_btn:
                if st.button("🤖 Validate with AI", key="ai_validate_btn"):
                    try:
                        resp = requests.post(f"{API_URL}/questions/{q['id']}/validate")
                        if resp.status_code == 200:
                            result = resp.json()
                            # Update the latest log with AI result
                            if q['logs']:
                                q['logs'][-1]['correct'] = result.get('correct', False)
                                q['logs'][-1]['gap_analysis'] = result.get('gap_analysis', '')
                            st.success("AI validation complete!")
    
                            st.markdown(result.get('gap_analysis', ''), unsafe_allow_html=True)
                        else:
                            st.error("AI validation failed.")
                    except Exception as e:
                        st.error(f"AI validation error: {e}")

# --- TAB: LOG PRACTICE ---
with tabs[1]:
    st.subheader("Global Progress Log")
    st.write("Select a question from the 'View Questions' tab to open the edit sidebar and log a specific session.")
