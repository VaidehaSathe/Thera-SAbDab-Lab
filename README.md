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
python src/pdf2image.py inputfile.pdf outputfolder --first-page 1 --last-page 5 --dpi 300
```

### OCR Pipeline
- Takes in the image folder
- Uses pytesseract to extract layout-aware text from the images
- Example Useage:

```
python src/image2text.py inputfolder -o outputfile.txt
```

### Text Parser
- Takes in the textfile
- Uses unique markers in the text to split it into INN entries and subfields
- Cleans up redunant information (headers/footers, multi-language variations etc.)
- Filters out the antibody entries (with WHO-defined stems)
- Stores the  as a dataframe (INN, Description, Sequence, Modifications)
- Example Useage

```
python src/text2df.py data/inputfile.txt --out-tsv data/outputfile.tsv
```
