# Dependency Policy

This project keeps dependency upgrades small and deliberate. The current goal is
stability, not broad modernization.

## Frozen Core Stack

Keep these versions frozen until a dedicated compatibility PR:

- `fastapi==0.110.0`
- Starlette transitively installed by FastAPI, currently `0.36.3`
- `httpx==0.27.2`

Do not casually upgrade `httpx` to `0.28.x`. Starlette `0.36.x` uses the older
`TestClient` integration that passes `app=` into `httpx.Client`; `httpx 0.28+`
removed that shortcut and can break tests before application behavior is even
checked.

## Upgrade Rules

Dependency upgrades should be done as small batch PRs:

- keep related packages together, for example FastAPI, Starlette, and httpx;
- keep unrelated packages out of the same PR;
- require green CI before merging;
- add or run regression tests that cover the touched behavior;
- document any compatibility notes in the PR description.

## Risky Dependencies

These dependencies need separate plans before changing them:

- `bleach`: used for HTML sanitization, so replacement or upgrade work is a
  security-sensitive change.
- `python-multipart`: used on upload paths; upgrade only with upload regression
  coverage.
- `cloudinary`: affects media upload behavior and external service integration.
- `psycopg2-binary`: acceptable for local/test installs, but production should
  have an explicit PostgreSQL driver strategy.
