"""Conftest for integration tests.

The `client`, `client_no_raise`, `fresh_state` and `set_env` fixtures are
defined in tests/conftest.py and apply to this directory as well.

API-key / Bearer auth is not implemented on `dev` (no `AUTH_METHOD`/`API_KEY`
in app/config.py, no app/api/auth.py), so the auth test module and its
`client_with_api_key` / `client_with_bearer_token` fixtures live on the
`feature/auth-tests` branch until auth lands. They were removed here so this
branch tests only the contract `dev` actually exposes.
"""
