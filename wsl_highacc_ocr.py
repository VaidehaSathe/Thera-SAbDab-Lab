#!/usr/bin/env python3
"""
wsl_highacc_ocr.py
High-resolution, high-accuracy OCR for PDF pages (WSL-friendly).

Defaults:
  INPUT_PDF = /mnt/data/INN.pdf
  PAGES = 85-86

Usage examples:
  python3 wsl_highacc_ocr.py
  python3 wsl_highacc_ocr.py --pdf /mnt/data/INN.pdf --first 85 --last 86
  python3 wsl_highacc_ocr.py --pdf /mnt/data/INN.pdf --first 1 --last 3 --dpi 600
"""

import argparse
import os
import sys
from pdf2image import convert_from_path
import pytesseract
import numpy as np
import cv2
from PIL import Image
from docx import Document
import re

# ---------- DEFAULTS ----------
DEFAULT_PDF = r"/mnt/data/INN.pdf"
DEFAULT_FIRST = 85
DEFAULT_LAST = 86
DEFAULT_DPI = 600

# ---------- UTILITIES ----------
def deskew_image(binary):
    coords = cv2.findNonZero(255 - binary)
    if coords is None:
        return binary
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.1:
        return binary
    (h, w) = binary.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def preprocess_pil_image(pil_img, debug_save=None):
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    th = cv2.adaptiveThreshold(gray, 255,
                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 31, 15)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
    cleaned = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)

    deskewed = deskew_image(cleaned)

    kernel2 = np.ones((1,1), np.uint8)
    final = cv2.dilate(deskewed, kernel2, iterations=1)

    if debug_save:
        cv2.imwrite(debug_save, final)

    return final

def find_column_bounds(binary, min_col_width=100, gap_thresh=0.02):
    h, w = binary.shape
    col_density = (255 - binary).sum(axis=0) / 255
    col_density_norm = col_density / (h + 1e-9)

    window = max(3, w // 200)
    kernel = np.ones(window) / window
    density_smooth = np.convolve(col_density_norm, kernel, mode='same')

    max_density = density_smooth.max() if density_smooth.max() > 0 else 1.0
    gap_mask = density_smooth < (max_density * gap_thresh)

    bounds = []
    in_col = False
    start = 0
    for x in range(w):
        if not gap_mask[x] and not in_col:
            in_col = True
            start = x
        elif gap_mask[x] and in_col:
            end = x - 1
            if (end - start) >= min_col_width:
                bounds.append((start, end))
            in_col = False

    if in_col:
        end = w - 1
        if (end - start) >= min_col_width:
            bounds.append((start, end))

    if not bounds:
        return [(0, w - 1)]

    merged = []
    cur_s, cur_e = bounds[0]
    for s, e in bounds[1:]:
        if s - cur_e < max(10, w // 200):
            cur_e = e
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged

def ocr_image_block(img_block, lang="eng", config=r"--oem 3 --psm 6"):
    if isinstance(img_block, np.ndarray):
        pil = Image.fromarray(img_block)
    else:
        pil = img_block
    return pytesseract.image_to_string(pil, lang=lang, config=config)

def clean_ocr_text(text):
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    lines = text.splitlines()
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if i + 1 < len(lines):
            nxt = lines[i+1].lstrip()
            if line and not line.endswith(('.', '?', '!', ':', ';', '-')) and nxt and nxt[0].islower():
                line = line + ' ' + nxt
                i += 1
                while i + 1 < len(lines) and lines[i+1].lstrip() and lines[i+1].lstrip()[0].islower():
                    i += 1
                    line = line + ' ' + lines[i].lstrip()
        out_lines.append(line)
        i += 1
    joined = "\n".join(out_lines)
    joined = re.sub(r'\n{3,}', '\n\n', joined)
    return joined.strip() + "\n"

# ---------- MAIN PROCESS ----------
def process_pdf_to_text(pdf_path, first_page, last_page, dpi, output_txt, output_docx,
                        debug_dir=None, lang="eng"):

    pages = convert_from_path(pdf_path, dpi=dpi, first_page=first_page, last_page=last_page)
    all_page_texts = []

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)

    for idx, pil_page in enumerate(pages, start=first_page):
        print(f"[+] Page {idx}: preprocess at {dpi} DPI")
        debug_img_path = os.path.join(debug_dir, f"page_{idx}_processed.png") if debug_dir else None
        binary = preprocess_pil_image(pil_page, debug_save=debug_img_path)

        cols = find_column_bounds(binary)
        print(f"    detected {len(cols)} column(s): {cols}")

        page_text_parts = []
        for cnum, (x0, x1) in enumerate(cols, start=1):
            h, w = binary.shape
            margin = max(6, int(0.005 * w))
            sx = max(0, x0 - margin)
            ex = min(w - 1, x1 + margin)
            crop = binary[:, sx:ex]

            ch, cw = crop.shape
            if cw < 800:
                scale = int(round(800 / max(1, cw)))
                crop = cv2.resize(crop, (cw * scale, ch * scale), interpolation=cv2.INTER_CUBIC)

            print(f"    OCR col {cnum}: x={sx}-{ex}")
            text = ocr_image_block(crop, lang=lang)
            page_text_parts.append(text)

            if debug_dir:
                cv2.imwrite(os.path.join(debug_dir, f"page_{idx}_col_{cnum}.png"), crop)

        page_joined = "\n\n".join(page_text_parts)
        page_clean = clean_ocr_text(page_joined)
        all_page_texts.append(f"--- PAGE {idx} ---\n{page_clean}")

    combined = "\n\n".join(all_page_texts)

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(combined)
    doc = Document()
    for line in combined.splitlines():
        doc.add_paragraph(line)
    doc.save(output_docx)

    print(f"[+] Wrote TXT → {output_txt}")
    print(f"[+] Wrote DOCX → {output_docx}")
    if debug_dir:
        print(f"[+] Debug images in → {debug_dir}")

# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="High-accuracy OCR for PDF pages (WSL).")
    p.add_argument("--pdf", default=DEFAULT_PDF)
    p.add_argument("--first", type=int, default=DEFAULT_FIRST)
    p.add_argument("--last", type=int, default=DEFAULT_LAST)
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    p.add_argument("--out-txt", default=os.path.expanduser("~/INN_pages_ocr.txt"))
    p.add_argument("--out-docx", default=os.path.expanduser("~/INN_pages_ocr.docx"))
    p.add_argument("--debug-dir", default=os.path.expanduser("~/ocr_debug_images"))
    p.add_argument("--lang", default="eng")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()

    if not os.path.isfile(args.pdf):
        print(f"ERROR: PDF not found → {args.pdf}")
        sys.exit(2)

    # locate tesseract if needed
    import shutil
    if not shutil.which("tesseract"):
        print("ERROR: tesseract not found. Install with: sudo apt install tesseract-ocr")
        sys.exit(3)

    process_pdf_to_text(
        pdf_path=args.pdf,
        first_page=args.first,
        last_page=args.last,
        dpi=args.dpi,
        output_txt=args.out_txt,
        output_docx=args.out_docx,
        debug_dir=args.debug_dir,
        lang=args.lang
    )
