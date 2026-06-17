# Developer Runbook

This runbook covers the common local development workflow for Furuzon.

## Local Setup Without Docker

Use the project Python version:

```bash
python3 --version
cat .python-version
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create local environment settings:

```bash
cp config/.env.example config/.env
```

`app/config.py` loads `config/.env` first. A root `.env` is also supported as a
fallback only when `config/.env` is absent.

Start or provision PostgreSQL locally, then set `DATABASE_URL` in
`config/.env`, for example:

```text
DATABASE_URL=postgresql://user:password@localhost/dbname
```

Apply migrations:

```bash
alembic upgrade head
```

Run the app:

```bash
uvicorn main:app --reload
```

## Docker Setup

See [docker.md](docker.md) for the full local/dev Docker guide.

Common commands:

```bash
docker compose up --build
docker compose run --rm app alembic upgrade head
```

Docker Compose is local/dev only. Do not use its development secrets or database
exposure assumptions for production.

## Testing

Run the standard local checks:

```bash
python3 -m compileall -q app main.py
python3 -m unittest -q
python3 -m pytest -q
bash scripts/smoke_test.sh
```

## Before Commit Checklist

```bash
git status --short
git diff --check
bash scripts/smoke_test.sh
python3 -m pytest -q
```

Review the staged diff before committing:

```bash
git diff --cached
```

## Notes

- Cloudinary dummy values are enough for app import but not for real upload
  flows that call Cloudinary.
- Docker Compose is local/dev only.
- Do not commit real `.env` files or secrets.
- Sensitive uploads are stored in private storage under `data/private_uploads/`.
- Public/runtime uploads can be written under `static/uploads/`,
  `static/materials/`, and legacy `static/documents/`.
- Dependency upgrade rules live in [dependency_policy.md](dependency_policy.md).
