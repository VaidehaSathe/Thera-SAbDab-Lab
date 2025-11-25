#!/usr/bin/env python3
"""
pdf_to_text_l2r.py — FULL PDF VERSION

Render *every page* in the PDF to PNG, OCR each page using bounding-box 
reconstruction (true left->right, top->bottom reading order), and generate a 
single merged TXT output.

Requirements:
    pip install pymupdf pillow pytesseract
System:
    sudo apt install -y tesseract-ocr
"""

from pathlib import Path
import traceback
import statistics

# --------- Configuration ----------
PDF_PATH = Path("/mnt/c/Users/skinare/Downloads/INN.pdf")   # UPDATE FOR YOUR SYSTEM
OUT_DIR = Path("/home/skinare/INN_full_OCR")                 # output directory
DPI = 300                                                    # or 600 if needed
OCR_LANG = "eng"
# ---------------------------------

def render_all_pages(pdf_path, out_dir, dpi=300):
    """Render ALL pages of a PDF to PNG. Returns list of image paths."""
    import fitz
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    out_dir.mkdir(parents=True, exist_ok=True)
    images = []

    doc = fitz.open(str(pdf_path))
    page_count = doc.page_count
    print(f"PDF has {page_count} pages.")

    try:
        for p in range(page_count):  # 🔥 process ALL pages
            page = doc[p]
            print(f"Rendering page {p+1}/{page_count} ...", end=" ", flush=True)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_path = out_dir / f"page_{p+1:03d}.png"
            pix.save(str(img_path))
            images.append(img_path)
            print("saved.")
    finally:
        doc.close()

    return images


def ocr_image_left_to_right(img_path, lang="eng"):
    """Perform left→right, top→bottom OCR by reconstructing text from bounding boxes."""
    from PIL import Image
    import pytesseract
    from pytesseract import Output

    img = Image.open(img_path)
    data = pytesseract.image_to_data(img, lang=lang, config="--oem 1", output_type=Output.DICT)

    words = []
    heights = []
    n = len(data['level'])
    for i in range(n):
        txt = data['text'][i].strip()
        if not txt:
            continue
        try:
            left = int(data['left'][i])
            top = int(data['top'][i])
            h = int(data['height'][i])
            center_y = top + h / 2
        except:
            continue
        words.append({'text': txt, 'left': left, 'top': top, 'h': h, 'center_y': center_y})
        heights.append(h)

    if not words:
        return ""

    median_h = statistics.median(heights)
    line_thresh = max(8, median_h * 0.6)

    words_sorted = sorted(words, key=lambda w: (w['center_y'], w['left']))

    lines = []
    current = [words_sorted[0]]
    last_y = words_sorted[0]['center_y']

    for w in words_sorted[1:]:
        if abs(w['center_y'] - last_y) <= line_thresh:
            current.append(w)
            last_y = (last_y * (len(current)-1) + w['center_y']) / len(current)
        else:
            lines.append(sorted(current, key=lambda x: x['left']))
            current = [w]
            last_y = w['center_y']
    if current:
        lines.append(sorted(current, key=lambda x: x['left']))

    lines_sorted = sorted(lines, key=lambda ln: min(word['top'] for word in ln))

    final_lines = []
    for ln in lines_sorted:
        tokens = []
        for w in ln:
            t = w['text']
            if tokens and t[0] in ".,:;?!%)":
                tokens[-1] += t
            else:
                tokens.append(t)
        final_lines.append(" ".join(tokens))

    return "\n".join(final_lines)


def main():
    print("Starting FULL-PDF left->right OCR pipeline")
    print("PDF:", PDF_PATH)
    print("Output directory:", OUT_DIR)

    if not PDF_PATH.exists():
        print("\nERROR: PDF not found at:", PDF_PATH)
        return

    try:
        image_paths = render_all_pages(PDF_PATH, OUT_DIR, dpi=DPI)
    except Exception as e:
        print("Render error:", e)
        traceback.print_exc()
        return

    merged_parts = []

    for img in image_paths:
        print(f"OCR (left->right) on {img.name} ...")
        try:
            page_text = ocr_image_left_to_right(img, lang=OCR_LANG)
            merged_parts.append(f"\n\n===== {img.name} =====\n\n")
            merged_parts.append(page_text)
        except Exception as e:
            print("OCR error:", e)
            traceback.print_exc()

    out_file = OUT_DIR / "merged_full_pdf.txt"
    out_file.write_text("".join(merged_parts), encoding="utf-8")
    print("\nSaved full-PDF OCR to:", out_file)


if __name__ == "__main__":
    main()
