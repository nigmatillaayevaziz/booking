# UzBooking Bot

Production-oriented Telegram booking backend built with Python 3.12, aiogram 3, FastAPI, PostgreSQL, Redis and Celery.

The approved functional specification is [TZ v1.1](../docs/TZ_v1.1.md).

## Implemented

- bilingual registration, verified self-contact, versioned consent and phone updates;
- complete passenger booking flow: route, date, transport, trip, passenger count, pickup and names;
- 24-hour Redis FSM with unfinished-booking resume/restart handling;
- passenger order history with active/completed/cancelled sections;
- two-step cancellation with BR-08 refund preview and unpaid-hold protection;
- signed QR ticket generation and ticket resend;
- localized prices, help and settings menus;
- notification preferences and 30-day personal-data deletion requests;
- PostgreSQL relational model for users, routes, fares, trips, bookings, payments, refunds and audit;
- application and DB-level `taxi > bus > train` fare validation and lowercase enum contracts;
- transactional seat hold using `SELECT FOR UPDATE`;
- per-user active-hold locking and 15-minute hold expiration with `SKIP LOCKED` processing;
- cancellation/refund calculation and strict booking state transitions;
- manual payment confirmation service with idempotent external ID;
- transactional notification outbox, localized payment reminder and Telegram retry worker;
- booking-event history, admin payment audit and per-request IDs;
- webhook secret verification, readiness/liveness checks and atomic Redis rate limiting;
- Alembic bootstrap migration with roles, transport types and 14 regions;
- unit tests plus a 50-request PostgreSQL concurrency test definition.

Still planned: Payme/Click adapters, full operator/admin/driver panels, 24-hour and 2-hour trip reminders, recurring trip generation, statistics/export and deployment monitoring.

## Requirements

- Python 3.12+
- Docker with Compose, or PostgreSQL 16 and Redis 7
- public HTTPS domain for Telegram webhook

## Local setup

```powershell
.\scripts\bootstrap-dev.ps1
# Replace PUBLIC_BASE_URL and SUPPORT_CONTACT in .env before a real deployment.
docker compose up -d postgres redis
docker compose run --rm bot alembic upgrade head
docker compose up -d bot worker beat
```

The bootstrap script imports the existing workspace `BOT_TOKEN` without printing it and generates unique
local secrets. It refuses to overwrite an existing `bot/.env` unless `-Force` is explicitly supplied.

Generate secrets before startup:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Never commit `.env`.

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\alembic upgrade head
.venv\Scripts\pytest
.venv\Scripts\ruff check .
.venv\Scripts\mypy app
```

For the real concurrency test, set `TEST_POSTGRES_DSN` to a disposable PostgreSQL database. The test drops and recreates its schema.

Current local quality gate:

```powershell
.venv\Scripts\python -m compileall -q app tests migrations
.venv\Scripts\pytest
.venv\Scripts\ruff check .
.venv\Scripts\mypy app
```

## Production checklist

1. Use managed secrets and unique keys for every environment.
2. Run migrations before application rollout.
3. Run exactly one Celery Beat instance.
4. Enable PostgreSQL backups and perform restore tests.
5. Enable Redis AOF.
6. Configure Sentry and infrastructure metrics.
7. Restrict the runtime DB role; `audit_log` must not allow UPDATE/DELETE.
8. Run payment providers in sandbox before enabling feature flags.
