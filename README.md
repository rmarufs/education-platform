# Furuzon

Furuzon is a server-rendered educational platform for courses, groups,
organizations, lessons, homework, materials, reviews, notifications, and admin
workflows.

## Tech Stack

- Python 3.11.8
- FastAPI with Jinja2 server-side rendering
- SQLAlchemy with PostgreSQL
- Alembic migrations
- Vanilla JavaScript and static CSS
- Cloudinary for selected media upload flows
- `unittest` and `pytest` regression tests
- GitHub Actions minimal CI
- Local/dev Docker Compose setup

## Local Setup Without Docker

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

Edit `config/.env` and provide at least:

- `SECRET_KEY`
- `DATABASE_URL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

The app loads `config/.env` first and falls back to root `.env` only when
`config/.env` does not exist.

Apply database migrations:

```bash
alembic upgrade head
```

Run the app:

```bash
uvicorn main:app --reload
```

## Docker Setup

The Docker Compose setup is for local development only:

```bash
docker compose up --build
```

Apply migrations manually:

```bash
docker compose run --rm app alembic upgrade head
```

See [docs/docker.md](docs/docker.md) for volumes, environment variables, and
production warnings.

## Tests And Smoke Checks

Run the same local quality gate used during Phase 2:

```bash
python3 -m compileall -q app main.py
python3 -m unittest -q
python3 -m pytest -q
bash scripts/smoke_test.sh
```

`scripts/smoke_test.sh` also runs the i18n key checker and pytest suite.

## Migrations

Alembic migrations live in `alembic/versions/`.

Apply existing migrations:

```bash
alembic upgrade head
```

Create a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Do not rewrite applied migration history without a dedicated migration task.

## Developer Docs

- [docs/development.md](docs/development.md): developer runbook and checklist.
- [docs/docker.md](docs/docker.md): local Docker guide.
- [docs/dependency_policy.md](docs/dependency_policy.md): dependency upgrade
  policy and risky dependency notes.
- [docs/architecture.md](docs/architecture.md): architecture and repository
  structure notes.

## Runtime Data

Runtime uploads and private files can be written under:

- `data/private_uploads/`
- `static/uploads/`
- `static/materials/`
- `static/documents/` for legacy paths

Do not commit real `.env` files, secrets, local databases, logs, backups, or
uploaded user files.
