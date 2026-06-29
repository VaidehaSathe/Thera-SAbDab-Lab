#!/usr/bin/env python3
"""
Text Parser
Parses OCR text to extract INN entries and segment into fields:
- INN (title ending with #)
- Chemical description
- Amino acid sequences
- Post-translational modifications

Usage:
    python src/text_parser.py data/ocr_text/input.txt data/segmented_text/output.txt
"""

import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional

class TextParser:
    def __init__(self):
        # WHO-defined monoclonal antibody stems
        self.antibody_stems = [
            'omab', 'imab', 'ximab', 'zuimab', 'umab', 'oimab', 'ecomab',
            'zumab', 'timab', 'sumab', 'limab', 'nimab', 'momab', 'vomab',
            'romab', 'gomab', 'somab', 'tomab', 'dumab'
        ]
        
        # Language patterns
        self.language_markers = {
            'french': ['Nom chimique', 'Description chimique', 'Utilisation'],
            'spanish': ['Nombre químico', 'Descripción química', 'Uso'],
            'russian': ['[\u0400-\u04FF]'],
            'chinese': ['[\u4E00-\u9FFF]']
        }
    
    def is_inn_title(self, line: str) -> bool:
        """
        Check if line is an INN title (ends with #)
        """
        return re.search(r'\s#\s*$', line.strip())
    
    def is_antibody(self, inn: str) -> bool:
        """
        Check if INN is a monoclonal antibody using WHO stems
        """
        inn_lower = inn.lower().replace(' ', '')
        return any(inn_lower.endswith(stem) for stem in self.antibody_stems)
    
    def is_non_english(self, text: str) -> bool:
        """
        Detect if text is primarily non-English
        """
        # Check for non-Latin scripts
        if re.search(r'[\u0400-\u04FF]', text):  # Cyrillic
            return True
        if re.search(r'[\u4E00-\u9FFF]', text):  # Chinese
            return True
        if re.search(r'[\u0600-\u06FF]', text):  # Arabic
            return True
        
        return False
    
    def extract_entries(self, text: str) -> List[Dict[str, str]]:
        """
        Parse text and extract INN entries
        
        Returns:
            List of dictionaries with keys: inn, description, sequences, ptm
        """
        entries = []
        lines = text.split('\n')
        
        current_entry = None
        buffer = []
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # Skip page markers
            if line.startswith('[PAGE:'):
                continue
            
            # Check if this is an INN title
            if self.is_inn_title(line):
                # Save previous entry if exists
                if current_entry:
                    current_entry['full_text'] = '\n'.join(buffer)
                    entries.append(current_entry)
                    buffer = []
                
                # Start new entry
                inn = line.replace('#', '').strip()
                current_entry = {
                    'inn': inn,
                    'antibody': self.is_antibody(inn),
                    'language': 'english' if not self.is_non_english(line) else 'mixed'
                }
            
            elif current_entry:
                buffer.append(line)
        
        # Add last entry
        if current_entry:
            current_entry['full_text'] = '\n'.join(buffer)
            entries.append(current_entry)
        
        return entries
    
    def filter_entries(self, entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Filter out:
        - Antibody entries (WHO-defined stems)
        - Non-English entries
        - Duplicates
        """
        filtered = []
        seen_inns = set()
        
        for entry in entries:
            # Skip if already seen (duplicate)
            if entry['inn'] in seen_inns:
                continue
            
            # Skip antibodies
            if entry['antibody']:
                continue
            
            # Skip non-English
            if entry['language'] != 'english':
                continue
            
            filtered.append(entry)
            seen_inns.add(entry['inn'])
        
        return filtered
    
    def parse_sequences_and_ptm(self, full_text: str) -> tuple[str, str]:
        """
        Extract amino acid sequences and PTM info from text block
        """
        # Look for sequences (capital letters separated by hyphens or continuous)
        aa_pattern = r'[A-Z]{3,}(?:-[A-Z]{3})*|[A-Z]{10,}'
        sequences = re.findall(aa_pattern, full_text)
        
        # Look for PTM patterns
        ptm_keywords = ['glycosylation', 'phosphorylation', 'disulfide', 'acetylation', 'modification']
        ptm_text = ' '.join([line for line in full_text.split('\n') 
                            if any(kw in line.lower() for kw in ptm_keywords)])
        
        return ' '.join(sequences[:2]), ptm_text  # Return first 2 sequences and PTM

def main():
    parser = argparse.ArgumentParser(description="Parse OCR text into segmented entries")
    parser.add_argument("input_file", help="Input OCR text file")
    parser.add_argument("output_file", help="Output segmented text file")
    
    args = parser.parse_args()
    
    print(f"Parsing {args.input_file}...\n")
    
    # Read input
    with open(args.input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Parse entries
    parser_obj = TextParser()
    entries = parser_obj.extract_entries(text)
    print(f"Found {len(entries)} entries")
    
    # Filter entries
    filtered = parser_obj.filter_entries(entries)
    print(f"After filtering: {len(filtered)} entries")
    
    # Write output
    Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(args.output_file, 'w', encoding='utf-8') as f:
        for entry in filtered:
            f.write(f"\n=== INN: {entry['inn']} ===\n")
            f.write(entry['full_text'])
            f.write("\n")
    
    print(f"\n✅ Segmented text saved to {args.output_file}")

if __name__ == "__main__":
    main()
