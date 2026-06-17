# Docker Development

This Docker setup is for local development only. It does not change application
startup, storage paths, dependency versions, or migration behavior.

## Start

Build and start the local stack:

```bash
docker compose up --build
```

The app is published on `http://localhost:8000`.

## Migrations

Automatic migrations are disabled in compose with
`AUTO_APPLY_MIGRATIONS=false`. Apply migrations manually after the database is
healthy:

```bash
docker compose run --rm app alembic upgrade head
```

Keep this explicit unless you deliberately decide to enable startup migrations
for a controlled environment.

## Environment

The compose file provides local development values for the variables required at
import time:

- `SECRET_KEY`
- `DATABASE_URL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

It also sets:

- `APP_ENV=development`
- `AUTO_APPLY_MIGRATIONS=false`
- `ENABLE_API_DOCS=true`

The Cloudinary values are dummy development values. Workflows that actually
upload to Cloudinary still require real Cloudinary credentials.

## Persistent Data

Compose uses named volumes for runtime data:

- `postgres_data` for PostgreSQL data
- `private_uploads` for `/app/data/private_uploads`
- `static_uploads` for `/app/static/uploads`
- `static_materials` for `/app/static/materials`
- `static_documents` for legacy `/app/static/documents`

These paths can contain user uploads or database state and should not be treated
as disposable container filesystem data.

## Production Notes

Do not use this compose file as production configuration without review:

- replace all development secrets;
- keep `AUTO_APPLY_MIGRATIONS=false` unless startup migrations are deliberately
  enabled;
- do not expose the database publicly;
- provide real Cloudinary credentials if Cloudinary-backed upload flows are used;
- keep uploaded files and PostgreSQL data on persistent storage.
