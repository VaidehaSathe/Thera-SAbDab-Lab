# Thera-SAbDab-Lab
ILESLA Team Project Sandpit 2025-2026

## Pipeline
PDF --(pdf2image)--> Image Folder --(pytesseract)--> Textfile --(string comprehension)--> Dataframe 

## Modules
### PDF Converter
- Takes in the PDF file
- Converts a specified page range into a folder of images at as specific DPI
- Example Useage:

```
python src/pdf_to_image.py inputfile.pdf outputfolder -f 1 -l 5 --dpi 300
```

### OCR Pipeline
- Takes in the image folder
- Uses pytesseract to extract layout-aware text from the images
- Example Useage:

```
python src/image_to_text.py inputfolder -o outputfile.txt
```

### Text Parser
- Takes in the textfile
- Uses unique markers in the text to split it into INN entries and subfields
- Cleans up redunant information (headers/footers, multi-language variations etc.)
- Filters out the antibody entries (with WHO-defined stems)
- Stores the  as a dataframe (INN, Description, Sequence, Modifications)
- Example Useage

```
python src/text_to_df.py data/inputfile.txt -o data/outputfile.tsv
```
