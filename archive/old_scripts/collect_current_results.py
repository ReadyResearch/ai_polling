#!/usr/bin/env python3

import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def collect_all_current_results():
    """Collect all current PDF extraction results."""
    
    cache_dir = Path("pdf_cache")
    if not cache_dir.exists():
        print("No cache directory found")
        return pd.DataFrame()
    
    # Get all JSON cache files (not debug files)
    cache_files = [f for f in cache_dir.glob("*.json") if not f.name.startswith("debug_")]
    
    print(f"Found {len(cache_files)} successful PDF extractions")
    
    all_data = []
    file_summary = []
    
    for cache_file in cache_files:
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                
            if data and len(data) > 0:
                all_data.extend(data)
                
                # Get org info for summary
                orgs = list(set(record.get('Survey_Organisation', 'Unknown') for record in data))
                file_summary.append({
                    'file': cache_file.name,
                    'records': len(data),
                    'organizations': ', '.join(orgs)
                })
                print(f"✓ {cache_file.name}: {len(data)} records from {', '.join(orgs)}")
            
        except Exception as e:
            print(f"✗ Error loading {cache_file.name}: {e}")
    
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Clean data
        df['Fieldwork_Date'] = pd.to_datetime(df['Fieldwork_Date'], errors='coerce')
        
        # Convert numeric columns
        numeric_cols = ['Agreement', 'Neutral', 'Disagreement', 'N_Respondents']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove duplicates and invalid records
        initial_count = len(df)
        df = df.dropna(subset=['Question_Text', 'Survey_Organisation'])
        df = df[df['Question_Text'].str.strip() != '']
        df = df.drop_duplicates(subset=['Question_Text', 'Country', 'Survey_Organisation'], keep='first')
        
        print(f"\n=== CURRENT PDF EXTRACTION RESULTS ===")
        print(f"Total records: {len(df)} (removed {initial_count - len(df)} invalid/duplicates)")
        print(f"Organizations: {', '.join(sorted(df['Survey_Organisation'].unique()))}")
        print(f"Countries: {len(df['Country'].unique())}")
        print(f"Date range: {df['Fieldwork_Date'].min()} to {df['Fieldwork_Date'].max()}")
        
        # Category breakdown
        print(f"\n=== RECORDS BY CATEGORY ===")
        category_counts = df['Category'].value_counts()
        for category, count in category_counts.items():
            print(f"{category}: {count} records")
        
        # AI Regulation details
        ai_reg = df[df['Category'] == 'AI_Regulation']
        print(f"\n=== AI_REGULATION DETAILS ===")
        print(f"Total AI_Regulation records: {len(ai_reg)}")
        
        if len(ai_reg) > 0:
            org_counts = ai_reg['Survey_Organisation'].value_counts()
            print(f"Organizations with AI_Regulation questions:")
            for org, count in org_counts.items():
                print(f"  • {org}: {count} questions")
            
            print(f"Countries with AI_Regulation data: {', '.join(sorted(ai_reg['Country'].unique()))}")
            
            # Show some example questions
            print(f"\nExample AI_Regulation questions:")
            for i, row in ai_reg.head(3).iterrows():
                print(f"  • {row['Question_Text'][:80]}... ({row['Survey_Organisation']})")
        
        # Save current results
        output_dir = Path("extracted_data")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = output_dir / f"current_pdf_results_{timestamp}.csv"
        json_file = output_dir / f"current_pdf_results_{timestamp}.json"
        
        df.to_csv(csv_file, index=False)
        df.to_json(json_file, orient='records', indent=2)
        
        # Also save as latest
        df.to_csv(output_dir / "current_pdf_latest.csv", index=False)
        df.to_json(output_dir / "current_pdf_latest.json", orient='records', indent=2)
        
        print(f"\n💾 Current results saved:")
        print(f"  📄 {csv_file}")
        print(f"  📄 Latest: {output_dir / 'current_pdf_latest.csv'}")
        
        return df
    else:
        print("No valid data found")
        return pd.DataFrame()

if __name__ == "__main__":
    df = collect_all_current_results()