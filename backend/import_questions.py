import re
import os
import json
from datetime import datetime

DSA_FILE = "../DSA_Must_Solve_Problems.md"
DATA_FILE = "data.json"

# Parse the DSA_Must_Solve_Problems.md file and add questions to data.json if not present

def parse_questions():
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
                    "logs": [],
                })
    return questions

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

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

if __name__ == "__main__":
    sync_questions()
    print("Questions synced from DSA_Must_Solve_Problems.md to data.json.")
