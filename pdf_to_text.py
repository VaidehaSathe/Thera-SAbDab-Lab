#!/usr/bin/env python3
"""
pdf_to_text.py
Renders pages 138-144 from the given PDF to high-res PNGs and OCRs them with Tesseract,
writing a single merged text file.

Edit PDF_WSL_PATH below if needed (currently set to your path).
"""

from pathlib import Path
import sys, traceback

PDF_WSL_PATH = Path("/mnt/c/Users/skinare/Downloads/INN.pdf")
OUT_DIR = Path("/home/skinare/INN_pages_138_144")
START_PAGE = 138
END_PAGE = 144
OCR_LANG = "eng"

def main():
    print("Starting pdf_to_text.py")
    print("PDF:", PDF_WSL_PATH)
    print("Output dir:", OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # imports with friendly messages
    try:
        import fitz
        from PIL import Image
        import pytesseract
    except Exception as e:
        print("IMPORT ERROR:", type(e).__name__, e)
        traceback.print_exc()
        sys.exit(1)

    # Check tesseract binary
    import shutil
    tpath = shutil.which("tesseract")
    if not tpath:
        print("WARNING: 'tesseract' not found in PATH. Install with: sudo apt install tesseract-ocr")
    else:
        print("tesseract binary found at:", tpath)

    # Check PDF exists
    if not PDF_WSL_PATH.exists():
        print("ERROR: PDF not found at:", PDF_WSL_PATH)
        sys.exit(2)

    # Open PDF
    try:
        doc = fitz.open(str(PDF_WSL_PATH))
        print("Opened PDF. page_count =", doc.page_count)
    except Exception as e:
        print("ERROR opening PDF:", e)
        traceback.print_exc()
        sys.exit(3)

    image_paths = []
    try:
        for p in range(START_PAGE - 1, END_PAGE):
            if p < 0 or p >= doc.page_count:
                print(f"Skipping page {p+1} (out of range)")
                continue
            print(f"Rendering page {p+1} ...", end=" ", flush=True)
            try:
                page = doc[p]
                mat = fitz.Matrix(3.0, 3.0)   # high-res
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_path = OUT_DIR / f"page_{p+1:03d}.png"
                pix.save(str(img_path))
                image_paths.append(img_path)
                print("OK ->", img_path.name)
            except Exception as re:
                print("RENDER ERROR on page", p+1, ":", type(re).__name__, re)
    finally:
        try:
            doc.close()
        except:
            pass

    if not image_paths:
        print("No images created. Exiting.")
        sys.exit(4)

    # OCR and merge
    merged_parts = []
    for img in image_paths:
        print("OCR on", img.name, "...")
        try:
            txt = pytesseract.image_to_string(Image.open(img), lang=OCR_LANG)
            merged_parts.append(f"\n\n=== {img.name} ===\n\n")
            merged_parts.append(txt)
            print("OCR length:", len(txt))
        except Exception as oe:
            print("OCR ERROR on", img, ":", type(oe).__name__, oe)
            traceback.print_exc()

    merged_txt = OUT_DIR / "merged_pages_138_144.txt"
    try:
        merged_txt.write_text("".join(merged_parts), encoding="utf-8")
        print("Saved merged text to:", merged_txt)
    except Exception as se:
        print("ERROR writing merged text:", se)
        traceback.print_exc()

    print("Done.")

if __name__ == '__main__':
    main()
