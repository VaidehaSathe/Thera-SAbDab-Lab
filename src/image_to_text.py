#!/usr/bin/env python3
"""
Image to Text (OCR) Converter
Extracts text from images using pytesseract with layout awareness.

Usage:
    python src/image_to_text.py data/images/input_folder data/ocr_text/output.txt
"""

import pytesseract
from PIL import Image
import argparse
import os
from pathlib import Path

def extract_text_from_images(image_dir: str, output_file: str) -> int:
    """
    Extract text from all images in a directory using OCR.
    
    Args:
        image_dir: Directory containing images
        output_file: Path to save extracted text
    
    Returns:
        Number of images processed
    """
    # Get all image files
    image_files = sorted([f for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    if not image_files:
        raise FileNotFoundError(f"No images found in {image_dir}")
    
    # Create output directory
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    all_text = []
    images_processed = 0
    
    for img_file in image_files:
        img_path = os.path.join(image_dir, img_file)
        
        try:
            # Open image
            img = Image.open(img_path)
            
            # Extract text with layout preservation
            text = pytesseract.image_to_string(img, config='--psm 1')  # PSM 1 = auto page segmentation with OSD
            
            # Add page marker
            all_text.append(f"\n\n[PAGE: {img_file}]\n{text}")
            images_processed += 1
            
            print(f"✓ Processed {img_file}")
        
        except Exception as e:
            print(f"⚠ Error processing {img_file}: {e}")
    
    # Write all text to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_text))
    
    return images_processed

def main():
    parser = argparse.ArgumentParser(description="Extract text from images using OCR")
    parser.add_argument("image_dir", help="Directory containing input images")
    parser.add_argument("output_file", help="Output text file")
    
    args = parser.parse_args()
    
    print(f"Extracting text from images in {args.image_dir}...\n")
    
    images_processed = extract_text_from_images(args.image_dir, args.output_file)
    
    print(f"\n✅ Processed {images_processed} images")
    print(f"✅ Text saved to {args.output_file}")

if __name__ == "__main__":
    main()
