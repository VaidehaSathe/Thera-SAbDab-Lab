#!/usr/bin/env python3
"""
Text to DataFrame Converter
Converts segmented text into a structured pandas DataFrame and saves as TSV.

Usage:
    python src/text_to_df.py data/segmented_text/input.txt data/dataframes/output.tsv
"""

import argparse
import re
import pandas as pd
from pathlib import Path
from typing import Dict, List

class TextToDataFrame:
    def __init__(self):
        pass
    
    def parse_segmented_text(self, file_path: str) -> List[Dict]:
        """
        Parse segmented text file into structured data
        """
        entries = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by INN markers
        blocks = re.split(r'^=== INN: (.+?) ===$', content, flags=re.MULTILINE)
        
        # Process pairs of (inn, text)
        for i in range(1, len(blocks), 2):
            if i + 1 < len(blocks):
                inn = blocks[i].strip()
                text = blocks[i + 1].strip()
                
                # Parse individual fields
                entry = self._parse_entry(inn, text)
                entries.append(entry)
        
        return entries
    
    def _parse_entry(self, inn: str, text: str) -> Dict:
        """
        Parse individual entry to extract fields
        """
        # Extract chemical description (usually first paragraph)
        lines = text.split('\n')
        description = ' '.join([l.strip() for l in lines[:3] if l.strip()])[:200]
        
        # Extract amino acid sequences
        aa_pattern = r'[A-Z]{3,}(?:-[A-Z]{3})*|[A-Z]{10,}'
        sequences = re.findall(aa_pattern, text)
        
        # Try to split into heavy and light chains
        heavy_chain = sequences[0] if len(sequences) > 0 else ''
        light_chain = sequences[1] if len(sequences) > 1 else ''
        
        # Extract PTM information
        ptm_keywords = ['glycosylation', 'phosphorylation', 'disulfide', 'acetylation', 
                       'modification', 'bridge', 'site']
        ptm_lines = [line for line in lines if any(kw in line.lower() for kw in ptm_keywords)]
        ptm = ' '.join(ptm_lines)[:300] if ptm_lines else ''
        
        return {
            'INN': inn,
            'Chemical_Description': description,
            'Heavy_Chain_Sequence': heavy_chain,
            'Light_Chain_Sequence': light_chain,
            'Post_Translational_Modifications': ptm
        }
    
    def create_dataframe(self, entries: List[Dict]) -> pd.DataFrame:
        """
        Create pandas DataFrame from entries
        """
        return pd.DataFrame(entries)

def main():
    parser = argparse.ArgumentParser(description="Convert segmented text to DataFrame")
    parser.add_argument("input_file", help="Input segmented text file")
    parser.add_argument("output_file", help="Output TSV file")
    
    args = parser.parse_args()
    
    print(f"Converting {args.input_file} to DataFrame...\n")
    
    # Parse and create dataframe
    converter = TextToDataFrame()
    entries = converter.parse_segmented_text(args.input_file)
    df = converter.create_dataframe(entries)
    
    print(f"Extracted {len(df)} entries")
    print(f"\nDataFrame shape: {df.shape}")
    print(f"\nFirst entry:")
    print(df.iloc[0] if len(df) > 0 else "No entries")
    
    # Save to TSV
    Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output_file, sep='\t', index=False, encoding='utf-8')
    
    print(f"\n✅ DataFrame saved to {args.output_file}")

if __name__ == "__main__":
    main()
