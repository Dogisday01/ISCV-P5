## P3 Security Analysis

Student: `РќСѓСЂС‹Рј РђР±Р·Р°Р»`

Variant: `2`

Topic: `Oil and gas asset maintenance MVP with source code security analysis`

## Current status

- MVP implementation: complete
- security-oriented tests: complete
- `Bandit`: complete
- `pip-audit`: complete
- report artifacts: started

## Critical code areas

- authentication and token lifecycle
  - `app/services/auth.py`
  - `app/core/security.py`
- authorization and object access control
  - `app/core/authorization.py`
  - `app/api/routes/maintenance_requests.py`
- input validation and response shaping
  - `app/schemas/asset.py`
  - `app/schemas/maintenance_request.py`
- audit logging and data minimization
  - `app/services/audit.py`
  - `app/api/routes/assets.py`
  - `app/api/routes/reports.py`

## Protected business risks

- unauthorized status change
  - mitigated by server-side role and object checks in `app/core/authorization.py`
- IDOR on maintenance requests
  - mitigated by `ensure_can_view_request`
- leakage of internal operational notes
  - mitigated by conditional serialization in `app/schemas/maintenance_request.py`
- unrestricted export of operational data
  - mitigated by privileged-role-only access in `app/api/routes/reports.py`
- sensitive values in logs
  - mitigated by sanitization in `app/services/audit.py`

## Static analysis results

### Bandit

Command:

```powershell
.\.venv\Scripts\bandit.exe -c bandit.yaml -r app
```

Result:

- `No issues identified`
- total issues: `0`

### pip-audit

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pip-audit.exe
```

Result:

- `No known vulnerabilities found`
- local package `p3-universal-mvp` skipped because it is not published on PyPI

## Verification results

Commands:

```powershell
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe app tests
```

Results:

- `pytest`: `5 passed`
- `ruff`: passed
- `mypy`: passed

## Remaining report work

- add structural diagram excerpt
- add source -> propagation -> sink -> sanitization chain
- add findings table with actual result `no critical findings in current MVP`
- add protected-risk table with code references
- add final screenshots or code fragments for the report appendix
