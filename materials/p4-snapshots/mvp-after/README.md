# P3 Variant 2 MVP

Security-first FastAPI MVP for `P3` variant 2: oil and gas asset maintenance.

## Implemented scope

Business entities:

- `users`
- `assets`
- `maintenance_requests`

Security support entities:

- `refresh_tokens`
- `audit_logs`

Roles:

- `engineer`
- `supervisor`
- `technical admin`

Business flow:

- supervisor registers an asset
- engineer creates a maintenance request
- supervisor assigns the request
- assigned engineer starts work
- assigned engineer completes work
- supervisor or technical admin exports a maintenance summary report

## Security controls

- JWT access tokens with short lifetime
- refresh token rotation and logout
- password hashing via `pwdlib`
- role-based and object-level authorization
- audit logging for critical actions
- sensitive-field redaction in logs
- request body size limit middleware
- neutral server error handling
- strict input validation through Pydantic schemas

## Quick start

1. Copy `.env.example` to `.env` and set:
   - `SECRET_KEY`
   - `BOOTSTRAP_ADMIN_PASSWORD`
   - `BOOTSTRAP_STAFF_PASSWORD`
   - `BOOTSTRAP_USER_PASSWORD`
2. Create the virtual environment:

```powershell
py -3.13 -m venv .venv
```

3. Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install bandit pip-audit pre-commit pytest pytest-cov httpx ruff mypy==1.17.1
```

4. Apply migrations:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

5. Seed demo data:

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

6. Run the API:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

## Default demo accounts

Seed uses the credentials from `.env`:

- bootstrap admin -> `technical admin`
- bootstrap staff -> `supervisor`
- bootstrap user -> `engineer`

## Main endpoints

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`
- `POST /api/v1/assets`
- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `POST /api/v1/maintenance-requests`
- `GET /api/v1/maintenance-requests`
- `GET /api/v1/maintenance-requests/{request_id}`
- `PATCH /api/v1/maintenance-requests/{request_id}/status`
- `GET /api/v1/reports/maintenance-summary`
- `GET /api/v1/health`

## Verification commands

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe app tests
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\bandit.exe -c bandit.yaml -r app
$env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pip-audit.exe
```

## Current verification status

- `pytest`: passed
- `ruff`: passed
- `mypy`: passed
- `Bandit`: no issues identified
- `pip-audit`: no known vulnerabilities found

## Submission direction

The coding part of the MVP is complete for variant 2.
The next phase is report packaging:

- structural and business-flow diagrams
- source code security analysis narrative
- code snippets proving protections
- findings table and prevented-risk table
- final `Bandit` and `pip-audit` outputs
