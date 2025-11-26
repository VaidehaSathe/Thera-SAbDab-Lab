# Thera-SAbDab-Lab
ILESLA Team Project Sandpit 2025-2026

## Pipeline
PDF --(pdf2image)--> Image Folder --(pytesseract, layoutparser)--> Textfile --(string comprehension)--> Dataframe 

## Modules
### PDF Converter
- Takes in the PDF file
- Converts a specified page range into a folder of images at as specific DPI
- Example Useage:

```
python src/pdf_converter.py input.pdf output_folder --first-page 1 --last-page 5 --dpi 300
```

### OCR Pipeline
- Takes in the image folder
- Uses pytesseract and layoutparser to extract text information from the images
- Extracts layout information (stored as a .json) to infrom text layout
- Example Useage:

```
python src/images_layout_ocr_pipeline.py data/inputfolder --json-out data/outputs/outputfile.json --txt-out data/outputs/outputfile.txt
```

### Text Parser
- Takes in the textfile
- Uses unique markers in the text to split it into INN entries and subfields
- Cleans up redunant information (headers/footers, multi-language variations etc.)
- Filters out the antibody entries (with WHO-defined stems)
- Stores the  as a dataframe (INN, Description, Sequence, Modifications)
- Example Useage

```
python src/parse_antibody_inn_v3.py data/outputs/inputfile.txt --out-tsv data/outputs/outputfile.tsv
```
