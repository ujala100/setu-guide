# Environment variables — name sheet

- **Updated:** 2026-11-13
- **Owner:** Aditya (DevOps 1)
- **Rule:** names only. Values live in the host environment (or a local `.env` that git ignores) — never in a repository, PR, log or ticket.
- 🔒 = secret. Store it in the host's secret manager.
- "planned" = the name is reserved but the code does not read it yet.

## Setu Guide (FastAPI) — `ujala100/setu-guide`

| Variable | Purpose | Used by | Dev | Staging | Prod | Secret |
|---|---|---|---|---|---|---|
| `USE_MOCK` | `true` = template mock reply, no LLM call | Guide | local `.env` | host env | host env | no |
| `LLM_PROVIDER` | LLM vendor name | Guide | local `.env` | host env | host env | no |
| `LLM_API_KEY` | Provider API key (required when `USE_MOCK=false`) | Guide | — | host env | host env | 🔒 |
| `LLM_TIMEOUT_SECONDS` | Outbound LLM time budget | Guide | local `.env` | host env | host env | no |
| `RATE_LIMIT_PER_USER` | Per-user limit, `<count>/<period>` | Guide | local `.env` | host env | host env | no |
| `RATE_LIMIT_PER_IP` | Per-IP limit, `<count>/<period>` | Guide | local `.env` | host env | host env | no |
| `TRUSTED_PROXY` | `true` only behind a reverse proxy we control | Guide | local `.env` | host env | host env | no |
| `CACHE_ENABLED` | Enable the response cache | Guide | local `.env` | host env | host env | no |
| `CACHE_TTL_SECONDS` | Cache entry TTL | Guide | local `.env` | host env | host env | no |
| `CACHE_MAX_ITEMS` | Max cached entries | Guide | local `.env` | host env | host env | no |
| `LOG_LEVEL` | Log verbosity | Guide | local `.env` | host env | host env | no |
| `INTERNAL_API_KEY` | Inbound key for service-to-service calls (only when auth is enabled) | Guide | — | planned | planned | 🔒 |
| `AUTH_METHOD` | `api_key` or `bearer` (branch `feature/auth-tests`) | Guide | — | planned | planned | no |

## Node backend — `Bharathgoud07/Sambandh-Setu`

| Variable | Purpose | Used by | Dev | Staging | Prod | Secret |
|---|---|---|---|---|---|---|
| `PORT` | HTTP port | Backend | local `.env` | host env | host env | no |
| `NODE_ENV` | Runtime mode | Backend | local `.env` | host env | host env | no |
| `MONGODB_URI` | MongoDB Atlas connection string (contains credentials) | Backend | local `.env` | host env | host env | 🔒 |
| `JWT_SECRET` | Signs session tokens; at least 32 characters (enforced at startup) | Backend | local `.env` | host env | host env | 🔒 |
| `GUIDE_SERVICE_URL` | Base URL of Setu Guide; the `/guide/chat` call lands in D1-16/D2-04 | Backend | — | host env | host env | no |

## Expo frontend — `karanpandeyklk/Setu_app`

| Variable | Purpose | Used by | Dev | Staging | Prod | Secret |
|---|---|---|---|---|---|---|
| `EXPO_PUBLIC_API_URL` | Node backend base URL (bundled into the app — public) | Frontend | local `.env` | EAS/host env | EAS/host env | no |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | Google OAuth web client ID (public) | Frontend | local `.env` | EAS/host env | EAS/host env | no |

## Reserved names (not read by code yet)

| Variable | Purpose | Owner |
|---|---|---|
| `EMAIL_API_KEY` | Transactional email provider key | DevOps 2 |
| `STORAGE_*` | Photo storage credentials | DevOps 2 |
| `CORS_ORIGINS` | Allowed browser origins (currently `cors()` is open) | DevOps 2 |

## Notes

- The frontend never holds a secret: every `EXPO_PUBLIC_*` value ships inside the app bundle.
- The backend never holds the Guide key today — when Sakshi adds the `/guide/chat` call, any Guide credential goes in the host env, not in code.
- Rotating `JWT_SECRET` (D1-02) invalidates every existing session by design.
