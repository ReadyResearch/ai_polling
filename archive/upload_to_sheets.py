#!/usr/bin/env python3
"""Direct upload script to push data to Google Sheets Poll Results tab."""

import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path

def clean_data_for_sheets(data):
    """Clean data to make it Google Sheets compatible."""
    cleaned = []
    
    for item in data:
        clean_item = {}
        for key, value in item.items():
            if isinstance(value, list):
                # Convert lists to semicolon-separated strings
                clean_item[key] = '; '.join(str(v) for v in value) if value else ''
            elif value is None:
                # Convert None to empty string
                clean_item[key] = ''
            elif isinstance(value, float) and pd.isna(value):
                # Convert NaN to empty string
                clean_item[key] = ''
            else:
                clean_item[key] = value
        cleaned.append(clean_item)
    
    return cleaned

def upload_to_poll_results_tab():
    """Upload extracted data to the Poll Results tab."""
    
    print("🔍 Loading extracted data...")
    
    # Load the latest extracted data
    data_file = Path("extracted_data/polling_data_latest.json")
    if not data_file.exists():
        print("❌ No extracted data found. Run extraction first.")
        return
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    print(f"📊 Found {len(data)} questions to upload")
    
    # Clean data for Google Sheets
    cleaned_data = clean_data_for_sheets(data)
    
    # Convert to DataFrame
    df = pd.DataFrame(cleaned_data)
    
    # Reorder columns for better presentation
    column_order = [
        'question_text', 'category', 'survey_organisation', 'country',
        'fieldwork_date', 'agreement', 'neutral', 'disagreement', 'non_response',
        'n_respondents', 'response_scale', 'notes', 'source_file',
        'extraction_date', 'data_quality', 'quality_issues'
    ]
    
    # Only include columns that exist
    existing_columns = [col for col in column_order if col in df.columns]
    df = df[existing_columns]
    
    print("🔑 Connecting to Google Sheets...")
    
    # Connect to Google Sheets
    service_account_path = Path.home() / ".config/gspread/service_account.json"
    creds = Credentials.from_service_account_file(
        str(service_account_path),
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )
    
    gc = gspread.authorize(creds)
    
    # Open the spreadsheet
    sheet_id = "1FqAiXwrS3rvPfqOltxO5CTNxfdjFKMc6FLWFMw6UkcE"
    spreadsheet = gc.open_by_key(sheet_id)
    
    # Get or create the Poll Results worksheet
    try:
        worksheet = spreadsheet.worksheet("Poll Results")
        print("📄 Found existing 'Poll Results' tab")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="Poll Results", rows=1000, cols=20)
        print("📄 Created new 'Poll Results' tab")
    
    # Clear existing data
    worksheet.clear()
    
    print("📤 Uploading data to Google Sheets...")
    
    # Upload data
    # Convert DataFrame to list of lists for gspread
    values = [df.columns.tolist()] + df.values.tolist()
    
    # Convert any remaining problematic values
    clean_values = []
    for row in values:
        clean_row = []
        for cell in row:
            if pd.isna(cell):
                clean_row.append('')
            elif isinstance(cell, (list, dict)):
                clean_row.append(str(cell))
            else:
                clean_row.append(cell)
        clean_values.append(clean_row)
    
    # Upload in batches to avoid API limits
    batch_size = 1000
    for i in range(0, len(clean_values), batch_size):
        batch = clean_values[i:i+batch_size]
        start_row = i + 1
        end_row = start_row + len(batch) - 1
        
        range_name = f'A{start_row}:Z{end_row}'
        worksheet.update(range_name, batch)
        print(f"📊 Uploaded rows {start_row}-{end_row}")
    
    # Format the header row
    if len(clean_values) > 0:
        header_range = f'A1:Z1'
        worksheet.format(header_range, {
            "backgroundColor": {"red": 0.8, "green": 0.9, "blue": 1.0},
            "textFormat": {"bold": True}
        })
    
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid=1312672982"
    print(f"✅ Successfully uploaded {len(data)} questions to Poll Results tab!")
    print(f"🔗 View at: {sheet_url}")
    
    return sheet_url

if __name__ == "__main__":
    upload_to_poll_results_tab()