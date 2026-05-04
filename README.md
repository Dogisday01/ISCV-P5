# ISCV P5

Assignment 3 / Practical work 5 for the MVP security analysis course.

Contents:

- `mvp/` - FastAPI MVP source code and tests.
- `materials/p4-snapshots/mvp-after/` - baseline snapshot used before P5 changes.
- `materials/p5-output/P5 Comprehensive MVP security analysis.docx` - final P5 report.
- `materials/p5-output/build_p5_report.py` - reproducible report generator.

Local verification commands:

```powershell
cd mvp
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app tests
.\.venv\Scripts\python.exe -m bandit -c bandit.yaml -r app
$env:PYTHONUTF8='1'; semgrep scan --config auto --exclude __pycache__ app
.\.venv\Scripts\python.exe -m pip_audit
```
