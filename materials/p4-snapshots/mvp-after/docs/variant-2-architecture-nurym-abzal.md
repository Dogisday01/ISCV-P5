# Practical Assignment 3

## Metadata

- Student: `РќСѓСЂС‹Рј РђР±Р·Р°Р»`
- Assignment: `Practical work No. 3`
- Variant: `2`
- Domain: `РќРµС„С‚РµРіР°Р·РѕРІР°СЏ РѕС‚СЂР°СЃР»СЊ - С‚РµС…РЅРёС‡РµСЃРєРѕРµ РѕР±СЃР»СѓР¶РёРІР°РЅРёРµ Р°РєС‚РёРІРѕРІ`
- Current stage: `architecture freeze v1, implementation not started`

## Architecture Freeze v1

This document is the fixed baseline for implementation.
All later coding work should follow this file unless we explicitly revise it.

### Final decisions

- Stack remains exactly aligned with the current `mvp` template.
- Framework: `FastAPI`.
- Database for MVP: `SQLite`.
- Generic `WorkflowItem` will be specialized into `MaintenanceRequest`.
- New business entity: `Asset`.
- Role mapping is fixed as:
  - `user` -> `engineer`
  - `staff` -> `supervisor`
  - `admin` -> `technical admin`
- Final business statuses are fixed as:
  - `open`
  - `assigned`
  - `in_progress`
  - `completed`
  - `cancelled`
- Export/report route is part of the MVP baseline and is not optional.
- The main report scenario is fixed to:
  - asset registration -> maintenance request creation -> assignment -> work start -> work completion.
- No frontend, file upload, external integration, background job, or notification subsystem is included in MVP `v1`.

### Out of scope for v1

- `dispatcher` as a separate role
- `rejected` as a separate status
- file attachments
- notifications
- external APIs
- analytics dashboard
- public registration
- complex reassignment workflow

## 1. What the assignment requires

### Variant 2 from the task

Variant 2 requires an MVP for:

- equipment registration;
- maintenance request creation;
- work closure by an engineer.

The explicit security focus from the task:

- server-side verification of rights for work status changes;
- restriction of report export;
- protection of internal service data.

### Global MVP requirements from the task

The final MVP must include at least:

- one complete business scenario for the chosen variant;
- authentication and authorization;
- a database;
- audit logging of critical actions;
- explicit prevention of common security mistakes;
- at least `3-5` API endpoints or equivalent functions;
- at least `2` roles;
- at least `3` database entities;
- test data;
- SAST and SCA results (`bandit`, `pip-audit`).

## 2. Current project base and how we should use it

The existing `mvp` project is already a strong universal backend skeleton:

- `FastAPI`
- JWT access tokens plus refresh rotation
- password hashing
- RBAC and object-level authorization pattern
- audit logging
- SQLAlchemy + Alembic
- `bandit`, `pip-audit`, `pytest`, `ruff`, `mypy`

This means we do not rebuild the project from scratch.

Instead, the correct strategy is:

1. Keep the common security/auth foundation unchanged as much as possible.
2. Adapt the generic `WorkflowItem` into the business object for variant 2.
3. Add one new business entity for equipment/assets.
4. Tighten authorization rules specifically around status transitions and export.
5. Extend tests and documentation for the assigned scenario.

### 2.1 Template-synchronized technology stack

To avoid changing stack mid-implementation, we explicitly stay within what the template already uses:

- `Python 3.13`
- `FastAPI`
- `SQLAlchemy 2`
- `Pydantic` / `pydantic-settings`
- `PyJWT`
- `pwdlib` with `Argon2` and `bcrypt`
- `Alembic`
- `SQLite`
- `pytest`
- `ruff`
- `mypy`
- `bandit`
- `pip-audit`

### 2.2 Important alignment notes

- The assignment allows `FastAPI` or `Flask`; the template is already `FastAPI`, so we keep `FastAPI`.
- The assignment allows `PostgreSQL` or `SQLite`; the template already defaults to `SQLite`, so we keep `SQLite` for MVP.
- The assignment asks for hashed passwords using `Passlib / bcrypt / PBKDF2`; the template already uses `pwdlib` with `Argon2` and `bcrypt`, which is acceptable and stronger than retrofitting a different password stack.
- The assignment asks for JWT with limited lifetime; the template already has short-lived access tokens and refresh-token handling.
- The template already includes security headers middleware, request body size limiting, neutral server-error handling and audit-log sanitization, so these controls must be preserved.

### 2.3 Template constraints we will not change

- auth remains under `app/api/routes/auth.py`
- token generation and verification remain under `app/core/security.py`
- audit logging remains under `app/services/audit.py`
- settings and secrets remain under `app/core/config.py`
- generic router registration style in `app/api/router.py` remains unchanged
- current testing and tooling stack remains unchanged

## 3. Fixed MVP interpretation for variant 2

### Business meaning

Our MVP…532 chars truncated…able:

1. supervisor creates asset;
2. engineer creates maintenance request for an existing asset;
3. supervisor assigns request;
4. assigned engineer moves request to `in_progress`;
5. assigned engineer closes request as `completed`;
6. supervisor or technical admin exports a restricted summary report.

### What is intentionally left out

To keep the product minimal and defensible, we do not include:

- file uploads
- image attachments
- complex notifications
- external ERP integration
- calendar planning
- multi-step approval chains
- offline mode
- public portal
- analytics dashboards beyond one restricted export/report endpoint

## 4. Target domain model

### Core business entities

Minimum target entities:

1. `users`
2. `assets`
3. `maintenance_requests`

Infrastructure and security entities already present and still needed:

4. `refresh_tokens`
5. `audit_logs`

### 4.1 `users`

Purpose:

- authenticated identities
- system roles
- ownership and assignment

Key fields already aligned with template:

- `id`
- `email`
- `full_name`
- `role`
- `password_hash`
- `is_active`
- `failed_login_attempts`
- `locked_until`
- `last_login_at`
- `created_at`

### 4.2 `assets`

Purpose:

- registered equipment units that can be serviced

Final fields:

- `id`
- `asset_code`
- `name`
- `category`
- `location`
- `status`
- `commissioned_at` optional
- `created_by_id`
- `created_at`
- `updated_at`

Security note:

- asset data is internal operational data
- creation and update must be restricted to internal roles

### 4.3 `maintenance_requests`

Purpose:

- record of a maintenance issue and its lifecycle

Final fields:

- `id`
- `asset_id`
- `title`
- `description`
- `issue_category`
- `priority`
- `status`
- `requested_date`
- `owner_id`
- `assigned_to_id`
- `closure_notes`
- `created_at`
- `updated_at`

### 4.4 Final status model

We use the following domain statuses:

- `open`
- `assigned`
- `in_progress`
- `completed`
- `cancelled`

Why:

- it matches the assignment wording directly
- it is easy to explain in the report
- authorization logic becomes clearer and testable

## 5. Fixed authorization model

### Role mapping

- `user` -> `engineer`
- `staff` -> `supervisor`
- `admin` -> `technical admin`

This matches the current template with minimal auth refactoring.

### Engineer (`user`)

Allowed:

- login and view own profile
- view assets needed for maintenance work
- create maintenance request
- view own requests
- view requests assigned to self
- move assigned request to `in_progress`
- close assigned request with `completed`
- cancel own `open` request if not yet assigned

Not allowed:

- register assets
- export operational reports
- modify someone else's request
- change arbitrary statuses

### Supervisor (`staff`)

Allowed:

- view all assets
- register assets
- view all maintenance requests
- assign request to engineer
- move request through allowed internal transitions
- export restricted reports

Not allowed:

- bypass audit
- use admin-only technical operations outside business scope

### Technical admin (`admin`)

Allowed:

- all internal operational actions
- technical administration
- emergency or recovery access where explicitly supported

### Critical security rule for this variant

Status transitions must be checked:

- on the server
- against the current status
- against the acting user's role
- against assignment and ownership context
- against the specific request object

This is the most important business-security rule for variant 2.

## 6. Fixed business scenario for the report

### Main end-to-end scenario

1. Supervisor registers asset `A-1001`.
2. Engineer authenticates.
3. Engineer creates maintenance request for asset `A-1001`.
4. Supervisor reviews and assigns the request.
5. Engineer changes status to `in_progress`.
6. Engineer enters closure notes and sets status to `completed`.
7. System writes audit records for creation, assignment, status change, and closure.

### Why this is the correct main scenario

- it fully covers the task statement for variant 2
- it exercises all major security controls
- it gives a clean `source -> propagation -> sink -> sanitization` chain for the report
- it naturally produces audit events and role-based checks

## 7. Fixed API baseline

### Auth and user endpoints kept from the template

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`

### Final business endpoints

#### Assets

- `POST /api/v1/assets`
- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`

#### Maintenance requests

- `POST /api/v1/maintenance-requests`
- `GET /api/v1/maintenance-requests`
- `GET /api/v1/maintenance-requests/{request_id}`
- `PATCH /api/v1/maintenance-requests/{request_id}/status`
