# Known limitations

- The Windows launcher scripts are generated and code-inspected in a Linux environment and therefore cannot be physically executed under Windows here.
- v1.0.4 requires a usable 64-bit Python installation on the Windows PC. It is designed for Python 3.11-3.13 and also attempts 3.10/3.14 as fallbacks.
- First launch requires internet access to download pinned free Python wheels into the private virtual environment.
- Tesseract and Poppler are not bundled in this source ZIP. Core database/search/review features work without them; OCR recovery requires those external tools or a separately bundled runtime.
- The generic WHO importer intentionally sends unresolved image/layout-dependent sequence extraction to review rather than inventing residues.
