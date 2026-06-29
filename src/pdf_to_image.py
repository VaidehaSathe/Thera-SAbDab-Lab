#!/usr/bin/env python3
"""
PDF to Image Converter
Converts PDF pages to images at specified DPI and page range.

Usage:
    python src/pdf_to_image.py data/pdfs/input.pdf data/images/output -f 1 -l 10 --dpi 300
"""

import fitz  # PyMuPDF
import argparse
import os
from pathlib import Path
from PIL import Image
import io

def convert_pdf_to_images(pdf_path: str, output_dir: str, first_page: int = 1, 
                         last_page: int = None, dpi: int = 300) -> int:
    """
    Convert PDF pages to images.
    
    Args:
        pdf_path: Path to input PDF
        output_dir: Directory to save images
        first_page: First page to convert (1-indexed)
        last_page: Last page to convert (inclusive)
        dpi: Resolution in DPI
    
    Returns:
        Number of images created
    """
    # Open PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    # Validate page range
    first_page = max(1, first_page)
    if last_page is None:
        last_page = total_pages
    else:
        last_page = min(last_page, total_pages)
    
    if first_page > last_page:
        raise ValueError(f"Invalid page range: {first_page} to {last_page}")
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert DPI to zoom factor (72 DPI is default)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    
    images_created = 0
    for page_num in range(first_page - 1, last_page):  # Convert to 0-indexed
        page = doc[page_num]
        
        # Render page to image
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Save as PNG
        output_path = os.path.join(output_dir, f"page_{page_num + 1:04d}.png")
        pix.save(output_path)
        images_created += 1
        
        print(f"✓ Saved page {page_num + 1} to {output_path}")
    
    doc.close()
    return images_created

def main():
    parser = argparse.ArgumentParser(description="Convert PDF pages to images")
    parser.add_argument("pdf_path", help="Path to input PDF file")
    parser.add_argument("output_dir", help="Directory to save output images")
    parser.add_argument("-f", "--first", type=int, default=1, help="First page to convert (default: 1)")
    parser.add_argument("-l", "--last", type=int, default=None, help="Last page to convert (default: last page)")
    parser.add_argument("--dpi", type=int, default=300, help="DPI resolution (default: 300)")
    
    args = parser.parse_args()
    
    print(f"Converting {args.pdf_path} to images...")
    print(f"Page range: {args.first} to {args.last if args.last else 'end'}")
    print(f"DPI: {args.dpi}")
    print()
    
    images_created = convert_pdf_to_images(
        args.pdf_path,
        args.output_dir,
        first_page=args.first,
        last_page=args.last,
        dpi=args.dpi
    )
    
    print(f"\n✅ Created {images_created} images in {args.output_dir}")

if __name__ == "__main__":
    main()
