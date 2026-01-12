# Thera-SAbDab-Lab
ILESLA Team Project Sandpit 2025-2026

## PDF Parsing Pipeline
PDF --(pdf2image)--> Image Folder --(pytesseract)--> Textfile --(string comprehension)--> Segmented Textfile --(string comprehension and SQLite)--> Database

## Modules
### PDF Converter
- Takes in a PDF file
- Converts a specified page range into a folder of images at a specific DPI
- Example Useage:

```
python src/pdf_to_image.py data/pdfs/inputfile.pdf data/images/outputfolder -f 1 -l 5 --dpi 300
```

### OCR Pipeline
- Takes in an image folder
- Uses pytesseract to extract layout-aware text from the images
- Example Useage:

```
python src/image_to_text.py data/images/inputfolder data/ocr_text/outputfile.txt
```

### Text Parser
- Takes in a textfile
- Uses unique markers in the text to split it into INN entries and subfields:
  - INN
  - Chemical description
  - Amino acid sequence
  - Post-translational modifications
- Cleans up redunant information (headers/footers, multi-language variations etc.)
- Filters out the antibody entries (with WHO-defined stems)
- Example Useage:

```
python src/text_parser.py data/ocr_text/inputfile.txt data/segmented_text/outputfile.txt
```

### Text Cleaner (TO BE MADE)
- Takes in a textfile
- Cleans INN entries and subfields:
  - Parses chemical description (TBD)
  - Extracts whole AA sequence and splits it into heavy and light chains
  -  Sorts PTM into various types (TBD; disulfite-bridges, N-glycosylations etc.)
-  Stores the cleaned data into a dataframe (multiple entries per column converted to dict objects)
-  Example Useage:

```
python src/text_to_df.py data/segmented_text/inputfile.txt data/dataframes/outputfile.tsv
```

### Converion to Database
- Uses SQLite and string comprehension to transform the segmented text into a usable relational database.
- Needs Development

## Scraping additional information (NEEDS TO BE BUILT)`
Database --(LLM API + Query)--> Find alternate names --(LLM API + Query)--> Extract ADA/Immunogenicity data from preclinical studies/databases --(SQLite + String Comprehension)--> Updated Database
