# Testing Guide for Protein Extraction Pipeline

## Quick Start Testing

### 1. Unit Tests (Recommended First)
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_pdf_converter.py -v

# Run with coverage report
python -m pytest tests/ --cov=src --cov-report=html
```

### 2. Manual Integration Testing

#### Step 1: PDF to Images
```bash
python src/pdf_to_image.py data/pdfs/pl134.pdf data/images/pl134_output -f 1 -l 5 --dpi 300
# Check: data/images/pl134_output/ should contain PNG files
ls data/images/pl134_output/
```

#### Step 2: Images to Text (OCR)
```bash
python src/image_to_text.py data/images/pl134_output data/ocr_text/pl134_raw.txt
# Check: data/ocr_text/pl134_raw.txt should contain extracted text
head -50 data/ocr_text/pl134_raw.txt
```

#### Step 3: Text Parsing
```bash
python src/text_parser.py data/ocr_text/pl134_raw.txt data/segmented_text/pl134_parsed.txt
# Check: data/segmented_text/pl134_parsed.txt should have structured entries
wc -l data/segmented_text/pl134_parsed.txt
```

#### Step 4: Text to DataFrame
```bash
python src/text_to_df.py data/segmented_text/pl134_parsed.txt data/dataframes/pl134_output.tsv
# Check: data/dataframes/pl134_output.tsv should be valid TSV
head data/dataframes/pl134_output.tsv
```

### 3. Validation Checks

**After each step, verify:**

1. **File exists and has content:**
   ```bash
   test -s output_file.txt && echo "✓ File exists and has content" || echo "✗ File empty or missing"
   ```

2. **Check data integrity:**
   ```bash
   python -c "
   import json
   with open('data/dataframes/pl134_output.tsv') as f:
       lines = f.readlines()
       print(f'Total entries: {len(lines)-1}')  # -1 for header
       print(f'Sample row: {lines[1][:100]}...')
   "
   ```

3. **Validate JSON output (if generated):**
   ```bash
   python -m json.tool data/output.json | head -50
   ```

### 4. End-to-End Test Script

Save this as `test_pipeline.sh`:
```bash
#!/bin/bash
set -e  # Exit on error

echo "🔄 Starting pipeline test..."

# Create directories
mkdir -p data/{pdfs,images,ocr_text,segmented_text,dataframes}

# Step 1
echo "1️⃣  PDF → Images"
python src/pdf_to_image.py data/pdfs/pl134.pdf data/images/pl134 -f 1 -l 3 --dpi 150
[ "$(ls -1 data/images/pl134 | wc -l)" -gt 0 ] && echo "✓ Images created" || exit 1

# Step 2
echo "2️⃣  Images → Text"
python src/image_to_text.py data/images/pl134 data/ocr_text/pl134_raw.txt
[ -s data/ocr_text/pl134_raw.txt ] && echo "✓ OCR complete" || exit 1

# Step 3
echo "3️⃣  Text → Parsed"
python src/text_parser.py data/ocr_text/pl134_raw.txt data/segmented_text/pl134_parsed.txt
[ -s data/segmented_text/pl134_parsed.txt ] && echo "✓ Parsing complete" || exit 1

# Step 4
echo "4️⃣  Parsed → DataFrame"
python src/text_to_df.py data/segmented_text/pl134_parsed.txt data/dataframes/pl134_output.tsv
[ -s data/dataframes/pl134_output.tsv ] && echo "✓ DataFrame created" || exit 1

echo "✅ Pipeline test passed!"
```

Run it with:
```bash
chmod +x test_pipeline.sh
./test_pipeline.sh
```

### 5. Common Issues & Debugging

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| `ModuleNotFoundError: pytesseract` | Missing dependency | `pip install pytesseract` + install Tesseract |
| Empty output files | Previous step failed silently | Check exit codes: `echo $?` |
| Encoding errors | Non-UTF8 text | Add `encoding='utf-8'` to file opens |
| Memory errors on large PDFs | Too many pages at once | Reduce page range with `-f` and `-l` flags |
| Poor OCR quality | Low image DPI | Increase `--dpi` to 300+ |

### 6. Success Criteria

✅ **Pipeline is working if:**
- [ ] All 4 steps complete without errors
- [ ] Each output file exists and has content
- [ ] No unhandled exceptions in logs
- [ ] Final DataFrame has >0 entries
- [ ] PTM and sequence fields are populated

❌ **Pipeline needs fixes if:**
- [ ] Any step produces 0-byte files
- [ ] OCR output is gibberish
- [ ] Parser can't find INN markers
- [ ] DataFrame rows are all empty
