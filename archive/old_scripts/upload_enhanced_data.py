#!/usr/bin/env python3

import pandas as pd
from pathlib import Path

try:
    import gspread
    from google.auth import default
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run(["pip", "install", "gspread", "google-auth"])
    import gspread
    from google.auth import default

def upload_to_google_sheets():
    """Upload enhanced dataset to Google Sheets."""
    
    # Load the enhanced dataset
    csv_file = Path("extracted_data/enhanced_polling_data.csv")
    if not csv_file.exists():
        print("Enhanced dataset not found")
        return
    
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} records to upload")
    
    try:
        # Set up Google Sheets client
        import os
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            print("Error: GOOGLE_API_KEY environment variable not set")
            return
        
        # Use googlesheets4 approach via R since we have the auth set up
        import subprocess
        
        # First save the data in a format R can read
        df.to_csv("temp_upload_data.csv", index=False)
        
        # Use R to upload via googlesheets4
        r_script = """
        library(googlesheets4)
        library(readr)
        
        # Read the data
        data <- read_csv('temp_upload_data.csv')
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
            cat('Successfully uploaded', nrow(data), 'records to Google Sheet tab 3\\n')
        }, error = function(e) {
            cat('Error uploading to Google Sheets:', e$message, '\\n')
        })
        
        # Clean up
        file.remove('temp_upload_data.csv')
        """
        
        # Write R script to file
        with open("upload_script.R", "w") as f:
            f.write(r_script)
        
        # Run R script
        result = subprocess.run(["Rscript", "upload_script.R"], 
                              capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        
        # Clean up
        Path("upload_script.R").unlink(missing_ok=True)
        Path("temp_upload_data.csv").unlink(missing_ok=True)
        
    except Exception as e:
        print(f"Error during upload: {e}")
        print(f"Data saved locally as {csv_file}")

if __name__ == "__main__":
    upload_to_google_sheets()