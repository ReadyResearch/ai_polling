#!/usr/bin/env python3

import os
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Installing google-genai package...")
    os.system("pip install google-genai")
    from google import genai
    from google.genai import types

class PDFPollingExtractor:
    def __init__(self, api_key: str, cache_dir: str = "pdf_cache"):
        """Initialize the PDF polling data extractor."""
        self.client = genai.Client(api_key=api_key)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # System prompt for data extraction
        self.system_prompt = """You are an expert at extracting polling data from survey reports and academic papers. Your task is to extract individual polling questions and their results from the provided document.

EXTRACTION CRITERIA:
- Extract only binary questions (Yes/No, Agree/Disagree) and Likert scale questions (3-point, 5-point, 7-point, etc.)
- Skip multi-select, checkbox, ranking, or open-ended questions
- Extract every qualifying question - do not make comparability judgments
- Focus on questions about AI, technology, automation, or related topics

OUTPUT FORMAT:
Return a JSON array where each object represents one question-country combination with these exact fields:

{
  "Question_Text": "Exact question wording from the survey",
  "Response_Scale": "Exact response options (e.g., 'Strongly agree, Somewhat agree, Neither, Somewhat disagree, Strongly disagree')",
  "Category": "One of: AI_Regulation, AI_Risk_Concern, AI_Sentiment, Job_Displacement, Extinction_Risk, Other",
  "Agreement": numeric_percentage_of_positive_responses,
  "Neutral": numeric_percentage_of_neutral_responses,
  "Disagreement": numeric_percentage_of_negative_responses,
  "N_Respondents": number_of_survey_respondents,
  "Country": "Country or region where survey was conducted",
  "Survey_Organisation": "Organization that conducted the survey",
  "Fieldwork_Date": "YYYY-MM-DD format if available, otherwise YYYY-MM or YYYY",
  "Notes": "Any methodological details, sample descriptions, or important caveats"
}

CATEGORIZATION GUIDE:
- AI_Regulation: Questions about AI governance, oversight, testing, safety standards, government regulation
- AI_Risk_Concern: Questions about AI risks, dangers, worries, potential harms
- AI_Sentiment: General feelings, attitudes, opinions about AI (positive/negative/excited/worried)
- Job_Displacement: Questions specifically about AI impact on jobs and employment
- Extinction_Risk: Questions about existential risks, human extinction, loss of control
- Other: Any AI-related questions that don't fit the above categories

IMPORTANT NOTES:
- For Agreement/Neutral/Disagreement: Calculate percentages by combining appropriate response options
- If a document covers multiple countries, create separate records for each country
- If sample sizes differ by question, use the specific N for each question
- Extract tables, charts, and graphs carefully - these often contain the key data
- If exact dates aren't provided, estimate based on context (e.g., "Spring 2023" = "2023-04")

Return only the JSON array, no additional text or explanation."""

    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key based on file path and modification time."""
        stat = os.stat(file_path)
        content = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Load extracted data from cache if available."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_to_cache(self, cache_key: str, data: List[Dict]) -> None:
        """Save extracted data to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def extract_from_pdf(self, pdf_path: str, max_retries: int = 2) -> List[Dict]:
        """Extract polling data from a PDF file."""
        
        # Check cache first
        cache_key = self._get_cache_key(pdf_path)
        cached_data = self._load_from_cache(cache_key)
        if cached_data is not None:
            print(f"✓ Using cached data for {Path(pdf_path).name}")
            return cached_data

        print(f"📄 Processing PDF: {Path(pdf_path).name}")
        
        for attempt in range(max_retries):
            try:
                # Read PDF file
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()

                # Create PDF part
                pdf_part = types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type='application/pdf'
                )

                # Generate content
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        "Extract all polling questions and their results from this survey document:",
                        pdf_part
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        response_mime_type='application/json',
                        temperature=0.1,
                        max_output_tokens=60000
                    )
                )

                # 1. Check for safety-related blocking first.
                if # In the try... block of the extract_from_pdf method...

# 1. Check for safety-related blocking first.
if response and response.prompt_feedback and response.prompt_feedback.block_reason:
                    print(f"✗ Request was blocked for {Path(pdf_path).name}. Reason: {response.prompt_feedback.block_reason.name}")
                    return []

                # 2. Safely access the response text.
                try:
                    response_text = response.text
                except ValueError:
                    # This error is raised by the library if no content is generated.
                    print(f"⚠ API returned no content for {Path(pdf_path).name}. It might be empty or a different issue.")
                    return []
                
                # 3. Now, parse the JSON.
                extracted_data = json.loads(response_text)
                
                # Validate that we got a list
                if not isinstance(extracted_data, list):
                    raise ValueError("Response is not a JSON array")

                # Cache the results
                self._save_to_cache(cache_key, extracted_data)
                
                print(f"✓ Extracted {len(extracted_data)} records from {Path(pdf_path).name}")
                return extracted_data

            except json.JSONDecodeError as e:
                print(f"⚠ JSON parsing error for {Path(pdf_path).name} (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    print(f"✗ Failed to parse JSON after {max_retries} attempts")
                    return []
                time.sleep(2)

            except Exception as e:
                print(f"⚠ An unexpected error occurred for {Path(pdf_path).name} (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    print(f"✗ Failed after {max_retries} attempts")
                    return []
                time.sleep(5)

        return []

    def process_directory(self, pdf_dir: str = "polling_pdfs") -> pd.DataFrame:
        """Process all PDF files in the specified directory."""
        
        pdf_dir_path = Path(pdf_dir)
        if not pdf_dir_path.exists():
            raise FileNotFoundError(f"Directory {pdf_dir} not found")

        # Find all PDF files
        pdf_files = list(pdf_dir_path.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {pdf_dir}")
            return pd.DataFrame()

        print(f"Found {len(pdf_files)} PDF files to process")
        
        all_extracted_data = []
        processed_count = 0
        
        for pdf_file in pdf_files:
            try:
                extracted_data = self.extract_from_pdf(str(pdf_file))
                all_extracted_data.extend(extracted_data)
                processed_count += 1
                
                # Rate limiting - be respectful to the API
                if processed_count % 5 == 0:
                    print(f"Processed {processed_count}/{len(pdf_files)} files... pausing briefly")
                    time.sleep(2)
                    
            except Exception as e:
                print(f"✗ Error processing {pdf_file.name}: {e}")
                continue

        # Convert to DataFrame
        if all_extracted_data:
            df = pd.DataFrame(all_extracted_data)
            
            # Clean and validate data
            df = self._clean_data(df)
            
            print(f"\n=== EXTRACTION COMPLETE ===")
            print(f"Total records extracted: {len(df)}")
            print(f"Organizations: {', '.join(df['Survey_Organisation'].unique())}")
            print(f"Countries: {len(df['Country'].unique())}")
            print(f"Categories: {', '.join(df['Category'].unique())}")
            
            return df
        else:
            print("No data extracted from any files")
            return pd.DataFrame()

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the extracted data."""
        
        # Convert date strings to datetime where possible
        def parse_date(date_str):
            if pd.isna(date_str) or date_str == "":
                return None
            try:
                # Try various date formats
                date_str = str(date_str).strip()
                if len(date_str) == 4:  # Just year
                    return pd.to_datetime(f"{date_str}-01-01")
                elif len(date_str) == 7:  # YYYY-MM
                    return pd.to_datetime(f"{date_str}-01")
                else:  # Full date
                    return pd.to_datetime(date_str)
            except:
                return None

        df['Fieldwork_Date'] = df['Fieldwork_Date'].apply(parse_date)
        
        # Ensure numeric columns are numeric
        numeric_cols = ['Agreement', 'Neutral', 'Disagreement', 'N_Respondents']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove rows with invalid data
        initial_count = len(df)
        df = df.dropna(subset=['Question_Text', 'Survey_Organisation'])
        df = df[df['Question_Text'].str.strip() != '']
        
        if len(df) < initial_count:
            print(f"Removed {initial_count - len(df)} invalid records")
        
        return df

    def save_results(self, df: pd.DataFrame, output_dir: str = "extracted_data") -> None:
        """Save results to various formats."""
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save as CSV
        csv_file = output_path / f"pdf_extracted_data_{timestamp}.csv"
        df.to_csv(csv_file, index=False)
        print(f"💾 Saved CSV: {csv_file}")
        
        # Save as JSON
        json_file = output_path / f"pdf_extracted_data_{timestamp}.json"
        df.to_json(json_file, orient='records', indent=2)
        print(f"💾 Saved JSON: {json_file}")
        
        # Save the latest as a standard name too
        latest_csv = output_path / "pdf_extracted_data_latest.csv"
        latest_json = output_path / "pdf_extracted_data_latest.json"
        
        df.to_csv(latest_csv, index=False)
        df.to_json(latest_json, orient='records', indent=2)
        
        print(f"💾 Saved latest: {latest_csv}")

def main():
    """Main execution function."""
    
    # Get API key from environment
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set")
        print("Please run: export GOOGLE_API_KEY='your-api-key'")
        return

    # Initialize extractor
    extractor = PDFPollingExtractor(api_key=api_key)
    
    # Process all PDFs
    try:
        df = extractor.process_directory("polling_pdfs")
        
        if not df.empty:
            # Save results
            extractor.save_results(df)
            
            # Print summary by category
            print(f"\n=== RECORDS BY CATEGORY ===")
            category_summary = df.groupby(['Category', 'Survey_Organisation']).size().reset_index(name='count')
            print(category_summary.to_string(index=False))
            
            # Show AI regulation specifically
            ai_reg = df[df['Category'] == 'AI_Regulation']
            print(f"\n=== AI_REGULATION SUMMARY ===")
            print(f"Total AI_Regulation records: {len(ai_reg)}")
            if len(ai_reg) > 0:
                print(f"Organizations with AI_Regulation questions: {', '.join(ai_reg['Survey_Organisation'].unique())}")
                print(f"Countries with AI_Regulation data: {', '.join(ai_reg['Country'].unique())}")
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        raise

if __name__ == "__main__":
    main()
