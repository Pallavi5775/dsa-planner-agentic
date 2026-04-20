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
DATA_FILE = "data.json"

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

@app.post("/sync_questions")
def api_sync_questions():
    sync_questions()
    return {"status": "Questions synced from DSA_Must_Solve_Problems.md to data.json."}

# --- Updated API Logic for fetching questions ---
@app.get("/questions", response_model=List[Question])
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

@app.post("/questions", response_model=Question)
def add_question(q: Question):
    data = load_data()
    q.id = max([x['id'] for x in data], default=0) + 1
    q.logs = []
    data.append(q.dict())
    save_data(data)
    return q

@app.put("/questions/{qid}", response_model=Question)
def update_question(qid: int, q: Question):
    data = load_data()
    for i, item in enumerate(data):
        if item['id'] == qid:
            data[i] = q.dict()
            save_data(data)
            return q
    raise HTTPException(status_code=404, detail="Question not found")

@app.post("/questions/{qid}/log", response_model=Question)
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

@app.put("/questions/{qid}/status", response_model=Question)
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

@app.post("/questions/{qid}/validate")
def validate_question(qid: int):
    data = load_data()
    question = next((q for q in data if q['id'] == qid), None)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    payload = {k: v for k, v in question.items() if k != 'logs'}
    payload['log'] = question['logs'][-1] if question['logs'] else {}
    prompt = f"""
You are an expert DSA tutor. Given the following question and a student's latest session log, analyze if the solution is correct and provide a gap analysis. Respond in JSON with fields: correct (true/false), gap_analysis (HTML string, formatted for direct display in a web app, not plain text).

Question:
{payload['title']} (Pattern: {payload['pattern']})
Category: {payload['category']}
Revision Status: {payload['revision_status']}

Student Log:
Logic: {payload['log'].get('logic', '')}
Code: {payload['log'].get('code', '')}
Time Taken: {payload['log'].get('time_taken', '')} minutes
"""
    try:
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.2
        )
        import json as pyjson
        import re
        content = response.choices[0].message.content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return pyjson.loads(match.group(0))
        else:
            return {"correct": False, "gap_analysis": content.strip()}
    except Exception as e:
        return {"correct": False, "gap_analysis": f"OpenAI validation failed: {e}"}
