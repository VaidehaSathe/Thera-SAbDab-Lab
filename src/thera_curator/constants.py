APP_NAME = "Thera-SAbDab WHO INN Curator"
APP_VERSION = "1.0.4"

CANONICAL_COLUMNS = [
    "Drug name",
    "English Description",
    "Antibody Structure Summary",
    "Heavy Chain Count",
    "Heavy Chain FASTA",
    "Light Chain Count",
    "Light Chain FASTA",
    "Non-Variable chain FASTA (WHO/IMGT-Defined)",
    "Post Translational Modifications",
    "PDF Page number",
    "Quality Assessment Notes",
    "Alternative Drug Names",
    "Literature using the drug",
    "Clinical Trials",
    "Any publicly available Immunogenicity Data (including ADA etc)",
    "Patent information",
    "External Evidence / Search Notes",
    "CAS Registry Number",
    "Sequence QC Status",
]

DB_FIELDS = [
    "drug_name", "english_description", "structure_summary", "heavy_chain_count",
    "heavy_chain_fasta", "light_chain_count", "light_chain_fasta", "non_variable_fasta",
    "ptms", "pdf_pages", "quality_notes", "alternative_names", "literature",
    "clinical_trials", "immunogenicity", "patent_information", "external_evidence_notes",
    "cas_registry_number", "sequence_qc_status",
]

COLUMN_TO_DB = dict(zip(CANONICAL_COLUMNS, DB_FIELDS))
DB_TO_COLUMN = dict(zip(DB_FIELDS, CANONICAL_COLUMNS))

WHO_AUTHORITY_FIELDS = {
    "drug_name", "english_description", "structure_summary", "heavy_chain_count",
    "heavy_chain_fasta", "light_chain_count", "light_chain_fasta", "non_variable_fasta",
    "ptms", "pdf_pages", "cas_registry_number", "sequence_qc_status",
}

EVIDENCE_FIELDS = {
    "alternative_names", "literature", "clinical_trials", "immunogenicity",
    "patent_information", "external_evidence_notes",
}

AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")
