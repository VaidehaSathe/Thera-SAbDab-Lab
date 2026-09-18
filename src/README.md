# Thera-SAbDab WHO INN Curator

Version: 1.0.4

This Windows package is the repaired system-Python launcher release. It intentionally **does not install another Python runtime**. Instead it finds the 64-bit Python already installed on the PC, creates an isolated short-path virtual environment under `%LOCALAPPDATA%\TSCurator\venv104`, installs the pinned application dependencies there, performs an off-screen application smoke test against the packaged 70-record PL135 seed database, and then launches the Qt desktop application.

## Windows quick start

1. Extract the complete ZIP.
2. Open the extracted `TSCurator_1.0.4` folder.
3. Double-click `START_APP.bat`.
4. The first launch needs internet access for the free Python wheels. Later launches reuse the private environment.
5. If a first run was interrupted, run `REPAIR_AND_RUN.bat`.
6. `DIAGNOSE_WINDOWS.bat` writes `%LOCALAPPDATA%\TSCurator\logs\diagnostic_report_v104.txt`.

The launcher prefers Python 3.11, then 3.12, 3.13, 3.10 and 3.14. A 64-bit installation is required. It uses a private venv, so it does not change packages in the user's normal Python installation.

## Standalone executable

`BUILD_STANDALONE_EXE.bat` is optional. It uses the same private environment, stages the source under a short LocalAppData path, runs the automated tests, then runs PyInstaller. The resulting executable is copied back to `dist\Thera-SAbDab_WHO_INN_Curator\`.

## Application/data

The application includes the 70-record PL135 seed database and the PL135/PL129 regression resources. It provides database search/browse, record details, sequences and evidence views, favourites/recent records, comparison, persistent import review, audited corrections, database backup/merge, workbook merge/export and WHO PDF import infrastructure.

OCR recovery requires Tesseract and Poppler if those tools are not bundled. Their absence does not prevent the core database/search/review application from opening.

## Validation in the generation environment

The Python application test suite passes 13/13 tests, including the Qt off-screen UI smoke test and database/import-review tests. The Windows batch/PowerShell launcher itself cannot be executed in the Linux generation environment, so Windows-specific launcher behavior is code-inspected and targeted to the concrete Windows failures reported by the user.
