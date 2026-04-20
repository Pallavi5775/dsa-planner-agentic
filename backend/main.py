from fastapi import UploadFile, File
import os
import re
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
import openai

DSA_FILE = "../DSA_Must_Solve_Problems.md"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# --- Updated Data Models ---
class PracticeLog(BaseModel):
    date: str
    logic: str = ""
    code: str = ""
    time_taken: int = 0
    correct: bool = True  # Optional, default True for backward compatibility

class Question(BaseModel):
    id: int
    title: str
    pattern: str
    category: str = "Mixed"
    coverage_status: str = "Not Covered"
    revision_status: str = "Pending"
    logs: List[PracticeLog] = []
    
    # Advanced Metrics
    next_revision: Optional[str] = None
    ease_factor: float = 2.5 # Default ease factor for Spaced Repetition
    interval_days: int = 0
    total_time_spent: int = 0
    accuracy: Optional[float] = None
    suggestions: Optional[str] = None
    difficulty: str = "Medium"  # Default difficulty

# --- Updated Utility Functions ---

def get_spaced_repetition_values(logs, current_ease, current_interval):
    """
    Simple implementation of SM-2 inspired scheduling.
    """
    if not logs:
        return 1, 2.5
    last_log = logs[-1]
    # Calculate difficulty_score from time_taken
    time_taken = last_log.get('time_taken', 0)
    if time_taken <= 7:
        difficulty_score = 1  # Easy
    elif time_taken >= 15:
        difficulty_score = 5  # Hard
    else:
        difficulty_score = 3  # Medium
    # Map difficulty (1-5) to quality (0-5) where 5 is best
    # 1 (Easy) -> 5, 5 (Hard) -> 1
    quality = 6 - difficulty_score if last_log.get('correct', True) else 0
    
    # Update Ease Factor
    new_ease = current_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease = max(1.3, new_ease)
    
    # Calculate Interval
    if not last_log.get('correct', True):
        new_interval = 1 # Reset if failed
    else:
        if current_interval == 0:
            new_interval = 1
        elif current_interval == 1:
            new_interval = 3 # 3 days after first verification
        else:
            new_interval = round(current_interval * new_ease)
            
    return new_interval, new_ease

def get_suggestions(accuracy, revision_status, pattern, interval):
    if interval > 14:
        return f"🔥 Mastery! You've reached a long-term retention interval for {pattern}."
    if revision_status == "Weak":
        return f"Focus on identifying the 'Greedy Choice Property' for {pattern}."
    if accuracy < 60:
        return f"Warning: Low accuracy in {pattern}. Re-watch the core pattern video."
    return f"Keep it up! Next review scheduled based on difficulty."

def calculate_difficulty_from_time(time_taken):
    """
    Returns difficulty as a string based on time taken (in minutes):
    - <=7: Easy
    - 8-14: Medium
    - >=15: Hard
    """
    if time_taken <= 7:
        return "Easy"
    elif time_taken >= 15:
        return "Hard"
    else:
        return "Medium"

# --- Utility Functions ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def calculate_accuracy(logs):
    # Each log is a single attempt; correct is a boolean
    total = len(logs)
    correct = sum(1 for log in logs if log.get('correct', False))
    return round(correct / total * 100, 2) if total > 0 else 0.0

def get_next_revision(logs):
    if not logs:
        return datetime.now().strftime("%Y-%m-%d")
    last = datetime.strptime(logs[-1]['date'], "%Y-%m-%d")
    interval = min(30, 2 ** (len(logs)-1))
    return (last + timedelta(days=interval)).strftime("%Y-%m-%d")

def parse_questions():
    if not os.path.exists(DSA_FILE):
        return []
    with open(DSA_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    pattern_blocks = re.split(r"## ", content)[1:]
    questions = []
    for block in pattern_blocks:
        lines = block.splitlines()
        if not lines:
            continue
        pattern = lines[0].split("(")[0].strip()
        for line in lines[1:]:
            m = re.match(r"\d+\. (.+)", line.strip())
            if m:
                questions.append({
                    "title": m.group(1).strip(),
                    "pattern": pattern,
                    "category": "Mixed",
                    "coverage_status": "Not Covered",
                    "revision_status": "Pending",
                    "logs": [],
                })
    return questions

def sync_questions():
    questions = parse_questions()
    data = load_data()
    titles = set(q['title'] for q in data)
    next_id = max([q['id'] for q in data], default=0) + 1
    for q in questions:
        if q['title'] not in titles:
            q['id'] = next_id
            next_id += 1
            data.append(q)
    save_data(data)

# --- FastAPI App ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- Endpoint: Upload MD file and add questions to data.json ---
@app.post("/api/upload_md")
async def upload_md(file: UploadFile = File(...)):
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are supported.")
    content = await file.read()
    content = content.decode("utf-8")
    # Parse questions from uploaded content
    pattern_blocks = re.split(r"## ", content)[1:]
    new_questions = []
    for block in pattern_blocks:
        lines = block.splitlines()
        if not lines:
            continue
        pattern = lines[0].split("(")[0].strip()
        for line in lines[1:]:
            m = re.match(r"\d+\. (.+)", line.strip())
            if m:
                new_questions.append({
                    "title": m.group(1).strip(),
                    "pattern": pattern,
                    "category": "Mixed",
                    "coverage_status": "Not Covered",
                    "revision_status": "Pending",
                    "logs": [],
                    "next_revision": None,
                    "ease_factor": 2.5,
                    "interval_days": 0,
                    "total_time_spent": 0,
                    "accuracy": None,
                    "suggestions": None,
                    "difficulty": "Medium"
                })
    if not new_questions:
        raise HTTPException(status_code=400, detail="No questions found in uploaded file.")
    # Load existing data and add new questions with unique IDs
    data = load_data()
    titles = set(q['title'] for q in data)
    next_id = max([q['id'] for q in data], default=0) + 1
    added = 0
    for q in new_questions:
        if q['title'] not in titles:
            q['id'] = next_id
            next_id += 1
            data.append(q)
            added += 1
    save_data(data)
    return {"added": added, "total": len(data)}
# --- Helper: Update all fields except logs in a question dict ---
def update_question_fields_except_logs(question, new_data):
    """
    Updates all fields in question except 'logs' with values from new_data.
    """
    for k, v in new_data.items():
        if k != 'logs':
            question[k] = v
    return question



# --- Formatting Helper for Frontend Display ---
def format_dsa_feedback(data):
        """
        Returns a formatted string for displaying DSA feedback in the frontend chat area.
        """
        gap_analysis = data.get("gap_analysis", "")
        correction_suggestion = data.get("correction_suggestion", "")
        uf = data.get("updated_fields", {})
        return f'''
<div style="margin-bottom:1em;">
    <h4>Gap Analysis</h4>
    {gap_analysis}
</div>
<div style="margin-bottom:1em;">
    <h4>Correction Suggestion</h4>
    <div style="background:#f8f8fa; border-left:4px solid #eebbc3; padding:8px; border-radius:4px;">{correction_suggestion}</div>
</div>
<div style="margin-bottom:1em;">
    <h4>Updated Fields</h4>
    <ul style="margin:0 0 0 1em;">
        <li><b>Accuracy:</b> {uf.get('accuracy', '')}%</li>
        <li><b>Revision Status:</b> {uf.get('revision_status', '')}</li>
        <li><b>Next Revision:</b> {uf.get('next_revision', '')}</li>
        <li><b>Ease Factor:</b> {uf.get('ease_factor', '')}</li>
        <li><b>Interval Days:</b> {uf.get('interval_days', '')}</li>
        <li><b>Suggestions:</b> {uf.get('suggestions', '')}</li>
    </ul>
</div>
'''
@app.post("/api/sync_questions")
def api_sync_questions():
    sync_questions()
    return {"status": "Questions synced from DSA_Must_Solve_Problems.md to data.json."}

# --- Updated API Logic for fetching questions ---
@app.get("/api/questions", response_model=List[Question])
def get_questions():
    data = load_data()
    for q in data:
        # Calculate derived metrics
        q['total_time_spent'] = sum(log['time_taken'] for log in q['logs'])
        q['accuracy'] = calculate_accuracy(q['logs'])
        
        # Calculate Revision Logic
        interval, ease = get_spaced_repetition_values(q['logs'], q.get('ease_factor', 2.5), q.get('interval_days', 0))
        q['interval_days'] = interval
        q['ease_factor'] = ease
        
        if q['logs']:
            last_date = datetime.strptime(q['logs'][-1]['date'], "%Y-%m-%d")
            q['next_revision'] = (last_date + timedelta(days=interval)).strftime("%Y-%m-%d")
        else:
            q['next_revision'] = datetime.now().strftime("%Y-%m-%d")
            
        q['suggestions'] = get_suggestions(q['accuracy'], q['revision_status'], q['pattern'], interval)
        q['difficulty'] = calculate_difficulty_from_time(q['logs'][-1]['time_taken'] if q['logs'] else 0)
    return data

@app.post("/api/questions", response_model=Question)
def add_question(q: Question):
    data = load_data()
    q.id = max([x['id'] for x in data], default=0) + 1
    q.logs = []
    data.append(q.dict())
    save_data(data)
    return q

@app.put("/api/questions/{qid}", response_model=Question)
def update_question(qid: int, q: Question):
    data = load_data()
    for i, item in enumerate(data):
        if item['id'] == qid:
            data[i] = q.dict()
            save_data(data)
            return q
    raise HTTPException(status_code=404, detail="Question not found")

@app.post("/api/questions/{qid}/log", response_model=Question)
def add_log(qid: int, log: dict):
    data = load_data()
    for q in data:
        if q['id'] == qid:
            # Only store logic, code, and time_taken from the log
            log_entry = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "logic": log.get("logic", ""),
                "code": log.get("code", ""),
                "time_taken": log.get("time_taken", 0)
            }
            q['logs'].append(log_entry)
            save_data(data)
            # Optionally update derived fields if needed
            return q
    raise HTTPException(status_code=404, detail="Question not found")

@app.put("/api/questions/{qid}/status", response_model=Question)
def update_status(
    qid: int,
    category: str = Body(...),
    coverage_status: str = Body(...),
    revision_status: str = Body(...)
):
    data = load_data()
    for i, q in enumerate(data):
        if q['id'] == qid:
            q['category'] = category
            q['coverage_status'] = coverage_status
            q['revision_status'] = revision_status
            save_data(data)
            return q
    raise HTTPException(status_code=404, detail="Question not found")

@app.post("/api/questions/{qid}/validate")
def validate_question(qid: int):
    data_list = load_data()
    question = next((q for q in data_list if q['id'] == qid), None)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    prompt = f"""
You are an expert DSA Tutor and Spaced Repetition System (SRS). 
Your task is to analyze a student's session and update the question metadata.

### 📥 INPUT DATA (Current Question Object):
{json.dumps(question, ensure_ascii=False)}

### 🎯 TASK 1: VALIDATION
- If the input is empty or complete keyboard mashing, mark `correct = false`.
- If the student attempts a solution but uses the wrong strategy (e.g., Sorting by Start Time), mark `correct = false` but acknowledge that it was a **valid attempt at a sub-optimal strategy**.

### 🎯 TASK 2: TECHNICAL ANALYSIS (Activity Selection)
- Strategy Matching: Compare the student's logic and code against the optimal strategy for the {question['pattern']} pattern and the specific problem {question['title']}.
- The "Why" Analysis: 
      - If Correct: Explain why this specific greedy choice (or logic) leads to the global optimum.
      - If Incorrect: Explain the "Greedy Trap" or logical flaw they fell into (e.g., "Sorting by start time fails because a long early task can block multiple shorter tasks").
- Complexity Check: Verify if the time complexity matches the optimal $O(n \log n)$ or $O(n)$.


### 🎯 TASK 3: METADATA UPDATE (SRS Logic)
Update the following fields in the `updated_question`:
1. **accuracy**: 0-100 based on the current attempt.
2. **coverage_status**: Set to "Covered" only if a valid attempt was made.
3. **revision_status**: 
    - "Mastered" if accuracy > 90%.
    - "Needs Work" if accuracy < 60% but is a valid attempt.
    - "Pending" if the attempt was gibberish.
4. **ease_factor (EF)**: 
    - Decrease EF if accuracy is low. 
    - If accuracy < 60%, set $EF = max(1.3, EF - 0.2)$.
5. **interval_days**: 
    - If wrong/gibberish, set to 1 day. 
    - If correct, $Interval = Interval \times EF$.
6. **next_revision**: Calculate the date based on `today` (2026-04-20) + `interval_days`.
7. **suggestions**: Create a concise, one-sentence summary of WHY the attempt succeeded or failed based on the "Why Analysis" in Task 2. (e.g., "Correct! Sorting by finish time minimizes room usage.")

### 📋 JSON RESPONSE REQUIREMENTS:
Return ONLY a valid JSON object. No markdown. No preamble.
**Required Schema:**
{{
    "correct": boolean,
    "gap_analysis": "HTML string...",
    "gap_explanation": "Plain text...",
    "correction_suggestion": "The optimal implementation hint...",
    "updated_fields": {{
        "accuracy": float,
        "revision_status": "string",
        "next_revision": "YYYY-MM-DD",
        "ease_factor": float,
        "interval_days": int,
        "suggestions": "A concise summary of WHY their approach worked or failed. Example: 'Correct! Sorting by finish time works because it minimizes the resource usage per task. Keep it up!'"
    }}
}}
"""
    try:
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        client = openai.OpenAI()
        response = client.chat.completions.create(
    model="gpt-4o-mini", # 4o-mini is much better at avoiding hallucinations than 3.5
    messages=[
        {"role": "system", "content": "You are a strict DSA tutor. If input is gibberish, mark it incorrect. Output strictly JSON."},
        {"role": "user", "content": prompt}
    ],
    response_format={ "type": "json_object" },
    max_tokens=1000,
    temperature=0 # Zero temperature prevents creative hallucinations
)
        

        def safe_parse_dsa_response(raw_text):
            try:
                # 1. Strip whitespace
                text = raw_text.strip()
                
                # 2. Extract JSON if AI wrapped it in ```json blocks
                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                if json_match:
                    text = json_match.group(0)
                
                # 3. Final attempt to load
                return json.loads(text)
            except json.JSONDecodeError as e:
                # Debugging: Find exactly where the character error is
                print(f"Failed at char {e.pos}: {raw_text[max(0, e.pos-20):e.pos+20]}")
                return None

        raw_response = response.choices[0].message.content
        raw_response = raw_response.strip()
        data = safe_parse_dsa_response(raw_response)
         
    
         
        if data and "updated_fields" in data:
            # 1. Extract the new values from the AI
            updates = data["updated_fields"]

            # 2. Update all fields except logs
            update_question_fields_except_logs(question, updates)

            # 3. Explicitly set statuses based on AI 'correct' field
            if data.get("correct"):
                question["coverage_status"] = "Covered"
                question["revision_status"] = "Mastered"
            else:
                question["coverage_status"] = "Covered"
                question["revision_status"] = "Needs Work"

            # 4. Persistence: Write the updated list back to your JSON file
            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(data_list, f, indent=4, ensure_ascii=False)

            print(f"✅ Metadata updated for: {question['title']}")
        else:
            print("❌ AI returned invalid structure or gibberish.")
        return data
 
    except Exception as e:
        return {"correct": False, "gap_analysis": f"OpenAI validation failed: {e}"}
