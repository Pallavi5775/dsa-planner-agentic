# DSA Revision Planner

A full-stack learning platform for practising and tracking Data Structure & Algorithm problems, built on a modular architecture consisting of a **Core Learning Platform** and an **AI/Agentic Layer**.

---

## Platform Architecture

The platform is structured with a modular IP model:

| Layer | Description |
|---|---|
| **Core Learning Platform** | Foundational educational system — SRS engine, question bank, progress tracking, learning methodology |
| **AI / Agentic Layer** | Autonomous agent orchestration, multi-agent pipelines, enterprise integrations |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy (async), Alembic |
| Frontend | Streamlit, Plotly |
| Database | PostgreSQL (asyncpg) |
| AI | Anthropic Claude API (Haiku) + OpenAI GPT-4o-mini |
| Auth | OAuth 2.0 (Google, GitHub, Microsoft), JWT |
| Storage | GitHub API, Microsoft OneDrive via Graph API |
| Notifications | Resend (email), Telegram Bot API, Microsoft Teams webhooks |
| Agent Protocol | MCP (Model Context Protocol) — 3 servers |
| Task Scheduling | asyncio background workers |

---

## Core Learning Platform

### Features

- **Spaced Repetition (SM-2)** — Calculates optimal revision dates based on accuracy, time taken, and hint usage
- **Question Bank** — DSA problems organised by pattern, category, and difficulty
- **Practice Logging** — Log code, logic, time taken, and correctness per session
- **Progress Tracking** — Coverage status, revision status, accuracy per question
- **Pattern Notes** — Store notes and AI-generated memory techniques per DSA pattern
- **Activity Heatmap** — Visual breakdown of practice frequency and streak
- **Hint Chat** — AI-powered mentor chat per question with multi-turn conversation history
- **Variation Generator** — Auto-generates 3 problem variations to deepen pattern understanding
- **Problem Descriptions** — Auto-generated problem statements with examples and constraints

### Authentication

- Google OAuth 2.0
- GitHub OAuth 2.0 (also grants repo access for storage)
- Microsoft OAuth 2.0 (grants OneDrive + Calendar access)
- JWT tokens — stateless, 7-day expiry
- Role-based access — `admin` (manage questions) / `user` (practice)

### Database Schema (`dsa` schema)

| Table | Purpose |
|---|---|
| `users` | Auth, preferences, OAuth tokens |
| `questions` | DSA problem bank |
| `practice_logs` | Per-session practice records |
| `user_question_progress` | SRS state, accuracy, AI feedback per user + question |
| `user_pattern_notes` | Pattern-level notes and memory techniques |
| `notifications` | In-app notification inbox |

---

## AI / Agentic Layer

### Multi-Agent Architecture

```
Claude Code / App Backend
        │
        ├── MCP Server: dsa-planner      (DB tools)
        ├── MCP Server: sharepoint       (OneDrive / Graph API tools)
        └── MCP Server: microsoft-graph  (Calendar, Teams, pipelines)
                │
                ▼
        Orchestrator Agent
        ├── Session Analyst Agent
        ├── Study Coach Agent
        ├── SharePoint Librarian Agent
        ├── Teams Notifier Agent
        └── Calendar Scheduler Agent
```

### Agents

| Agent | File | Role |
|---|---|---|
| **Orchestrator** | `services/orchestrator.py` | Coordinates all specialists, runs pipelines sequentially or in parallel |
| **Session Analyst** | `services/agent.py` | Queries practice history + weak areas before writing personalised session insights |
| **Study Coach** | `services/agent.py` | Reasons across due questions, weak areas, and streak to plan today's study session |
| **SharePoint Librarian** | `services/sharepoint_agent.py` | Manages session files, insights, and summaries in OneDrive |
| **Teams Notifier** | `services/teams_agent.py` | Formats and dispatches rich Teams card notifications |
| **Calendar Scheduler** | `services/calendar_agent.py` | Checks Outlook calendar for free slots, creates study block events |

### Orchestration Pipelines

**Post-Session Pipeline** — runs after every practice log
```
Session logged
  → Session Analyst  (queries DB history → personalised insight)
  → SharePoint save + Teams notification  [parallel]
```

**Weekly Review Pipeline** — runs every Sunday
```
Weekly review triggered
  → Study Coach + Weekly Summary Analyst  [parallel]
  → SharePoint save + Teams notify + Calendar schedule  [parallel fan-out]
```

**Daily Coaching Pipeline** — runs at user's configured notification hour
```
Daily coaching triggered
  → Study Coach + due questions fetch  [parallel]
  → Calendar scheduling + Teams notification
```

### Agent Tool Use

Each agent calls Claude with tool-use enabled. Claude queries real DB data before producing output:

| Tool | What it queries |
|---|---|
| `get_past_attempts` | All previous practice logs for a question |
| `get_user_weak_areas` | Patterns sorted by lowest accuracy |
| `get_user_stats` | Streak, sessions, time, pattern breakdown |
| `get_due_questions` | Questions overdue or due within N days |
| `get_question_details` | Question metadata |

### MCP Servers (3 total)

All three run as local stdio processes and connect automatically via `.claude/settings.json`.

#### `dsa-planner` — Core DB tools
| Tool | Purpose |
|---|---|
| `get_due_questions` | Questions due for revision |
| `get_user_stats` | Overall practice statistics |
| `get_weak_areas` | Patterns with accuracy below threshold |
| `get_past_attempts` | Full practice history for a question |
| `get_all_questions` | Browse question bank with filters |
| `get_user_progress` | Coverage + accuracy per question |
| `get_pattern_notes` | Pattern notes and memory techniques |
| `get_all_users` | List registered users |
| `run_study_coach` | Trigger the Study Coach agent |

#### `sharepoint` — OneDrive / Graph API tools
| Tool | Purpose |
|---|---|
| `sharepoint_list_sessions` | List session JSON files in OneDrive |
| `sharepoint_list_sessions_with_insights` | Sessions paired with AI insights |
| `sharepoint_save_session` | Upload a session to OneDrive |
| `sharepoint_save_summary` | Upload a weekly summary to OneDrive |
| `check_microsoft_connection` | Check if user has Microsoft connected |

#### `microsoft-graph` — Calendar, Teams, full pipelines
| Tool | Purpose |
|---|---|
| `get_calendar_events` | Upcoming Outlook events |
| `create_study_event` | Create a study block in Outlook |
| `run_calendar_scheduler_for_user` | Run Calendar Scheduler Agent |
| `send_teams_notification` | Send a Teams card via webhook |
| `run_teams_notifier_for_user` | Run Teams Notifier Agent |
| `run_weekly_review` | Trigger full weekly review pipeline |
| `run_daily_coaching` | Trigger full daily coaching pipeline |

### Microsoft Enterprise Integration

- **OneDrive Storage** — Sessions, AI insights, and summaries stored in `OneDrive/DSA-Planner/`
- **Outlook Calendar** — Auto-creates study block events with 15-minute reminders, tagged `DSA Study`
- **Microsoft Teams** — Rich adaptive card notifications via incoming webhook
- **Microsoft Graph API** — All Microsoft features call `https://graph.microsoft.com/v1.0` using `httpx`

---

## Project Structure

```
DSA_TRACKER/
├── backend/
│   ├── api/
│   │   ├── auth.py                  Google + GitHub OAuth
│   │   ├── microsoft_auth.py        Microsoft OAuth (login + connect)
│   │   ├── routes.py                Main API routes
│   │   └── notification_routes.py   Notification endpoints
│   ├── core/
│   │   ├── security.py              JWT creation + validation
│   │   └── utils.py                 SRS algorithm, scheduling utilities
│   ├── crud/
│   │   ├── question.py              Question CRUD + AI validation
│   │   └── user.py                  User CRUD + OAuth helpers
│   ├── db/
│   │   ├── base.py                  SQLAlchemy declarative base
│   │   ├── models.py                ORM models
│   │   └── session.py               Async session factory
│   ├── schemas/
│   │   ├── auth.py                  Auth schemas
│   │   └── question.py              Question + practice log schemas
│   ├── services/
│   │   ├── agent.py                 Core agent loop + tool-use functions
│   │   ├── ai_insights.py           Simple Claude prompt calls (fallback)
│   │   ├── calendar_agent.py        Outlook Calendar Scheduler Agent
│   │   ├── github_storage.py        GitHub repo storage
│   │   ├── notifications.py         Email + Telegram dispatch
│   │   ├── orchestrator.py          Multi-agent pipeline orchestrator
│   │   ├── sharepoint_agent.py      SharePoint Librarian Agent
│   │   ├── sharepoint_storage.py    Raw Graph API file operations
│   │   └── teams_agent.py           Teams Notifier Agent
│   ├── main.py                      FastAPI app + background workers
│   ├── mcp_server.py                MCP server — DB tools
│   ├── mcp_sharepoint.py            MCP server — SharePoint tools
│   ├── mcp_microsoft.py             MCP server — Graph API + pipelines
│   └── requirements.txt
├── frontend/
│   └── app.py                       Streamlit UI
├── alembic/
│   └── versions/                    Database migrations
├── .claude/
│   └── settings.json                MCP server configuration for Claude Code
└── README.md
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- PostgreSQL database
- Node.js 18+ (for Claude Code CLI, optional)

### 2. Create virtual environment and install dependencies

```powershell
cd DSA_TRACKER
python -m venv myenv
myenv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. Configure environment variables

Create `DSA_TRACKER/.env`:

```env
# Database
DB_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Auth
SECRET_KEY=your-secret-key
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:8501

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# GitHub OAuth
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# Microsoft OAuth
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=common

# AI
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Notifications (optional)
RESEND_API_KEY=
RESEND_FROM=DSA Planner <info@yourdomain.com>
TELEGRAM_BOT_TOKEN=
```

### 4. Run database migrations

```powershell
cd DSA_TRACKER
alembic upgrade head
```

### 5. Start the backend

```powershell
# Run from DSA_TRACKER/ — not from inside backend/
uvicorn backend.main:app --reload
```

### 6. Start the frontend

```powershell
cd frontend
streamlit run app.py
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

---

## Microsoft Azure Setup

To enable OneDrive, Calendar, and Teams features:

1. Go to [portal.azure.com](https://portal.azure.com) → Azure Active Directory → App registrations → New registration
2. Set redirect URI (only one needed):
   - `http://localhost:8000/api/auth/microsoft/callback`
3. Under **Certificates & secrets** → create a new client secret
4. Under **API permissions** → add delegated permissions:
   - `openid`, `email`, `profile`, `offline_access`
   - `Files.ReadWrite`
   - `Calendars.ReadWrite`
   - `ChannelMessage.Send` *(requires admin consent for Teams messaging)*
5. Copy **Application (client) ID**, **Client secret value**, and **Directory (tenant) ID** into `.env`

---

## Microsoft Teams Webhook Setup

1. In your Teams channel → **Connectors** → **Incoming Webhook** → Configure
2. Name it `DSA Planner` and copy the webhook URL
3. Store the URL in the user's `teams_webhook_url` field in the database

---

## Claude Code MCP Integration

After restarting Claude Code in this project, all 3 MCP servers connect automatically via `.claude/settings.json`.

**Example queries:**

```
"What questions are due for user 1 today?"
"Show me user 1's weakest DSA patterns"
"Run the weekly review pipeline for user 1 and schedule next week in Outlook"
"Send a Teams notification to user 1 with their study plan"
"List all sessions user 1 has stored in OneDrive"
"Create a study block in user 1's Outlook calendar for tomorrow at 9am"
```

---

## Production Deployment

```bash
# Backend (background)
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

# Frontend (background)
nohup streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0 > frontend.log 2>&1 &

# Check processes
ps aux | grep uvicorn
ps aux | grep streamlit

# Nginx (if using reverse proxy)
sudo nginx -t
sudo systemctl reload nginx
```

---

## Architectural Note

*"The platform is structured with a modular IP model where the foundational educational framework — learning methodology, spaced repetition engine, and base planner — remains the independent core product, while the advanced AI-driven orchestration, autonomous agent pipelines, and enterprise automation components form a separate commercial extension layer."*
