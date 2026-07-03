#!/usr/bin/env python3
"""Europe PMC literature scraper for therapeutic antibodies.

Reads a 2-column CSV with:
  col0 = therapeutic name
  col1 = synonyms/aliases separated by commas, semicolons, or pipes

Outputs a deduplicated results CSV with confidence scoring.

This version also prints the highest-scoring candidates before thresholding,
which makes it easier to calibrate the score cutoff during development.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import re
import sys
import time
from typing import Any, Dict, List, Tuple

import certifi
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 3
DEFAULT_SLEEP_SECONDS = 0.15
DEFAULT_MIN_YEAR = 1990
DEFAULT_MAX_YEAR = dt.datetime.now().year + 1
DEFAULT_MIN_SCORE = 0.35
DEFAULT_TOP_N = 5
DEFAULT_DEBUG_TOP_N = 20
SYNONYM_SEPARATORS = [",", ";", "|"]

CLINICAL_TERMS = [
    "clinical trial",
    "phase 1",
    "phase 2",
    "phase 3",
    "first in human",
    "first-in-human",
    "phase i",
    "phase ii",
    "phase iii",
    "randomized",
    "randomised",
    "patient",
    "patients",
    "immunogenicity",
    "anti-drug antibody",
    "anti drug antibody",
    "ada",
]

BIOPHYSICAL_TERMS = [
    "affinity",
    "binding",
    "surface plasmon resonance",
    "spr",
    "biolayer interferometry",
    "bli",
    "epitope",
    "epitope mapping",
    "kinetics",
    "stability",
    "thermal stability",
    "developability",
]

PRECLINICAL_TERMS = [
    "preclinical",
    "in vitro",
    "in vivo",
    "animal",
    "mouse",
    "murine",
    "non-human primate",
    "monkey",
    "pharmacokinetic",
    "pharmacodynamic",
    "side effects"
]

REVIEW_TERMS = ["review", "systematic review", "meta-analysis"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Europe PMC for therapeutic literature.")
    parser.add_argument("--input-csv", default="antibodies.csv", help="2-column input CSV (name, synonyms)")
    parser.add_argument("--output-csv", default="literature_results.csv", help="Output CSV path")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Europe PMC page size")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Max pages per search term")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS, help="Seconds between requests")
    parser.add_argument("--min-year", type=int, default=DEFAULT_MIN_YEAR, help="Keep records from this year onward")
    parser.add_argument("--max-year", type=int, default=DEFAULT_MAX_YEAR, help="Keep records up to this year")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE, help="Minimum confidence score to retain")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="Keep the top N scored records per therapeutic")
    parser.add_argument("--wide-output-csv", default="literature_top5_per_therapeutic.csv", help="Wide-format output CSV path")
    parser.add_argument("--debug-top-n", type=int, default=DEFAULT_DEBUG_TOP_N, help="Print the top N scored records")
    parser.add_argument("--ncbi-email", default="", help="Optional email to include for NCBI requests")
    parser.add_argument("--ncbi-key", default="", help="Optional API key/token to include for NCBI requests")
    return parser.parse_args()


def build_session() -> requests.Session:
    session = requests.Session()
    session.verify = certifi.where()
    retries = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "Thera-SAbDab-literature-scraper/1.0"})
    return session


def split_synonyms(raw: Any) -> List[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return []
    for sep in SYNONYM_SEPARATORS:
        if sep in text:
            return [part.strip() for part in text.split(sep) if part.strip()]
    return [text]


def load_antibodies_from_csv(path: str) -> Dict[str, List[str]]:
    df = pd.read_csv(path, header=None, usecols=[0, 1], dtype=str)
    antibodies: Dict[str, List[str]] = {}
    for _, row in df.iterrows():
        common_name = str(row.iloc[0]).strip()
        if not common_name or common_name.lower() == "nan":
            continue
        synonyms = [common_name]
        synonyms.extend(split_synonyms(row.iloc[1]))
        cleaned: List[str] = []
        seen = set()
        for s in synonyms:
            s2 = re.sub(r"\s+", " ", str(s).strip())
            if not s2:
                continue
            key = s2.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(s2)
        antibodies[common_name] = cleaned
    if not antibodies:
        raise ValueError(f"No antibody data found in {path}")
    return antibodies


def escape_query_term(term: str) -> str:
    term = term.strip()
    term = term.replace('"', '')
    return term


def search_query_for_alias(alias: str) -> str:
    alias = escape_query_term(alias)
    if len(alias.split()) == 1:
        return alias
    return f'"{alias}"'


def europe_pmc_search(
    session: requests.Session,
    query: str,
    page_size: int,
    cursor_mark: str = "*",
    ncbi_email: str = "",
    ncbi_key: str = "",
) -> Dict[str, Any]:
    params = {
        "query": query,
        "format": "json",
        "pageSize": page_size,
        "resultType": "core",
        "cursorMark": cursor_mark,
    }
    # Include optional NCBI credentials either as query params or headers
    if ncbi_email:
        params.setdefault("email", ncbi_email)
    if ncbi_key:
        params.setdefault("apiKey", ncbi_key)

    # Prepare per-request headers so we don't mutate session headers globally
    req_headers = None
    if ncbi_key or ncbi_email:
        req_headers = {}
        if ncbi_email:
            req_headers["From"] = ncbi_email
        if ncbi_key:
            req_headers["Authorization"] = f"Bearer {ncbi_key}"

    r = session.get(EUROPE_PMC_SEARCH_URL, params=params, headers=req_headers, timeout=30)
    r.raise_for_status()
    return r.json()


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def parse_year(record: Dict[str, Any]) -> int:
    for key in ("pubYear", "pubyear", "firstPublicationDate", "firstpublicationdate", "pubDate", "pubdate", "date"):
        value = record.get(key)
        if not value:
            continue
        text = str(value)
        m = re.search(r"(19|20)\d{2}", text)
        if m:
            return int(m.group(0))
    return 0


def parse_month(record: Dict[str, Any]) -> int:
    for key in ("firstPublicationDate", "pubDate", "date", "pubDateSort"):
        value = record.get(key)
        if not value:
            continue
        text = str(value)
        m = re.search(r"\b(\d{4})-(\d{2})", text)
        if m:
            return int(m.group(2))
        m = re.search(r"\b(\d{4})/(\d{2})", text)
        if m:
            return int(m.group(2))
    return 1


def compact_text(*parts: Any) -> str:
    text = " ".join(str(p) for p in parts if p not in (None, "", "nan"))
    return re.sub(r"\s+", " ", text).strip().lower()


def count_phrase(text: str, phrase: str) -> int:
    if not text or not phrase:
        return 0
    pattern = re.escape(phrase.lower())
    return len(re.findall(pattern, text.lower()))


def score_record(alias: str, record: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    title = str(record.get("title", record.get("titleText", "")))
    abstract = str(record.get("abstractText", record.get("abstract", "")))
    pub_type_raw = record.get("pubTypeList", {})
    if isinstance(pub_type_raw, dict):
        pub_type_raw = pub_type_raw.get("pubType", [])
    publication_types = " ".join(as_list(pub_type_raw))
    text = compact_text(title, abstract)
    alias_norm = compact_text(alias)

    score = 0.0
    evidence: List[str] = []

    if alias_norm and alias_norm in compact_text(title):
        score += 2.5
        evidence.append("alias_in_title")
    if alias_norm and alias_norm in compact_text(abstract):
        score += 1.5
        evidence.append("alias_in_abstract")

    term_hits = count_phrase(text, alias_norm)
    if term_hits:
        score += min(term_hits * 0.2, 0.6)
        evidence.append(f"term_hits={term_hits}")

    year = parse_year(record)
    if year:
        now_year = dt.datetime.now().year
        recency = math.exp(-0.05 * max(0, now_year - year))
        score += 0.8 * recency
        evidence.append(f"recency={recency:.3f}")

    cited_by = record.get("citedByCount", record.get("citedbycount", 0))
    try:
        cited_by_int = int(cited_by)
    except Exception:
        cited_by_int = 0
    citation_norm = math.log1p(max(0, cited_by_int)) / math.log1p(1000)
    score += 0.6 * citation_norm
    evidence.append(f"citedByCount={cited_by_int}")

    pub_type_lower = publication_types.lower()
    if any(t in pub_type_lower for t in ["clinical trial", "randomized", "controlled trial", "observational study"]):
        score += 0.8
        evidence.append("clinical_pubtype")
    if any(t in pub_type_lower for t in ["review", "systematic review", "meta-analysis"]):
        score -= 0.35
        evidence.append("review_penalty")

    clinical_hits = sum(1 for term in CLINICAL_TERMS if term in text)
    biophysical_hits = sum(1 for term in BIOPHYSICAL_TERMS if term in text)
    preclinical_hits = sum(1 for term in PRECLINICAL_TERMS if term in text)
    review_hits = sum(1 for term in REVIEW_TERMS if term in text)

    score += min(clinical_hits * 0.22, 1.1)
    score += min(biophysical_hits * 0.18, 0.9)
    score += min(preclinical_hits * 0.14, 0.7)
    score -= min(review_hits * 0.10, 0.3)

    if clinical_hits:
        evidence.append(f"clinical_hits={clinical_hits}")
    if biophysical_hits:
        evidence.append(f"biophysical_hits={biophysical_hits}")
    if preclinical_hits:
        evidence.append(f"preclinical_hits={preclinical_hits}")

    return score, {"score_evidence": ";".join(evidence)}


def fetch_alias_records(
    session: requests.Session,
    alias: str,
    page_size: int,
    max_pages: int,
    sleep_seconds: float,
    ncbi_email: str = "",
    ncbi_key: str = "",
) -> List[Dict[str, Any]]:
    query = search_query_for_alias(alias)
    all_records: List[Dict[str, Any]] = []
    seen_keys = set()
    cursor_mark = "*"

    for _ in range(max_pages):
        data = europe_pmc_search(
            session,
            query=query,
            page_size=page_size,
            cursor_mark=cursor_mark,
            ncbi_email=ncbi_email,
            ncbi_key=ncbi_key,
        )
        result_list = data.get("resultList", {}).get("result", [])
        if not result_list:
            break

        for rec in result_list:
            pmid = str(rec.get("pmid", "")).strip()
            doi = str(rec.get("doi", "")).strip().lower()
            key = pmid or doi or str(rec.get("id", "")).strip()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            all_records.append(rec)

        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor_mark:
            break
        cursor_mark = next_cursor
        time.sleep(sleep_seconds)

    return all_records


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    pub_type = record.get("pubTypeList", {})
    if isinstance(pub_type, dict):
        pub_type = pub_type.get("pubType", [])
    pub_type_list = as_list(pub_type)

    source = record.get("source", "")
    rid = record.get("id", "")
    pmid = str(record.get("pmid", "")).strip()
    doi = str(record.get("doi", "")).strip()

    return {
        "source": source,
        "id": rid,
        "pmid": pmid,
        "doi": doi,
        "title": record.get("title", record.get("titleText", "")),
        "abstract": record.get("abstractText", record.get("abstract", "")),
        "journal": record.get("journalTitle", record.get("journal", "")),
        "year": parse_year(record),
        "month": parse_month(record),
        "first_publication_date": record.get("firstPublicationDate", record.get("pubDate", "")),
        "citedByCount": record.get("citedByCount", 0),
        "pub_types": ", ".join(pub_type_list),
        "is_open_access": record.get("isOpenAccess", ""),
        "pubmed_url": f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else "",
        "europe_pmc_url": f'https://europepmc.org/article/{source}/{rid}' if source and rid else "",
    }


def print_top_scores(rows: List[Dict[str, Any]], top_n: int) -> None:
    if not rows:
        return
    print("\nTop raw scores before thresholding:")
    for row in sorted(rows, key=lambda x: (x.get("score", 0.0), x.get("year", 0)), reverse=True)[:top_n]:
        score = row.get("score", 0.0)
        therapeutic = row.get("therapeutic", "")
        search_term = row.get("search_term", "")
        title = row.get("title", "")
        reason = row.get("match_reason", "")
        print(f"{score:.3f} | {therapeutic} | {search_term} | {title} | {reason}")
    print()


def main() -> int:
    args = parse_args()
    antibodies = load_antibodies_from_csv(args.input_csv)
    session = build_session()

    scored_rows: List[Dict[str, Any]] = []

    for therapeutic_name, aliases in antibodies.items():
        print(f"Processing {therapeutic_name} ({len(aliases)} aliases)")
        for alias in aliases:
            print(f"  searching: {alias}")
            try:
                records = fetch_alias_records(
                    session=session,
                    alias=alias,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                    sleep_seconds=args.sleep,
                    ncbi_email=args.ncbi_email,
                    ncbi_key=args.ncbi_key,
                )
            except requests.HTTPError as e:
                print(f"  HTTP error for alias '{alias}': {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"  failed for alias '{alias}': {e}", file=sys.stderr)
                continue

            for rec in records:
                normalized = normalize_record(rec)
                year = normalized["year"]
                if year and not (args.min_year <= year <= args.max_year):
                    continue

                score, extra = score_record(alias, rec)
                scored_row = {
                    "therapeutic": therapeutic_name,
                    "search_term": alias,
                    "score": round(score, 3),
                    "match_reason": extra["score_evidence"],
                    **normalized,
                }
                scored_rows.append(scored_row)

    if not scored_rows:
        print("No records were retrieved.")
        return 0

    print_top_scores(scored_rows, args.debug_top_n)

    candidate_rows: List[Dict[str, Any]] = []
    seen_global = set()
    for scored_row in sorted(scored_rows, key=lambda row: (row.get("score", 0.0), row.get("year", 0)), reverse=True):
        if scored_row.get("score", 0.0) < args.min_score:
            continue

        pmid = str(scored_row.get("pmid", "")).strip()
        doi = str(scored_row.get("doi", "")).strip().lower()
        dedupe_key = pmid or doi or f"{scored_row.get('source','')}:{scored_row.get('id','')}"
        if dedupe_key in seen_global:
            continue
        seen_global.add(dedupe_key)
        candidate_rows.append(scored_row)

    if not candidate_rows:
        print(f"No results matched the score threshold of {args.min_score:.2f}.")
        print("Lower --min-score to retain more candidates, or inspect the printed top scores above.")
        return 0

    selected_rows: List[Dict[str, Any]] = []
    for therapeutic_name in sorted({row["therapeutic"] for row in candidate_rows}):
        therapeutic_rows = [row for row in candidate_rows if row["therapeutic"] == therapeutic_name]
        therapeutic_rows.sort(key=lambda row: (row.get("score", 0.0), row.get("year", 0), row.get("title", "")), reverse=True)
        selected_rows.extend(therapeutic_rows[: max(1, args.top_n)])

    df = pd.DataFrame(selected_rows)
    df.sort_values(by=["therapeutic", "score", "year"], ascending=[True, False, False], inplace=True)
    df.to_csv(args.output_csv, index=False, encoding="utf-8")

    wide_rows: List[Dict[str, str]] = []
    for therapeutic_name, group in df.groupby("therapeutic", sort=False):
        entries = []
        for _, row in group.iterrows():
            title = str(row.get("title", "")).replace("\n", " ").strip()
            score = row.get("score", 0.0)
            pmid = str(row.get("pmid", "")).strip()
            doi = str(row.get("doi", "")).strip()
            ref = f"{title} (score={score:.3f})"
            if pmid:
                ref += f" [PMID:{pmid}]"
            elif doi:
                ref += f" [DOI:{doi}]"
            entries.append(ref)
        wide_rows.append({"therapeutic": therapeutic_name, "top5_papers": "; ".join(entries)})

    wide_df = pd.DataFrame(wide_rows)
    wide_df.to_csv(args.wide_output_csv, index=False, encoding="utf-8")

    print(f"Saved {len(df)} rows to {args.output_csv}")
    print(f"Saved {len(wide_df)} therapeutics to {args.wide_output_csv}")
    print("Breakdown by therapeutic:")
    print(df["therapeutic"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
