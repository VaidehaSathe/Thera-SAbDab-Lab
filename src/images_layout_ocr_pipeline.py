import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from PIL import Image
import pytesseract
from pytesseract import Output
import layoutparser as lp

# On Ubuntu/WSL, Tesseract is usually at /usr/bin/tesseract
# If you installed via apt, you generally DO NOT need this line.
# Uncomment only if tesseract is in a non-standard location:
# pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"


def ocr_image_to_layout(image: Image.Image, page_id: str) -> lp.Layout:
    """
    Run Tesseract on an image and group words into line-level blocks.
    Convert the result into a layoutparser Layout of TextBlocks.
    """
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    n = len(data["text"])

    # Group words by (block_num, line_num)
    lines: Dict[Tuple[int, int], Dict[str, Any]] = {}

    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue

        block_num = data["block_num"][i]
        line_num = data["line_num"][i]
        key = (block_num, line_num)

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]
        x1, y1, x2, y2 = x, y, x + w, y + h

        if key not in lines:
            lines[key] = {
                "text": text,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "block_num": block_num,
                "line_num": line_num,
            }
        else:
            # Append text and expand the bounding box
            lines[key]["text"] += " " + text
            lines[key]["x1"] = min(lines[key]["x1"], x1)
            lines[key]["y1"] = min(lines[key]["y1"], y1)
            lines[key]["x2"] = max(lines[key]["x2"], x2)
            lines[key]["y2"] = max(lines[key]["y2"], y2)

    # Convert to layoutparser TextBlocks
    text_blocks: List[lp.TextBlock] = []
    for (block_num, line_num), info in lines.items():
        rect = lp.Rectangle(info["x1"], info["y1"], info["x2"], info["y2"])
        tb = lp.TextBlock(
            rect,
            text=info["text"],
            id=f"{page_id}_b{block_num}_l{line_num}",
        )
        text_blocks.append(tb)

    # Sort blocks roughly by reading order: top-to-bottom, then left-to-right
    text_blocks.sort(key=lambda b: (b.block.y_1, b.block.x_1))

    layout = lp.Layout(text_blocks)
    return layout


def folder_to_layout_json(folder_path: str) -> Dict[str, Any]:
    """
    Process a folder of images into a JSON-serializable structure:

    {
      "source_folder": "...",
      "pages": [
        {
          "page_id": "0001.png",
          "width": ...,
          "height": ...,
          "blocks": [
            {"id": "...", "bbox": [x1,y1,x2,y2], "text": "..."},
            ...
          ]
        },
        ...
      ]
    }
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"{folder} is not a directory")

    # Adjust extensions if needed
    image_paths = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    )

    if not image_paths:
        raise ValueError(f"No .png/.jpg images found in {folder}")

    result: Dict[str, Any] = {
        "source_folder": str(folder.resolve()),
        "pages": [],
    }

    for img_path in image_paths:
        image = Image.open(img_path).convert("RGB")
        width, height = image.size

        page_id = img_path.name  # or use stem, or an index
        layout = ocr_image_to_layout(image, page_id=page_id)

        page_dict = {
            "page_id": page_id,
            "width": width,
            "height": height,
            "blocks": [],
        }

        for block in layout:
            bbox = block.block  # lp.Rectangle
            page_dict["blocks"].append(
                {
                    "id": block.id,
                    "bbox": [bbox.x_1, bbox.y_1, bbox.x_2, bbox.y_2],
                    "text": block.text,
                }
            )

        result["pages"].append(page_dict)

    return result


def layout_json_to_text(layout_data: Dict[str, Any]) -> str:
    """
    Convert the layout JSON structure into a plain-text representation
    that roughly preserves page order and block grouping.
    """
    lines: List[str] = []

    for page in layout_data["pages"]:
        page_id = page["page_id"]
        lines.append(f"===== IMAGE {page_id} =====")

        # Sort blocks by (top, left) to approximate visual order
        blocks = sorted(page["blocks"], key=lambda b: (b["bbox"][1], b["bbox"][0]))

        for blk in blocks:
            text = (blk["text"] or "").strip()
            if not text:
                continue
            lines.append(text)
            lines.append("")  # blank line between blocks

        lines.append("")  # extra blank line between images

    return "\n".join(lines)


def save_json(data: Dict[str, Any], path: str) -> None:
    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_text(text: str, path: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Folder of images → layout-aware JSON → TXT using layoutparser + pytesseract"
    )
    parser.add_argument("folder_path", help="Path to folder containing .png/.jpg images")
    parser.add_argument(
        "--json-out",
        default="images_layout.json",
        help="Path to JSON output file (default: images_layout.json)",
    )
    parser.add_argument(
        "--txt-out",
        default="images_text.txt",
        help="Path to TXT output file (default: images_text.txt)",
    )

    args = parser.parse_args()

    layout_data = folder_to_layout_json(args.folder_path)
    save_json(layout_data, args.json_out)

    text_output = layout_json_to_text(layout_data)
    save_text(text_output, args.txt_out)

    print(f"JSON written to: {args.json_out}")
    print(f"TXT written to:  {args.txt_out}")


if __name__ == "__main__":
    main()
