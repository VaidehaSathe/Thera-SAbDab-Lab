from pathlib import Path
from pdf2image import convert_from_path
import argparse


def pdf_to_png_folder(
    pdf_path: str,
    output_folder: str,
    first_page: int | None = None,
    last_page: int | None = None,
    dpi: int = 300,
):
    output_dir = Path(output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(
        pdf_path,
        dpi=dpi,
        first_page=first_page,
        last_page=last_page,
        fmt="png",
    )

    # If first_page is None, images start at page 1
    start_page = first_page or 1
    for i, img in enumerate(images, start=start_page):
        out_path = output_dir / f"page-{i}.png"
        img.save(out_path)
        print(f"Saved {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert selected PDF pages to PNG images in a folder."
    )
    parser.add_argument("pdf_path", help="Path to input PDF file")
    parser.add_argument("output_folder", help="Folder to save PNGs into")
    parser.add_argument(
        "--first-page", "-f", type=int, default=None, help="First page number (1-based)"
    )
    parser.add_argument(
        "--last-page", "-l", type=int, default=None, help="Last page number (1-based)"
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="Output DPI (default: 300)"
    )

    args = parser.parse_args()

    pdf_to_png_folder(
        pdf_path=args.pdf_path,
        output_folder=args.output_folder,
        first_page=args.first_page,
        last_page=args.last_page,
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()