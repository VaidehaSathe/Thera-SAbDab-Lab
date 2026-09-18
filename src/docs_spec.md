# Build and fully test a production-quality standalone Thera-SAbDab WHO INN desktop application

I want you to **build the finished application and give me the downloadable project/product in this conversation**. Do not merely give me code snippets, architectural advice, pseudo-code, or another prompt.

You have been given:

1.  the original WHO Proposed INN List 135 PDF; 
2.  the completed curated/enriched Excel workbook that was previously produced from that PDF; 
3.  the original canonical `.md` curation prompt that specifies exactly how the workbook is supposed to be produced; 
4.  optionally PL129 as an additional regression/generalisation test. 

**Read all three authoritative files before designing or coding anything.**

The `.md` file is the authoritative scientific curation specification.

The supplied completed PL135 Excel workbook is the **gold-standard output/template/database**.

The supplied PL135 PDF is the **gold-standard source document**.

Your central engineering task is therefore:

**reverse-engineer and reproduce the successful PL135 PDF → completed WHO-derived database-record transformation, then turn that workflow into a robust standalone Windows application that can process future WHO INN PDFs.**

Do not replace the successful curation methodology with a generic OCR pipeline.

---

## 1. End product I want

Build a polished standalone Windows desktop application called:

**Thera-SAbDab WHO INN Curator**

It should initially contain the data from my supplied completed PL135 workbook.

A normal user should be able to launch the application without opening:

-  Python 
-  VS Code 
-  Excel 
-  a command prompt 

The final distributable should ultimately be a standalone `.exe` or a clean Windows application folder/installer.

The end user should not need Python installed.

The end user should not need Tesseract installed separately if it can legally/practically be bundled.

**Do not use any paid API, LLM API, OpenAI API, cloud OCR, subscription service, or usage credits.**

Core functionality must work locally/offline.

---

# 2. There are TWO major parts of the application

## A. Database/search application

The existing completed PL135 workbook becomes the initial database.

Provide a polished UI for:

-  searching by INN; 
-  aliases/development codes; 
-  CAS; 
-  target; 
-  description; 
-  clinical-trial ID; 
-  patent number; 
-  literature; 
-  other stored fields. 

Include:

-  autocomplete; 
-  A-Z browsing; 
-  advanced filters; 
-  favorites; 
-  recent records; 
-  dashboard; 
-  drug comparison; 
-  sequence viewer; 
-  evidence viewer; 
-  QC status; 
-  manual-review status; 
-  export/copy functionality. 

Selecting a drug should expose **all fields contained in the canonical workbook**, not a simplified subset.

Sequence presentation should have dedicated HC, LC and non-variable sections with copy buttons and lengths.

Literature, trials, immunogenicity and patents should be displayed clearly rather than as an unreadable text dump.

---

## B. WHO INN PDF importer

The user should be able to click:

**Import WHO INN PDF**

and select a future Proposed INN or Recommended INN PDF.

The application must convert qualifying therapeutic-antibody entries into records following the **same scientific rules that produced the supplied PL135 workbook**.

After validation/review, approved records are added to the persistent local database.

This must work for future:

-  List 136 
-  List 137 
-  List 138 
-  etc. 

Do not hard-code List 135.

---

# 3. FIRST perform a gold-standard analysis

Before implementing the generic importer, programmatically compare the supplied PL135 PDF with the supplied completed PL135 workbook.

Determine:

-  how many qualifying antibodies are present; 
-  which WHO entries were included; 
-  which entries were excluded; 
-  how descriptions map to rows; 
-  how HC/LC physical counts were determined; 
-  how WHO sequence blocks map to FASTA records; 
-  how repeated physical copies are represented; 
-  how non-variable FASTA was derived; 
-  how PTMs map to rows; 
-  how physical PDF pages map to rows; 
-  how QA notes were constructed; 
-  how complex architectures are represented. 

Treat this PDF/workbook pair as a **golden regression dataset**.

The generic importer is not acceptable until it can reproduce the WHO-derived portions of these records.

---

# 4. Exact workbook schema

Inspect the supplied workbook directly and preserve its schema.

The main `Antibody Database` sheet currently uses these fields:

1.  Drug name 
2.  English Description 
3.  Antibody Structure Summary 
4.  Heavy Chain Count 
5.  Heavy Chain FASTA 
6.  Light Chain Count 
7.  Light Chain FASTA 
8.  Non-Variable chain FASTA (WHO/IMGT-Defined) 
9.  Post Translational Modifications 
10.  PDF Page number 
11.  Quality Assessment Notes 
12.  Alternative Drug Names 
13.  Literature using the drug 
14.  Clinical Trials 
15.  Any publicly available Immunogenicity Data (including ADA etc) 
16.  Patent information 
17.  External Evidence / Search Notes 
18.  CAS Registry Number 
19.  Sequence QC Status 

**Verify these against the actual workbook rather than blindly trusting this list.**

Do not rename/reorder them.

Preserve supporting sheets such as:

-  QA Summary 
-  Evidence Ledger 
-  Sources & Scope 
-  Manual Review 

Preserve workbook formatting where practical.

---

# 5. Critical PDF-extraction design

Do **not** implement:

`OCR everything → interpret arbitrary OCR tokens as drugs`.

Previous attempts did this and produced false records such as:

-  CH2 
-  CH3 
-  chain headings 
-  French entries 
-  Spanish entries 
-  duplicates 

Instead use:

`WHO document structure + native PDF information + rendered-page inspection/OCR + scientific validation`.

Drug entry identification and OCR must be separate concepts.

OCR must never independently create a drug record.

---

# 6. Follow the canonical PDF strategy

The `.md` prompt says native extraction should be used first, with rendered-page inspection/OCR used where native extraction is missing/corrupt.

Follow that principle.

Do not assume sequence/PTM content is selectable text.

Render pages to **lossless PNG** when visual extraction is necessary.

Keep physical page numbers.

Use local OCR only.

If you decide to OCR every page for a secondary representation, that is acceptable, but **do not trust OCR over clean native text merely because OCR exists**.

The important thing is reconciliation:

`native text + rendered page + OCR where needed → validated record`.

---

# 7. Fix the previous entry-boundary failure

This is critical.

A physical WHO page can contain:

-  the end of drug A; 
-  drug B's description; 
-  French/Spanish copies; 
-  drug B's CAS; 
-  drug B's sequence; 
-  drug B's PTMs; 
-  the beginning of drug C. 

Do NOT assign the entire page to every candidate on it.

Determine the actual WHO entry boundary.

Store page/start/end provenance where practical.

This must prevent:

-  previous drug's CAS being assigned; 
-  next drug's CAS being assigned; 
-  wrong sequence block; 
-  wrong PTM block; 
-  page-range inflation. 

---

# 8. English-only extraction

Follow the canonical prompt exactly.

Extract only the English WHO description/PTM content into English fields.

Do not translate French/Spanish.

Do not include them.

Detect multilingual boundaries structurally, including page-spanning entries.

---

# 9. Antibody inclusion/exclusion

Use the `.md` specification.

Include genuine therapeutic molecules containing antibody variable domains, including conventional antibodies, fragments, VHH/nanobody therapeutics, multispecifics, asymmetric antibodies, common-light-chain constructs, antibody-scFv/domain fusions, ADCs, radioconjugates and other qualifying non-canonical constructs.

Normally exclude CAR/cell therapies where the scFv/VHH is merely part of a CAR, gene therapies encoding antibody-derived components, Fc-only fusions without variable domains, non-antibody proteins, peptides, oligonucleotides and small molecules.

Do not infer classification from OCR noise.

---

# 10. Sequence extraction must be high precision

Recognize:

-  H 
-  H'' 
-  H''' 
-  L' 
-  L''' 
-  L'''' 
-  multiple non-equivalent chains 
-  common light chains 
-  appended scFv/VHH domains 
-  fusion chains 
-  fragments lacking Fc 

**Never assume every antibody is H2L2.**

Physical chain count is not unique sequence count.

---

# 11. FASTA rules

Follow the `.md` convention exactly.

Represent each physical chain copy explicitly.

Example:

`>drug|HC1|copy=1/2|sequence_group=HC-A|identical_copies=2`

and

`>drug|HC2|copy=2/2|sequence_group=HC-A|identical_to=HC1`

For asymmetric chains use different groups.

Do the same for light chains.

---

# 12. Mandatory residue-level QC

This is non-negotiable.

For every sequence:

-  normalize to uppercase amino-acid letters; 
-  remove spaces and printed residue counts; 
-  alphabet check; 
-  compare reconstructed length with WHO printed terminal count; 
-  explicitly check final short sequence line; 
-  compare description coordinate; 
-  validate WHO/IMGT variable coordinates; 
-  compare repeated chains when stated identical; 
-  inspect rendered page on any mismatch. 

Never silently repair an amino acid because another antibody or external database looks similar.

If one residue remains uncertain:

`Sequence QC Status = REVIEW`

and explain why.

---

# 13. Non-variable FASTA

Derive this **only** from explicit WHO/IMGT variable-domain coordinates.

Do not infer VH/VL boundaries from motifs, alignments or standard antibody lengths.

Remove all explicit variable intervals from the validated physical chain.

Preserve constant regions, hinge/Fc, linkers and fusion domains.

If the retained regions are discontiguous, output separate FASTA segments with coordinate provenance.

Never silently concatenate discontiguous segments.

---

# 14. PTMs

Extract only explicitly WHO-defined PTMs/structural modifications:

-  disulfides; 
-  glycosylation; 
-  glycans; 
-  clipping; 
-  pyroglutamate; 
-  conjugation sites; 
-  terminal processing; 
-  explicitly stated modifications. 

Do not infer predicted PTMs.

---

# 15. Import Review must actually work

Previous versions displayed “Pending Import Review” but did not provide a usable scientific review workflow.

Fix this completely.

After PDF processing, automatically open a review workspace.

Left side:

-  candidate list; 
-  PASS / REVIEW / ERROR; 
-  new/existing; 
-  approved/rejected/pending. 

Right side:

tabs for:

-  All Fields 
-  HC FASTA 
-  LC FASTA 
-  Non-variable FASTA 
-  PTMs 
-  QA 
-  Source 
-  Native Text 
-  OCR/visual extraction 

Show **all canonical spreadsheet fields**.

Provide:

-  Approve Current 
-  Reject Current 
-  Approve All PASS 
-  Clear Approved 
-  Merge Approved 
-  Mark Manual Review 
-  Edit/Correct Field 
-  Open Source Page 
-  Open PDF 

Clicking a row to inspect it must NOT automatically approve it.

REVIEW records must never be silently included by “Approve All PASS”.

Pending review must survive application restart.

There must be a permanent:

**Pending Import Review**

navigation item.

---

# 16. Manual corrections must be auditable

If the reviewer corrects an extracted field:

preserve:

-  original extracted value; 
-  corrected value; 
-  reason; 
-  timestamp; 
-  source page; 
-  review status. 

Do not silently replace the extraction.

---

# 17. Safe database merging

Before every merge:

automatically back up the database.

Detect:

-  exact existing INN; 
-  same WHO list; 
-  duplicates; 
-  conflicts. 

Do not overwrite stronger existing curation.

WHO normally takes precedence for official INN, WHO description, sequence, PTMs and WHO coordinates.

External evidence must never alter WHO sequence data.

Reimporting the same WHO list must not duplicate records.

---

# 18. Import Workbook must MERGE, not replace

A previous version simply copied an imported workbook over the working database.

Do not do that.

`Import Workbook` must:

-  back up; 
-  inspect schema; 
-  compare by INN; 
-  add new records; 
-  preserve stronger existing records; 
-  record conflicts; 
-  preserve evidence/history. 

---

# 19. External enrichment

Implement this as a separate optional stage after WHO extraction.

It must follow the supplied `.md` prompt exactly.

Search for:

-  verified alternative names/development codes; 
-  literature actually using the drug; 
-  attributable clinical trials; 
-  ADA/NAb/immunogenicity; 
-  defensible patent families. 

Use free public sources only.

No paid APIs.

Do not merely dump search hits into the final field.

First perform identity/alias resolution.

Require molecule-level attribution.

Target-only matches do not count.

Sponsor-only matches do not prove identity.

Sequence similarity alone does not establish an alias.

---

# 20. Hyperlink validation

Implement the dedicated URL-validation pass required by the `.md`.

Validate every URL written to the workbook.

Record:

-  valid; 
-  redirected-valid; 
-  blocked/inaccessible; 
-  broken/replaced; 
-  unresolved. 

Include hyperlink statistics in QA Summary.

---

# 21. UI quality

Make the application pleasant to use.

I want something that looks like a real scientific database application rather than a Tkinter prototype.

Prefer **PySide6/Qt** for the final GUI if practical.

Include:

-  modern navigation/sidebar; 
-  dashboard; 
-  search; 
-  browse; 
-  record details; 
-  sequences; 
-  evidence; 
-  compare; 
-  import/review; 
-  settings/about. 

Use readable typography and sensible spacing.

Long descriptions and FASTA must be easy to read.

---

# 22. Database functionality

Include:

-  search/autocomplete; 
-  fuzzy alias search; 
-  CAS search; 
-  target search; 
-  A-Z browse; 
-  filters; 
-  favorites; 
-  recent drugs; 
-  comparison of 2–5 drugs; 
-  sequence viewer; 
-  evidence browser; 
-  copy FASTA; 
-  export drug TXT/JSON/HTML; 
-  printable report; 
-  database backup; 
-  restore; 
-  import workbook; 
-  import WHO PDF. 

---

# 23. Persistent database

The initial database should be seeded from the supplied PL135 workbook.

On first launch, create a writable working database under the user's application-data directory.

The `.exe` should not require the original Excel file to remain beside it.

Future imported WHO lists should update the working database after approval.

Preserve provenance for each WHO list.

---

# 24. Regression testing — use the workbook, not just hard-coded counts

This is extremely important.

Do not merely test:

`70 records found`.

Build an automated **golden regression suite** by comparing the PL135 importer output against the supplied completed PL135 workbook.

For every qualifying PL135 record, where applicable compare:

-  INN; 
-  English description; 
-  CAS; 
-  physical pages; 
-  HC count; 
-  LC count; 
-  FASTA record count; 
-  exact HC sequence; 
-  exact LC sequence; 
-  sequence lengths; 
-  non-variable sequence; 
-  PTMs; 
-  structure; 
-  sequence QC. 

Report discrepancies.

**Do not declare the importer finished while unexplained discrepancies remain.**

---

# 25. Known PL135 control

`avrukibart` must reconcile to the supplied workbook and WHO PDF.

WHO explicitly describes its 450-aa gamma1 HC and 214-aa kappa LC, and the printed sequences terminate at 450 and 214. Use the actual attached files as authority rather than relying only on these values.

---

# 26. Additional PL129 generalisation test

If PL129 is supplied, use it to prove the importer is not hard-coded to PL135.

Known useful regression cases include:

-  abiprubart; 
-  verekitug; 
-  at least one complex multispecific/fusion antibody. 

Verify entry boundaries, CAS, sequence association, chain counts, PTMs and pages.

---

# 27. Complex-architecture tests

Specifically test the importer on:

-  conventional H2L2 IgG; 
-  asymmetric bispecific; 
-  multispecific; 
-  Fab; 
-  scFv fusion; 
-  common-light-chain construct; 
-  ADC/conjugate; 
-  VHH/nanobody if present; 
-  multiple unique HC sequences; 
-  multiple unique LC sequences. 

Do not call the parser generic until these cases work.

---

# 28. Test the actual OCR path

Do not fake the OCR regression with a dummy executable that merely proves a loop runs.

Test:

-  actual page rendering; 
-  actual local Tesseract execution; 
-  OCR text return; 
-  hidden Windows subprocess behavior where testable; 
-  native/OCR reconciliation; 
-  temporary-file cleanup. 

OCR should be a recovery/verification tool, not the authority for clean native sequences.

---

# 29. Test the actual UI workflow

Do not merely test parser functions.

Verify:

`launch → database → search → record → import PDF → review → approve → backup → merge → search imported record → close → reopen → persistence`.

Ensure every button advertised in the UI is actually connected to functioning code.

---

# 30. Clean-machine packaging test

Build the Windows application with PyInstaller or another suitable packager.

Test/document operation on a clean Windows environment without:

-  Python; 
-  VS Code; 
-  separate project dependencies; 
-  separately installed Tesseract if you claim it is bundled. 

Do not call it standalone unless this is actually true.

---

# 31. Do not overclaim

If something cannot be tested in your current environment, explicitly distinguish:

-  tested; 
-  code-inspected; 
-  not executable in this environment; 
-  requires Windows verification. 

Do not say “fully validated” merely because the Python code compiles.

---

# 32. Final pre-delivery audit

Before giving me the ZIP/product, inspect the complete codebase for:

-  syntax errors; 
-  missing imports; 
-  dead/unreachable code; 
-  buttons without handlers; 
-  wrong version numbers; 
-  missing bundled resources; 
-  hard-coded List 135 assumptions; 
-  incorrect paths; 
-  workbook-schema mismatch; 
-  destructive workbook import; 
-  duplicate-import behavior; 
-  entry-boundary contamination; 
-  neighbouring CAS contamination; 
-  wrong sequence association; 
-  chain-count errors; 
-  FASTA formatting errors; 
-  invalid residues; 
-  non-variable segmentation errors; 
-  French/Spanish carryover; 
-  source-page errors; 
-  review-state errors; 
-  unsafe merging; 
-  OCR console-window flashing; 
-  fake/inadequate regression tests; 
-  unsupported scientific inference. 

Fix identified problems **before** packaging.

---

# 33. Acceptance criteria

I do not want another version number unless these criteria are addressed:

-  supplied PL135 database loads correctly; 
-  all canonical fields display; 
-  search works; 
-  PL135 PDF can be parsed into the qualifying antibody records; 
-  PL135 importer is regression-tested against the supplied workbook; 
-  sequence data are residue-level validated; 
-  English-only extraction works; 
-  entry boundaries work; 
-  complex antibody architectures are tested; 
-  Import Review works; 
-  Pending Review can be reopened; 
-  REVIEW is not silently approved; 
-  database backup works; 
-  merging works; 
-  reimport does not duplicate; 
-  Import Workbook merges rather than replaces; 
-  local persistence works; 
-  final workbook maintains the canonical schema; 
-  no paid API/credits are required; 
-  executable/build is supplied. 

---

# 34. Deliverables

Give me a downloadable ZIP containing:

-  complete source; 
-  standalone application/build; 
-  Windows build script; 
-  requirements; 
-  bundled resources where appropriate; 
-  seed database; 
-  regression tests; 
-  README; 
-  test results; 
-  known limitations. 

Also provide the resulting `.exe` directly if your environment can build a Windows executable.

If the environment cannot produce a Windows binary, provide a reproducible Windows build script that has been code-reviewed and clearly say the binary itself could not be executed here.

**Do not stop after explaining how to build it. Actually create the project files and ZIP them.**

---

# 35. Working style

Do not ask me repeated minor implementation questions.

Make sensible engineering decisions from the supplied specification.

Work through the project end-to-end.

If a test exposes a bug, fix the bug and rerun the relevant tests before delivery.

Prioritize scientific correctness, provenance, safe review and reproducibility over speed.

**The supplied PL135 PDF + completed PL135 workbook + canonical** **`.md`** **prompt are the source of truth.**

Build the application around them.