**PubMedCrawl**

A small Python toolkit for searching Europe PMC with therapeutic antibody names and synonyms, scoring relevant literature, and exporting clean CSV results.

**Overview**

This script:

- reads a 2-column CSV of therapeutic names and aliases (can use antibodies.csv as a test),
- query Europe PMC for matching literature,
- score each candidate article with a simple relevance heuristic (probably requires more refining but fine for now),
- deduplicate results by PMID/DOI, and
- write normalized CSV outputs for further analysis.

**Requirements**

- Python 3.8+
- Install dependencies:

```bash
pip install pandas requests certifi
```

**Input Format**

The scraper expects a CSV with two columns and no header row:

1. Therapeutic name
2. Synonyms / aliases separated by commas, semicolons, or pipes

Example:

```csv
trastuzumab,Herceptin;rhuMAb-HER2
adalimumab,Humira|D2E7
```

This needs to be updates when merged with the main script.

**Usage**

Run the main script like this:

```bash
python crawlpubmed_europepmc_v2.py --input-csv antibodies.csv
```

Optional authentication arguments:

```bash
python crawlpubmed_europepmc.py \
  --input-csv antibodies.csv \
  --output-csv literature_results.csv \
  --ncbi-email you@domain.com \
  --ncbi-key YOUR_API_KEY
```

**Available CLI options**

- `--input-csv` — path to the input CSV (default `antibodies.csv`)
- `--output-csv` — path to the detailed output CSV
- `--page-size` — Europe PMC page size
- `--max-pages` — maximum pages per alias search
- `--sleep` — seconds between requests
- `--min-year` / `--max-year` — publication year filter
- `--min-score` — minimum score to keep a result
- `--ncbi-email` — optional email for request metadata
- `--ncbi-key` — optional API key/token for request metadata
- `--top-n` — keep top N scored results per therapeutic
- `--wide-output-csv` — path for the one-row-per-therapeutic summary CSV
- `--debug-top-n` — print the top N raw scored candidates before filtering

**Output files**

`crawlpubmed_europepmc.py` writes a detailed CSV with columns such as:

- `therapeutic`
- `search_term`
- `score`
- `match_reason`
- `source`
- `id`
- `pmid`
- `doi`
- `title`
- `abstract`
- `journal`
- `year`
- `month`
- `first_publication_date`
- `citedByCount`
- `pub_types`
- `is_open_access`
- `pubmed_url`
- `europe_pmc_url`

`crawlpubmed_europepmc_v2.py` also writes a wide summary CSV where each therapeutic has a single `top5_papers` string, which is the one to be merged with the main dataframe.

**Scoring System**

The script uses a simple heuristic to rate article relevance, including:

- whether the alias appears in the title or abstract
- publication recency
- citation count
- presence of clinical, biophysical, or preclinical keywords
- publication type adjustments (e.g. penalties for review articles)

This is designed to surface likely relevant antibody literature, not to replace full manual curation.

**Notes and suggestions**

- Use `--ncbi-email` and `--ncbi-key` when you have API credentials to help providers recognize your requests.
- Use a lower `--min-score` if too few candidates are returned.
- For larger datasets, add caching or incremental update logic to avoid repeating past searches.

**Existing files**

- `antibodies.csv` — example input file with therapeutic names and synonyms.
- `literature_results.csv`, `literature_top5_per_therapeutic.csv` — example output files.


