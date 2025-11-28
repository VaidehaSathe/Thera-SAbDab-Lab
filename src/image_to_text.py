import argparse
import statistics
from pathlib import Path
import re


def ocr_image_left_to_right(img_path, lang="eng"):
    """Perform left→right, top→bottom OCR by reconstructing text from bounding boxes."""
    from PIL import Image
    import pytesseract
    from pytesseract import Output

    img = Image.open(img_path)
    data = pytesseract.image_to_data(
        img, lang=lang, config="--oem 1", output_type=Output.DICT
    )

    words = []
    heights = []
    n = len(data["level"])
    for i in range(n):
        txt = data["text"][i].strip()
        if not txt:
            continue
        try:
            left = int(data["left"][i])
            top = int(data["top"][i])
            h = int(data["height"][i])
            center_y = top + h / 2
        except Exception:
            continue
        words.append(
            {
                "text": txt,
                "left": left,
                "top": top,
                "h": h,
                "center_y": center_y,
            }
        )
        heights.append(h)

    if not words:
        return ""

    median_h = statistics.median(heights)
    line_thresh = max(8, median_h * 0.6)

    words_sorted = sorted(words, key=lambda w: (w["center_y"], w["left"]))

    lines = []
    current = [words_sorted[0]]
    last_y = words_sorted[0]["center_y"]

    for w in words_sorted[1:]:
        if abs(w["center_y"] - last_y) <= line_thresh:
            current.append(w)
            last_y = (last_y * (len(current) - 1) + w["center_y"]) / len(current)
        else:
            lines.append(sorted(current, key=lambda x: x["left"]))
            current = [w]
            last_y = w["center_y"]
    if current:
        lines.append(sorted(current, key=lambda x: x["left"]))

    lines_sorted = sorted(lines, key=lambda ln: min(word["top"] for word in ln))

    final_lines = []
    for ln in lines_sorted:
        tokens = []
        for w in ln:
            t = w["text"]
            if tokens and t[0] in ".,:;?!%)":
                tokens[-1] += t
            else:
                tokens.append(t)
        final_lines.append(" ".join(tokens))

    return "\n".join(final_lines)


def page_sort_key(path: Path):
    """
    Sort key that extracts the first integer from the filename stem.
    For example:
      'page-1.png'  -> 1
      'page-02.png' -> 2
      'page-10.png' -> 10
    Files without a number are placed at the end, ordered by name.
    """
    m = re.search(r"(\d+)", path.stem)
    if m:
        return (0, int(m.group(1)))  # 0 = "has number"
    else:
        return (1, path.stem.lower())  # 1 = "no number", sort by name


def main():
    parser = argparse.ArgumentParser(
        description="Run left→right OCR over all images in a folder and combine to one text output."
    )
    parser.add_argument(
        "input_folder",
        help="Path to folder containing images (e.g. .png, .jpg, .jpeg, .tif, .tiff)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output .txt file path (if omitted, prints to stdout)",
    )
    parser.add_argument(
        "--lang",
        default="eng",
        help="Tesseract language code(s), e.g. 'eng', 'eng+fra' (default: eng)",
    )

    args = parser.parse_args()

    folder = Path(args.input_folder)
    if not folder.is_dir():
        raise SystemExit(f"Input path is not a directory: {folder}")

    # Collect image files
    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    image_paths = [
        p for p in folder.iterdir() if p.suffix.lower() in exts and p.is_file()
    ]

    if not image_paths:
        raise SystemExit(f"No image files found in folder: {folder}")

    # Sort by page number extracted from filename
    image_paths = sorted(image_paths, key=page_sort_key)

    chunks = []
    for img_path in image_paths:
        print(f"OCR: {img_path.name}...", flush=True)
        text = ocr_image_left_to_right(str(img_path), lang=args.lang)
        chunks.append(f"===== {img_path.name} =====")
        chunks.append(text)
        chunks.append("")  # blank line between images

    full_text = "\n".join(chunks)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(full_text, encoding="utf-8")
        print(f"\nWrote OCR text to: {out_path}")
    else:
        print()
        print(full_text)


if __name__ == "__main__":
    main()