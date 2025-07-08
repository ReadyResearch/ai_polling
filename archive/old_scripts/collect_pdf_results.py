#!/usr/bin/env python3

import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def collect_pdf_cache_results():
    """Collect all results from PDF cache and create a dataset."""
    
    cache_dir = Path("pdf_cache")
    if not cache_dir.exists():
        print("No PDF cache directory found")
        return pd.DataFrame()
    
    all_data = []
    cache_files = list(cache_dir.glob("*.json"))
    
    print(f"Found {len(cache_files)} cached PDF extractions")
    
    for cache_file in cache_files:
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                all_data.extend(data)
                print(f"✓ Loaded {len(data)} records from {cache_file.name}")
        except Exception as e:
            print(f"✗ Error loading {cache_file.name}: {e}")
    
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Convert date column
        df['Fieldwork_Date'] = pd.to_datetime(df['Fieldwork_Date'], errors='coerce')
        
        print(f"\n=== PDF EXTRACTION RESULTS ===")
        print(f"Total records: {len(df)}")
        print(f"Organizations: {', '.join(df['Survey_Organisation'].unique())}")
        print(f"Countries: {', '.join(df['Country'].unique())}")
        print(f"Categories: {', '.join(df['Category'].unique())}")
        print(f"Date range: {df['Fieldwork_Date'].min()} to {df['Fieldwork_Date'].max()}")
        
        # Show AI_Regulation breakdown
        ai_reg = df[df['Category'] == 'AI_Regulation']
        print(f"\n=== AI_REGULATION FROM PDFs ===")
        print(f"AI_Regulation records: {len(ai_reg)}")
        if len(ai_reg) > 0:
            print(f"Organizations: {', '.join(ai_reg['Survey_Organisation'].unique())}")
            print(f"Countries: {', '.join(ai_reg['Country'].unique())}")
            
            # Show some example questions
            print(f"\nExample AI Regulation questions:")
            for i, row in ai_reg.head(3).iterrows():
                print(f"- {row['Question_Text'][:80]}...")
        
        # Show summary by category
        print(f"\n=== RECORDS BY CATEGORY ===")
        category_summary = df.groupby(['Category', 'Survey_Organisation']).size().reset_index(name='count')
        print(category_summary.to_string(index=False))
        
        # Save results
        output_dir = Path("extracted_data")
        output_dir.mkdir(exist_ok=True)
        
        csv_file = output_dir / "pdf_extracted_partial.csv"
        json_file = output_dir / "pdf_extracted_partial.json"
        
        df.to_csv(csv_file, index=False)
        df.to_json(json_file, orient='records', indent=2)
        
        print(f"\n💾 Saved partial results:")
        print(f"- {csv_file}")
        print(f"- {json_file}")
        
        return df
    else:
        print("No data found in cache files")
        return pd.DataFrame()

if __name__ == "__main__":
    df = collect_pdf_cache_results()