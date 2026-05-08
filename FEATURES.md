# DSA Revision Planner — Features

## Authentication
- **Google OAuth** — sign in with Google account
- **GitHub OAuth** — sign in with GitHub account (also grants repo access for storage)
- **JWT session tokens** — secure, stateless auth passed to frontend
- **Role-based access** — `admin` role for question management, `user` role for practice

---

## Question Management
- Browse all DSA questions with pattern, category, and difficulty
- Admin: create, update questions (title, pattern, category, difficulty)
- Admin: add hints per question
- AI-generated question descriptions on demand
- Bulk import questions from uploaded `.md` files
- Sync questions from `DSA_Must_Solve_Problems.md` (admin)

---

## Practice Logging
- Log a practice session per question (code, logic, time taken, correct/incorrect)
- View and edit the last log for any question
- Track hint usage per session

---

## Spaced Repetition Scheduling
- SM-2-style algorithm: ease factor + interval days per question per user
- `next_revision` date auto-calculated after every session
- **Configurable practice days** — set which weekdays (Mon–Sun) you practice; revision dates skip non-practice days
- Recalculate all revision dates when practice schedule changes

---

## AI Features (powered by Claude)

| Feature | What it does |
|---|---|
| **Session Validation** | After logging a session, AI checks your code/logic, scores accuracy, and writes a gap analysis |
| **Session Insights** | AI generates a motivating markdown insight (what went well, what to improve, key takeaway) |
| **Weekly Summary** | Every Sunday, AI summarises the week's sessions and commits it to your GitHub repo |
| **Hint Chat** | Per-question AI chat — ask for hints, explanations, or problem variations |
| **Variation Review** | Submit a problem variation + your code; AI reviews it |
| **Pattern Chat** | Chat with AI about any DSA pattern (e.g. "explain sliding window") |
| **Pattern Memo Generator** | AI generates a memory technique/mnemonic for a DSA pattern |

---

## GitHub Storage Integration
- Auto-creates a private `dsa-planner-data` repo on your GitHub account
- Commits each practice session as a JSON file
- Commits AI insight as a markdown file alongside each session
- Commits weekly AI summary markdown every Sunday
- View full history (all sessions + insights) from GitHub inside the app

---

## Pattern Notes
- Per-user notes per DSA pattern (e.g. "Two Pointers", "Sliding Window")
- Store memory techniques / mnemonics alongside notes
- AI can generate memory techniques via pattern chat

---

## Activity Tracking
- Activity heatmap — visualise practice frequency by date
- Timezone-aware activity view

---

## User Profile
- Avatar URL from OAuth provider
- GitHub username display
- OAuth provider shown (Google / GitHub)
