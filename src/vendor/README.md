# Optional bundled Windows OCR runtimes

The application works without OCR for clean native PDF text. For the fully offline Windows OCR build, place redistributable Windows runtimes here before running `build_windows.ps1`:

* `vendor/tesseract/tesseract.exe` plus its DLLs, `tessdata/eng.traineddata`, and upstream license files.
* `vendor/poppler/Library/bin/pdftoppm.exe` (or `vendor/poppler/bin/pdftoppm.exe`) plus required DLLs and upstream license files.

The build script refuses to call the result a bundled-OCR build if those executables are absent. Use `-AllowExternalOCR` only when intentionally producing a build where OCR can use separately installed Tesseract/Poppler.

Do not redistribute third-party binaries without retaining their required license notices.
