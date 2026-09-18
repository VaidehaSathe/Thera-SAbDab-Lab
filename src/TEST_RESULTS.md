# Test results - 1.0.4

## Automated application tests

Generation environment: Linux, Python 3.12, PyQt5, Qt off-screen mode.

The full application suite was rerun after the v1.0.4 Windows-launcher changes.

```text
13 passed
```

The suite covers seed/schema integrity, database persistence, pending review, PASS/REVIEW approval rules, audited manual corrections, backup-before-merge, non-destructive workbook merge, PL135 candidate-set regression, PL129 generalisation controls, avrukibart native sequence/residue-count QC, CAR/cell-therapy exclusion, OCR-path coverage where local OCR executables are available, golden-fixture reconciliation, exports, and Qt UI smoke tests.

## Windows failure addressed in v1.0.4

The v1.0.3 Windows diagnostic proved that the downloaded embedded `python.exe` existed, but `PyQt5` was not installed into that runtime and the diagnostic process could not import the application package. The user also confirmed that the Windows laptop already has Python installed.

v1.0.4 therefore removes embedded-Python bootstrapping from the normal path. It:

- discovers the existing 64-bit system Python, preferring 3.11, 3.12 and 3.13;
- creates a clean venv at `%LOCALAPPDATA%\\TSCurator\\venv104`;
- installs all pinned runtime dependencies only inside that venv;
- uses PyQt5, avoiding the deep PySide6 QML path that failed in v1.0.1;
- explicitly sets `PYTHONPATH` to the extracted package root for smoke tests and launch;
- verifies PyQt5 and all required application dependencies;
- runs an off-screen `MainWindow` smoke test against the packaged 70-record seed database before opening the visible application;
- uses the same private environment for the optional PyInstaller build;
- stages the PyInstaller source under a short LocalAppData path.

## Static checks

- Full Python test suite: passed.
- `python -m compileall` over application, scripts and tests: passed.
- Critical launcher/resource file presence: checked.
- ZIP CRC/integrity check: performed before delivery.

## Windows execution status

The generation environment does not contain Windows `cmd.exe` or Windows PowerShell, so the v1.0.4 batch/PowerShell launcher cannot be natively executed here. The launcher is targeted to the concrete diagnostic supplied from the user's Windows machine and now uses the user's already-installed Python rather than another downloaded runtime.
