#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Import our PDF extractor
sys.path.append('.')
from extract_polling_data_pdf import PDFPollingExtractor

def main():
    """Extract PDFs in small batches to avoid timeouts."""
    
    # Get API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set")
        return
    
    # Initialize extractor
    extractor = PDFPollingExtractor(api_key=api_key)
    
    # Find all PDFs
    pdf_dir = Path("polling_pdfs")
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    # Check which ones are already processed
    processed_files = []
    for pdf_file in pdf_files:
        cache_key = extractor._get_cache_key(str(pdf_file))
        cache_file = extractor.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            processed_files.append(pdf_file.name)
    
    remaining_files = [f for f in pdf_files if f.name not in processed_files]
    
    print(f"Total PDFs: {len(pdf_files)}")
    print(f"Already processed: {len(processed_files)}")
    print(f"Remaining: {len(remaining_files)}")
    
    if not remaining_files:
        print("All files already processed!")
        return
    
    # Process files in batches of 5
    batch_size = 5
    for i in range(0, len(remaining_files), batch_size):
        batch = remaining_files[i:i+batch_size]
        print(f"\n=== Processing batch {i//batch_size + 1}: {len(batch)} files ===")
        
        for pdf_file in batch:
            try:
                print(f"Processing: {pdf_file.name}")
                extracted_data = extractor.extract_from_pdf(str(pdf_file))
                print(f"✓ Extracted {len(extracted_data)} records from {pdf_file.name}")
            except Exception as e:
                print(f"✗ Error processing {pdf_file.name}: {e}")
                continue
        
        print(f"Completed batch {i//batch_size + 1}")
        
        # Check total progress
        total_processed = len([f for f in pdf_files if f.name in processed_files or f in batch])
        print(f"Progress: {total_processed}/{len(pdf_files)} files processed")

if __name__ == "__main__":
    main()