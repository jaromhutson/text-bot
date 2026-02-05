# Text-Bot Deployment Documentation

## Overview

Text-bot is a FastAPI SMS bot for managing Tidbit's 8-week GTM (Go-To-Market) launch plan. It sends daily task reminders, accepts natural language commands via SMS, and uses Claude AI to help with task management.

**Repository:** https://github.com/jaromhutson/text-bot
**Live URL:** https://text-bot-production.up.railway.app
**Twilio Number:** (your toll-free number)

---

## Architecture

- **Framework:** FastAPI + uvicorn
- **Database:** SQLite with aiosqlite (persisted on Railway volume at `/data/gtm_bot.db`)
- **AI:** Claude Haiku 4.5 with tool use for SMS processing
- **SMS:** Twilio (toll-free number)
- **Scheduler:** APScheduler AsyncIOScheduler
- **Hosting:** Railway (Hobby plan, $5/mo)

---

## Deployment Timeline (2026-02-05)

### Step 0: Security Hardening
Updated `.gitignore` with:
```
*.db-wal
*.db-shm
.DS_Store
.env.local
.env.*.local
*.log
.pytest_cache/
.coverage
```

### Step 1: Git + GitHub
- Initial commit created with all project files
- Public repo created at https://github.com/jaromhutson/text-bot

### Step 2: Railway Setup
- Created Railway project from GitHub repo
- Added volume mounted at `/data` for SQLite persistence
- Configured environment variables:
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`
  - `USER_PHONE`
  - `ANTHROPIC_API_KEY`
  - `ADMIN_API_KEY`
  - `TIMEZONE=America/Los_Angeles`
  - `DATABASE_URL=/data/gtm_bot.db`
- Generated public domain: `text-bot-production.up.railway.app`

### Step 3: Twilio Webhook
- Configured webhook in Twilio Console:
  - URL: `https://text-bot-production.up.railway.app/webhook/sms`
  - Method: HTTP POST
- Note: Toll-free verification pending (may take a few days for outbound SMS)

### Step 4: Plan Activation
- Activated GTM plan with start date: **2026-02-10**
- 213 tasks scheduled across 8 weeks
- Launch day: **April 3, 2026** (Week 8, Day 53)

---

## GTM Plan Structure

| Phase | Name | Tasks | Days |
|-------|------|-------|------|
| 1 | Foundation Building | 32 | 0-4 |
| 2 | Content & Landing Page | 27 | 7-11 |
| 3 | Outreach & Assets | 27 | 14-18 |
| 4 | Coming Soon & Submission | 27 | 21-25 |
| 5 | Visual Polish & Pre-Launch | 28 | 28-32 |
| 6 | Launch Prep & Activation | 27 | 35-39 |
| 7 | Final Checks & Rehearsal | 28 | 42-46 |
| 8 | Launch Week | 17 | 49-53 |

**Total:** 213 tasks over 54 days (8 weeks)

---

## Scheduled Messages

- **Daily tasks:** 8:00 AM Pacific, every day
- **Weekly review:** 6:00 PM Pacific, Sundays

---

## Key Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | Basic health check |
| `/health/ready` | GET | None | Readiness check (DB connected) |
| `/webhook/sms` | POST | Twilio signature | Incoming SMS handler |
| `/admin/activate` | POST | Bearer token | Activate plan with start date |
| `/admin/tasks` | GET | Bearer token | List all tasks |
| `/admin/tasks/{id}` | PATCH | Bearer token | Update task status |

---

## Admin API Key

```
9d7e9fd4a7168628286b180737929ab96aeb92886540c53ee83bc00a24eb5f05
```

Use in Authorization header: `Bearer <key>`

---

## Troubleshooting

### App won't start
Check Railway logs for missing environment variables. Required:
- `ANTHROPIC_API_KEY` (will crash without it)
- `DATABASE_URL` should point to `/data/gtm_bot.db` (requires volume)

### SMS not sending
- Check toll-free verification status in Twilio Console
- Inbound SMS works immediately; outbound may be blocked until verified

### Database issues
- SQLite file is at `/data/gtm_bot.db` on Railway volume
- WAL mode enabled for better concurrency
- Database is seeded automatically on first startup

---

## Files Overview

```
text-bot/
├── app/
│   ├── __init__.py
│   ├── config.py          # Settings from environment
│   ├── database.py        # SQLite connection management
│   ├── main.py            # FastAPI app + lifespan
│   ├── models.py          # Pydantic models
│   ├── data/
│   │   ├── gtm_plan.py    # 213 tasks + 8 phases
│   │   └── seed.py        # Database seeding
│   ├── routers/
│   │   ├── admin.py       # Admin endpoints
│   │   ├── health.py      # Health checks
│   │   └── webhooks.py    # Twilio SMS webhook
│   └── services/
│       ├── ai.py          # Claude integration
│       ├── plans.py       # Plan management
│       ├── scheduler.py   # APScheduler setup
│       ├── sms.py         # Twilio SMS sending
│       └── tasks.py       # Task CRUD operations
├── railway.toml           # Railway deployment config
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
└── .gitignore
```

---

## Next Steps

1. Wait for toll-free verification to complete
2. Test by texting the Twilio number
3. First daily SMS arrives February 10, 2026 at 8:00 AM PT
4. Launch day is April 3, 2026
