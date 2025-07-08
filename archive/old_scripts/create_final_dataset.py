#!/usr/bin/env python3

import pandas as pd
import subprocess
from pathlib import Path

def create_final_comprehensive_dataset():
    """Combine all extraction results into final comprehensive dataset."""
    
    print("🔄 Creating final comprehensive dataset...")
    
    # Load existing data (from R format)
    existing_file = Path("extracted_data/combined_polling_data.rds")
    if existing_file.exists():
        # Convert RDS to CSV using R
        subprocess.run([
            "Rscript", "-e", 
            "data <- readRDS('extracted_data/combined_polling_data.rds'); write.csv(data, 'temp_existing.csv', row.names=FALSE)"
        ])
        existing_df = pd.read_csv("temp_existing.csv")
        print(f"✓ Loaded {len(existing_df)} existing records")
    else:
        existing_df = pd.DataFrame()
        print("No existing data found")
    
    # Load current PDF results
    pdf_file = Path("extracted_data/current_pdf_latest.csv")
    if pdf_file.exists():
        pdf_df = pd.read_csv(pdf_file)
        print(f"✓ Loaded {len(pdf_df)} new PDF records")
    else:
        print("❌ No PDF results found")
        return existing_df
    
    # Combine datasets
    if not existing_df.empty:
        # Ensure compatible date formats
        existing_df['Fieldwork_Date'] = pd.to_datetime(existing_df['Fieldwork_Date'], errors='coerce')
        pdf_df['Fieldwork_Date'] = pd.to_datetime(pdf_df['Fieldwork_Date'], errors='coerce')
        
        # Combine
        combined_df = pd.concat([existing_df, pdf_df], ignore_index=True)
        
        # Remove duplicates based on key fields
        initial_count = len(combined_df)
        combined_df = combined_df.drop_duplicates(
            subset=['Question_Text', 'Country', 'Survey_Organisation'], 
            keep='first'
        )
        
        if len(combined_df) < initial_count:
            print(f"🧹 Removed {initial_count - len(combined_df)} duplicate records")
            
    else:
        combined_df = pdf_df
    
    print(f"\n=== FINAL COMPREHENSIVE DATASET ===")
    print(f"📊 Total records: {len(combined_df)}")
    print(f"🏢 Organizations: {len(combined_df['Survey_Organisation'].unique())}")
    print(f"🌍 Countries: {len(combined_df['Country'].unique())}")
    print(f"📅 Date range: {combined_df['Fieldwork_Date'].min()} to {combined_df['Fieldwork_Date'].max()}")
    
    # Show all organizations
    print(f"\n🏢 ALL SURVEY ORGANIZATIONS:")
    org_counts = combined_df['Survey_Organisation'].value_counts()
    for org, count in org_counts.items():
        print(f"  • {org}: {count} records")
    
    # Category breakdown
    print(f"\n📂 RECORDS BY CATEGORY:")
    category_counts = combined_df['Category'].value_counts()
    for category, count in category_counts.items():
        print(f"  {category}: {count} records")
    
    # AI Regulation comprehensive analysis
    ai_reg = combined_df[combined_df['Category'] == 'AI_Regulation']
    print(f"\n🏛️ COMPREHENSIVE AI_REGULATION ANALYSIS:")
    print(f"Total AI_Regulation records: {len(ai_reg)}")
    
    if len(ai_reg) > 0:
        ai_reg_orgs = ai_reg['Survey_Organisation'].value_counts()
        print(f"\nOrganizations with AI_Regulation questions:")
        for org, count in ai_reg_orgs.items():
            print(f"  • {org}: {count} questions")
        
        countries = ai_reg['Country'].value_counts()
        print(f"\nCountries with AI_Regulation data:")
        for country, count in countries.items():
            print(f"  • {country}: {count} questions")
        
        # Calculate average agreement
        valid_agreement = ai_reg[ai_reg['Agreement'].notna()]
        if len(valid_agreement) > 0:
            avg_agreement = valid_agreement['Agreement'].mean()
            print(f"\nAverage agreement on AI regulation: {avg_agreement:.1f}%")
    
    # Save comprehensive results
    output_dir = Path("extracted_data")
    
    # Save as CSV and JSON
    final_csv = output_dir / "comprehensive_polling_data.csv"
    final_json = output_dir / "comprehensive_polling_data.json"
    
    combined_df.to_csv(final_csv, index=False)
    combined_df.to_json(final_json, orient='records', indent=2)
    
    print(f"\n💾 Final comprehensive dataset saved:")
    print(f"  📄 {final_csv}")
    print(f"  📄 {final_json}")
    
    # Clean up temp file
    temp_file = Path("temp_existing.csv")
    if temp_file.exists():
        temp_file.unlink()
    
    return combined_df

def upload_to_google_sheets(df):
    """Upload comprehensive dataset to Google Sheets."""
    
    print(f"\n📤 Uploading {len(df)} records to Google Sheets...")
    
    # Save as temp file for R to process
    df.to_csv("temp_comprehensive_upload.csv", index=False)
    
    # Use R to upload
    r_script = """
    library(googlesheets4)
    library(readr)
    
    # Read the data
    data <- read_csv('temp_comprehensive_upload.csv', show_col_types = FALSE)
    cat('Loaded', nrow(data), 'records for upload\\n')
    
    # Authenticate (using cached token)
    gs4_auth()
    
    # The spreadsheet ID
    sheet_id <- "1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE"
    
    # Clear and upload to tab 3
    tryCatch({
        range_clear(ss = sheet_id, sheet = 3)
        range_write(
            ss = sheet_id,
            data = data,
            sheet = 3,
            range = "A1",
            col_names = TRUE,
            reformat = FALSE
        )
        cat('✅ Successfully uploaded', nrow(data), 'records to Google Sheet tab 3\\n')
    }, error = function(e) {
        cat('❌ Error uploading to Google Sheets:', e$message, '\\n')
    })
    
    # Clean up
    file.remove('temp_comprehensive_upload.csv')
    """
    
    # Write and run R script
    with open("upload_comprehensive.R", "w") as f:
        f.write(r_script)
    
    result = subprocess.run(["Rscript", "upload_comprehensive.R"], 
                          capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    
    # Clean up
    Path("upload_comprehensive.R").unlink(missing_ok=True)
    Path("temp_comprehensive_upload.csv").unlink(missing_ok=True)

def main():
    """Main execution function."""
    
    # Create comprehensive dataset
    final_df = create_final_comprehensive_dataset()
    
    if not final_df.empty:
        # Upload to Google Sheets
        upload_to_google_sheets(final_df)
        
        print(f"\n🎉 COMPREHENSIVE POLLING ANALYSIS COMPLETE!")
        print(f"📊 Dataset: {len(final_df)} records from {len(final_df['Survey_Organisation'].unique())} organizations")
        
        ai_reg_count = len(final_df[final_df['Category'] == 'AI_Regulation'])
        print(f"🏛️ AI Regulation questions: {ai_reg_count} from multiple organizations")
        
        print(f"✅ Results uploaded to Google Sheet and saved locally")
    else:
        print("❌ No data to process")

if __name__ == "__main__":
    main()