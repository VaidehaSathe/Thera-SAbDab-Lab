# Thera-SAbDab-LAB: A WHO INN Curator

A Python-based curation tool for converting WHO International Nonproprietary Name (INN) documents into structured, reviewable therapeutic-antibody records and enriching them with public clinical, literature, immunogenicity and patent evidence.

The project aims to reduce manual Thera-SAbDab curation while preserving scientific traceability and human review. It combines deterministic WHO INN parsing, sequence-level QC, a local SQLite database and optional LLM-guided external enrichment.

## Project goals

1. **WHO INN ingestion** — identify qualifying antibody therapeutics and extract names, descriptions, sequences, structural information, PTMs and source provenance.
2. **Sequence annotation** — preserve physical heavy/light-chain structure and derive WHO/IMGT-defined constant-region information from explicit domain coordinates.
3. **Database curation** — stage records in a persistent local database, support review and merge approved records safely.
4. **External enrichment** — use the INN and verified aliases to guide LLM-assisted searches for clinical trials, current medical use, literature, ADA/immunogenicity and patents.

## Application

The intended end product is the **Thera-SAbDab WHO INN Curator**, a standalone desktop application with two main functions.

### Database and search

The application provides a local searchable antibody knowledgebase with INN/alias, target, CAS, trial, patent and literature search; sequence and evidence viewers; QC/manual-review status; record comparison/export; and local backup/persistence.

### WHO INN PDF importer

A curator can import future WHO Proposed or Recommended INN PDFs. The importer uses WHO document structure and native PDF content first, with rendered-page inspection and local OCR where required. OCR is used for recovery and verification rather than independently defining drug records.

The importer isolates individual WHO entries and English descriptions, extracts sequences and PTMs, validates physical chain counts and sequence content, and stages candidate records for manual review before database merge. The workflow is intended to support conventional IgGs as well as fragments, nanobodies, asymmetric antibodies, common-light-chain constructs, multispecifics, antibody-domain fusions and conjugates.

## Database architecture

The current lightweight application uses **SQLite** as a portable local backend for parsed WHO INN information, review state and application persistence.

A more complete relational architecture has also been designed for future implementation. Instead of storing each antibody as a single spreadsheet row, it separates repeating or structurally related information into linked entities.

The central `ANTIBODY` record links to alternative names, formats, biochemical targets, manufacturers, medical usage, clinical trials, external references and sequence information.

### Complex sequence representation

The sequence model is designed specifically to avoid assuming every therapeutic is a simple H2L2 antibody.

- `ANTIBODY_SEQUENCE` stores distinct heavy, light or other physical sequences.
- `SEQUENCE_DOMAIN` stores VH, VL, constant-region and WHO/IMGT domain annotations.
- `BINDING_UNIT` represents an antibody arm or functional binding unit.
- A bridge between `BINDING_UNIT` and `ANTIBODY_SEQUENCE` records which chains form each unit.

This allows HC1 + LC1 to define one binding arm and HC2 + LC2 another, while also supporting shared/common light chains, multivalent copies, scFv/VHH components and fusion architectures. The database therefore records both **which sequences belong to an antibody** and **how those sequences are structurally associated**.

Clinical information is modeled separately so one antibody can link to multiple indications, regional usage records, trials and trial-specific ADA, safety, efficacy, PK/PD or qualitative results.

A shared `REFERENCE` layer stores literature, patent, clinical-trial, regulatory and external-database sources. `EVIDENCE` links extracted values to supporting references and review status, while `CHANGE_LOG` provides an audit trail for subsequent updates.

## LLM-assisted web enrichment

External enrichment is a separate stage after WHO-derived information has been parsed.

For each antibody, the LLM workflow first resolves identity by starting from the INN, discovering potential brand names/development codes/aliases and validating that each refers to the same therapeutic. The validated name set is then used to search free, publicly accessible and authoritative sources for:

- current medical usage and regulatory status;
- attributable clinical trials;
- relevant peer-reviewed literature;
- study-specific ADA/immunogenicity data;
- defensible patent records and families.

The workflow prioritizes sources such as WHO, medicines regulators, recognized clinical-trial registries, PubMed/PMC/Europe PMC and public patent resources. News, blogs, unsourced aggregators and other unverified sources are excluded.

Every accepted finding is linked to a `REFERENCE` record and supporting evidence. Missing information is explicitly recorded as `not found during automated scrape` rather than guessed or silently left blank. Each antibody search is recorded as an ingestion run with quality notes, confidence and review state; automated findings remain pending human validation.

## Scientific quality control

Key safeguards include:

- WHO-derived molecular and sequence data are not overwritten by external evidence;
- physical chain count is distinguished from unique sequence count;
- WHO/IMGT coordinates define constant-region extraction rather than inferred boundaries;
- sequences are checked for residue validity and source-consistent length;
- ambiguous extraction is flagged for review;
- English WHO content is isolated from multilingual copies;
- clinical and ADA results remain linked to their specific study context;
- aliases require molecule-level evidence rather than target similarity alone;
- automated enrichment remains reviewable before final curation.

## Workflow

```text
WHO INN PDF
    ↓
PDF parsing + sequence QC
    ↓
Structured WHO-derived records
    ↓
SQLite database / pending review
    ↓
Human approval
    ↓
Optional LLM-assisted web enrichment
    ↓
References + evidence + clinical/literature/patent data
    ↓
Human review
    ↓
Curated antibody knowledgebase
```

## Development status

Working components include WHO INN parsing, sequence/constant-region handling and a lightweight SQLite-backed Python application. The fuller relational architecture and evidence-linked LLM enrichment workflow have been designed for future integration but are not yet fully implemented.

The long-term objective is a reproducible standalone curator that can ingest future WHO INN lists, stage scientifically validated records for review, enrich them from accredited public sources and maintain a traceable local therapeutic-antibody database.
