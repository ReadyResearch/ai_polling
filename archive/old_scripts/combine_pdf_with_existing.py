#!/usr/bin/env python3

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

def combine_pdf_with_existing():
    """Combine PDF extraction results with existing dataset."""
    
    # Load existing data
    existing_file = Path("extracted_data/combined_polling_data.rds")
    if existing_file.exists():
        # Use R to convert RDS to CSV for Python
        import subprocess
        subprocess.run([
            "Rscript", "-e", 
            "data <- readRDS('extracted_data/combined_polling_data.rds'); write.csv(data, 'extracted_data/existing_for_python.csv', row.names=FALSE)"
        ])
        existing_df = pd.read_csv("extracted_data/existing_for_python.csv")
        print(f"Loaded {len(existing_df)} existing records")
    else:
        existing_df = pd.DataFrame()
        print("No existing data file found")
    
    # Load PDF extraction results
    pdf_file = Path("extracted_data/pdf_extracted_partial.csv")
    if pdf_file.exists():
        pdf_df = pd.read_csv(pdf_file)
        print(f"Loaded {len(pdf_df)} PDF extraction records")
    else:
        print("No PDF extraction results found")
        return existing_df
    
    # Combine datasets
    if not existing_df.empty:
        # Ensure compatible column types
        existing_df['Fieldwork_Date'] = pd.to_datetime(existing_df['Fieldwork_Date'], errors='coerce')
        pdf_df['Fieldwork_Date'] = pd.to_datetime(pdf_df['Fieldwork_Date'], errors='coerce')
        
        # Combine
        combined_df = pd.concat([existing_df, pdf_df], ignore_index=True)
    else:
        combined_df = pdf_df
    
    print(f"\n=== COMBINED DATASET ===")
    print(f"Total records: {len(combined_df)}")
    print(f"Organizations: {len(combined_df['Survey_Organisation'].unique())}")
    print(f"Date range: {combined_df['Fieldwork_Date'].min()} to {combined_df['Fieldwork_Date'].max()}")
    
    # AI Regulation analysis
    ai_reg = combined_df[combined_df['Category'] == 'AI_Regulation']
    print(f"\n=== AI_REGULATION COVERAGE ===")
    print(f"Total AI_Regulation records: {len(ai_reg)}")
    print(f"Organizations with AI_Regulation questions:")
    
    ai_reg_summary = ai_reg.groupby('Survey_Organisation').size().reset_index(name='count')
    for _, row in ai_reg_summary.iterrows():
        print(f"  - {row['Survey_Organisation']}: {row['count']} questions")
    
    # Show records by category
    print(f"\n=== RECORDS BY CATEGORY ===")
    category_summary = combined_df.groupby(['Category']).size().reset_index(name='count')
    category_summary = category_summary.sort_values('count', ascending=False)
    for _, row in category_summary.iterrows():
        print(f"  {row['Category']}: {row['count']} records")
    
    # Save combined results
    output_dir = Path("extracted_data")
    combined_csv = output_dir / "enhanced_polling_data.csv"
    combined_json = output_dir / "enhanced_polling_data.json"
    
    combined_df.to_csv(combined_csv, index=False)
    combined_df.to_json(combined_json, orient='records', indent=2)
    
    print(f"\n💾 Saved enhanced dataset:")
    print(f"- {combined_csv}")
    print(f"- {combined_json}")
    
    return combined_df

if __name__ == "__main__":
    df = combine_pdf_with_existing()