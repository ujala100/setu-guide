# Gitleaks history scan — D1-03

- **Date:** 2026-11-13
- **Tool:** gitleaks 8.30.1
- **Owner:** Aditya (DevOps 1)
- **Scope:** full git history of all branches in the three Setu repositories
- **Command:**
  `gitleaks git <repo> --config <repo>/.gitleaks.toml --log-opts="--all" --redact --exit-code 1`

## Result

| Repository | Commits scanned | Real secrets | Findings before allowlist | Disposition |
|---|---|---|---|---|
| `ujala100/setu-guide` | 86 | **0** | 8 | All synthetic / documentation placeholders — allowlisted |
| `Bharathgoud07/Sambandh-Setu` | 2 | **0** | 10 | Seed fixture IDs (`reflection-01` … `reflection-10`) — allowlisted |
| `karanpandeyklk/Setu_app` | 7 | **0** | 0 | Clean |

**No real secret was found in any repository or any commit. No history rewrite is required.**

## Findings reviewed (all false positives)

### `setu-guide`

| File (historical commit) | Rule | What it actually is |
|---|---|---|
| `docs/integration_handover.md` | curl-auth-header | `X-API-Key: your-real-key` — documentation placeholder |
| `tests/integration/test_auth.py` | generic-api-key | Synthetic test key |
| `tests/failure/test_log_privacy.py` | generic-api-key | Synthetic log-hygiene marker key |
| `docs/verification/privacy-log-audit.md` (lines 58, 86) | generic-api-key | Synthetic `sk-…` example used in a log-hygiene doc |

### `Sambandh-Setu`

| File | Rule | What it actually is |
|---|---|---|
| `backend/seed/b2Fixtures.js` (10 lines) | generic-api-key | Seed data IDs `reflection-01` … `reflection-10` |

### `Setu_app`

No findings.

## How the false positives are handled

Narrow allowlists in each repo's `.gitleaks.toml` (added in D1-04):

- **guide:** one exact placeholder (`your-real-key`) plus three test/documentation paths that contain only synthetic values.
- **backend:** one regex for the seed IDs (`^reflection-\d{2}$`).
- **frontend:** no allowlist — zero findings.

Anything not on those lists still fails the scan.

## Re-run locally

```bash
gitleaks git . --config .gitleaks.toml --log-opts="--all" --redact --exit-code 1
```
