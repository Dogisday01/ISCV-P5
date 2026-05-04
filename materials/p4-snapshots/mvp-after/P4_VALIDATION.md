# P4 Validation Snapshot: After Fixes

This snapshot preserves the MVP state after the P4 hardening fixes.

Run regression tests with the existing main virtual environment:

```powershell
cd "C:\Users\nurym\Documents\Assignment 3\materials\p4-snapshots\mvp-after"
& "C:\Users\nurym\Documents\Assignment 3\mvp\.venv\Scripts\python.exe" -m pytest
```

Expected result: 19 tests pass.

This version includes P4 fixes and regression tests for:

- streaming request body size enforcement;
- trusted proxy handling for client IP extraction;
- recursive audit metadata sanitization;
- refresh token replay/race protection;
- refresh token client-context mismatch detection;
- host and API documentation exposure controls;
- bounded asset list and maintenance report output;
- frontend static asset serving behavior.

Raw static analysis and test artifacts are stored in `p4-validation/raw-tool-results`.
