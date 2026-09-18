# Release notes - v1.0.4

This release replaces the failed embedded-Python bootstrap used by v1.0.3.

The user's diagnostic showed that the embedded `python.exe` existed, but PyQt5 had not been installed and the diagnostic process could not import the application package. v1.0.4 therefore uses the user's already-installed 64-bit Windows Python only as a base to create a clean, isolated short-path virtual environment under LocalAppData.

Changes:

- Removed the embedded-Python dependency from the normal launch path.
- Finds installed Python through the Python launcher (`py.exe`) or `python.exe`.
- Creates `%LOCALAPPDATA%\TSCurator\venv104` with `venv`.
- Keeps all dependency installation under the short LocalAppData path.
- Explicitly sets `PYTHONPATH` for smoke testing and launch.
- Runs a real Qt off-screen main-window smoke test before launch.
- Reworked Windows diagnostics to report system Python and the private venv separately.
- Reworked standalone PyInstaller build to use the same known-good venv and short staging path.
- Keeps the 70-record PL135 seed and existing regression/test suite unchanged.
