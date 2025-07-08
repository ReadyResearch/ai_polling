#!/usr/bin/env python3

import os
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
import re

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Installing google-genai package...")
    os.system("pip install google-genai")
    from google import genai
    from google.genai import types

class RobustPDFExtractor:
    def __init__(self, api_key: str, cache_dir: str = "pdf_cache"):
        """Initialize the robust PDF extractor."""
        self.client = genai.Client(api_key=api_key)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Enhanced system prompt with better JSON formatting instructions
        self.system_prompt = """You are an expert at extracting polling data from survey reports. Extract individual polling questions and their results.

CRITICAL: Your response must be ONLY a valid JSON array. No markdown formatting, no explanations, no additional text.

Extract binary questions (Yes/No, Agree/Disagree) and Likert scale questions (3-7 point scales).
Skip multi-select, ranking, or open-ended questions.

Return a JSON array where each object has these exact fields:
{
  "Question_Text": "exact question wording",
  "Response_Scale": "exact response options",
  "Category": "AI_Regulation|AI_Risk_Concern|AI_Sentiment|Job_Displacement|Extinction_Risk|Other",
  "Agreement": number,
  "Neutral": number, 
  "Disagreement": number,
  "N_Respondents": number,
  "Country": "country name",
  "Survey_Organisation": "organization name",
  "Fieldwork_Date": "YYYY-MM-DD or YYYY-MM or YYYY",
  "Notes": "methodology details"
}

CATEGORIZATION:
- AI_Regulation: governance, oversight, testing, safety standards, government regulation
- AI_Risk_Concern: risks, dangers, worries, potential harms
- AI_Sentiment: general feelings about AI
- Job_Displacement: AI impact on jobs/employment
- Extinction_Risk: existential risks, human extinction
- Other: AI-related questions not fitting above

IMPORTANT: 
- Calculate Agreement/Neutral/Disagreement by combining appropriate response percentages
- For multi-country surveys, create separate records per country
- Extract from tables and charts carefully
- Return ONLY the JSON array, nothing else"""

    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key based on file path and modification time."""
        stat = os.stat(file_path)
        content = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Load extracted data from cache if available."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

    def _save_to_cache(self, cache_key: str, data: List[Dict]) -> None:
        """Save extracted data to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _clean_json_response(self, response_text: str) -> str:
        """Clean and extract JSON from response text."""
        # Remove any markdown formatting
        if "```json" in response_text:
            # Extract content between ```json and ```
            pattern = r'```json\s*(.*?)\s*```'
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        
        # Remove any text before the first [ or {
        first_bracket = min(
            response_text.find('[') if '[' in response_text else len(response_text),
            response_text.find('{') if '{' in response_text else len(response_text)
        )
        if first_bracket < len(response_text):
            response_text = response_text[first_bracket:]
        
        # Remove any text after the last ] or }
        last_bracket = max(
            response_text.rfind(']'),
            response_text.rfind('}')
        )
        if last_bracket >= 0:
            response_text = response_text[:last_bracket + 1]
        
        return response_text.strip()

    def extract_from_pdf(self, pdf_path: str, max_retries: int = 3) -> List[Dict]:
        """Extract polling data from a PDF file with robust error handling."""
        
        # Check cache first
        cache_key = self._get_cache_key(pdf_path)
        cached_data = self._load_from_cache(cache_key)
        if cached_data is not None:
            print(f"✓ Using cached data for {Path(pdf_path).name} ({len(cached_data)} records)")
            return cached_data

        file_name = Path(pdf_path).name
        print(f"📄 Processing: {file_name}")
        
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

                # Generate content with enhanced configuration
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',  # Use stable model
                    contents=[
                        "Extract all polling questions about AI, technology, or automation from this document. Focus on questions with clear percentage results.",
                        pdf_part
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        response_mime_type='application/json',
                        temperature=0.0,  # Deterministic output
                        max_output_tokens=8192,
                        candidate_count=1
                    )
                )

                # Validate response
                if not response:
                    print(f"   ⚠ No response received (attempt {attempt + 1})")
                    if attempt == max_retries - 1:
                        return []
                    time.sleep(3)
                    continue

                # Check for blocking
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                        print(f"   ✗ Request blocked: {response.prompt_feedback.block_reason}")
                        return []

                # Get response text
                try:
                    response_text = response.text
                    if not response_text or response_text.strip() == "":
                        print(f"   ⚠ Empty response (attempt {attempt + 1})")
                        if attempt == max_retries - 1:
                            return []
                        time.sleep(3)
                        continue
                except Exception as e:
                    print(f"   ⚠ Error accessing response text (attempt {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        return []
                    time.sleep(3)
                    continue
                
                # Clean and parse JSON
                try:
                    cleaned_text = self._clean_json_response(response_text)
                    extracted_data = json.loads(cleaned_text)
                    
                    # Validate structure
                    if not isinstance(extracted_data, list):
                        print(f"   ⚠ Response not a list (attempt {attempt + 1})")
                        if attempt == max_retries - 1:
                            return []
                        time.sleep(2)
                        continue
                    
                    # Validate data quality
                    valid_records = []
                    for record in extracted_data:
                        if (isinstance(record, dict) and 
                            'Question_Text' in record and 
                            'Survey_Organisation' in record and
                            record.get('Question_Text', '').strip() != ''):
                            valid_records.append(record)
                    
                    if len(valid_records) == 0:
                        print(f"   ⚠ No valid records found (attempt {attempt + 1})")
                        if attempt == max_retries - 1:
                            return []
                        time.sleep(2)
                        continue
                    
                    # Cache successful results
                    self._save_to_cache(cache_key, valid_records)
                    print(f"   ✓ Extracted {len(valid_records)} records")
                    return valid_records

                except json.JSONDecodeError as e:
                    print(f"   ⚠ JSON error (attempt {attempt + 1}): {str(e)[:100]}...")
                    if attempt == max_retries - 1:
                        print(f"   ✗ Failed to parse JSON after {max_retries} attempts")
                        # Save the raw response for debugging
                        debug_file = self.cache_dir / f"debug_{cache_key}.txt"
                        with open(debug_file, 'w') as f:
                            f.write(f"File: {file_name}\n")
                            f.write(f"Attempt: {attempt + 1}\n")
                            f.write(f"Error: {e}\n")
                            f.write(f"Response:\n{response_text}\n")
                        return []
                    time.sleep(3)

            except Exception as e:
                print(f"   ⚠ Unexpected error (attempt {attempt + 1}): {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    print(f"   ✗ Failed after {max_retries} attempts")
                    return []
                time.sleep(5)

        return []

    def process_all_pdfs(self, pdf_dir: str = "polling_pdfs") -> pd.DataFrame:
        """Process all PDF files in the directory."""
        
        pdf_dir_path = Path(pdf_dir)
        if not pdf_dir_path.exists():
            raise FileNotFoundError(f"Directory {pdf_dir} not found")

        # Find all PDF files
        pdf_files = sorted(list(pdf_dir_path.glob("*.pdf")))
        
        if not pdf_files:
            print(f"No PDF files found in {pdf_dir}")
            return pd.DataFrame()

        print(f"\n=== PROCESSING ALL {len(pdf_files)} PDF FILES ===")
        
        all_data = []
        success_count = 0
        
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
            
            try:
                records = self.extract_from_pdf(str(pdf_file))
                if records:
                    all_data.extend(records)
                    success_count += 1
                    print(f"   📊 Total records so far: {len(all_data)}")
                else:
                    print(f"   ⚠ No records extracted")
                    
            except Exception as e:
                print(f"   ✗ Error: {e}")
            
            # Progress update and rate limiting
            if i % 5 == 0:
                print(f"\n🔄 Progress: {i}/{len(pdf_files)} files processed")
                print(f"📊 Success rate: {success_count}/{i} ({100*success_count/i:.1f}%)")
                print(f"📈 Total records: {len(all_data)}")
                time.sleep(2)  # Rate limiting

        # Create final dataset
        if all_data:
            df = pd.DataFrame(all_data)
            df = self._clean_dataframe(df)
            
            print(f"\n=== FINAL RESULTS ===")
            print(f"📊 Total records: {len(df)}")
            print(f"✅ Successful files: {success_count}/{len(pdf_files)}")
            print(f"🏢 Organizations: {len(df['Survey_Organisation'].unique())}")
            print(f"🌍 Countries: {len(df['Country'].unique())}")
            print(f"📂 Categories: {', '.join(df['Category'].unique())}")
            
            # Save comprehensive results
            self._save_results(df)
            
            return df
        else:
            print("❌ No data extracted from any files")
            return pd.DataFrame()

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the extracted dataframe."""
        
        print(f"🔧 Cleaning data...")
        initial_count = len(df)
        
        # Parse dates
        def parse_date(date_str):
            if pd.isna(date_str) or date_str == "":
                return None
            try:
                date_str = str(date_str).strip()
                if len(date_str) == 4:
                    return pd.to_datetime(f"{date_str}-01-01")
                elif len(date_str) == 7:
                    return pd.to_datetime(f"{date_str}-01")
                else:
                    return pd.to_datetime(date_str)
            except:
                return None

        df['Fieldwork_Date'] = df['Fieldwork_Date'].apply(parse_date)
        
        # Convert numeric columns
        numeric_cols = ['Agreement', 'Neutral', 'Disagreement', 'N_Respondents']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove invalid records
        df = df.dropna(subset=['Question_Text', 'Survey_Organisation'])
        df = df[df['Question_Text'].str.strip() != '']
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['Question_Text', 'Country', 'Survey_Organisation'], keep='first')
        
        if len(df) < initial_count:
            print(f"   🧹 Removed {initial_count - len(df)} invalid/duplicate records")
        
        return df

    def _save_results(self, df: pd.DataFrame) -> None:
        """Save comprehensive results."""
        
        output_dir = Path("extracted_data")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save timestamped files
        csv_file = output_dir / f"all_pdfs_extracted_{timestamp}.csv"
        json_file = output_dir / f"all_pdfs_extracted_{timestamp}.json"
        
        df.to_csv(csv_file, index=False)
        df.to_json(json_file, orient='records', indent=2)
        
        # Save as latest
        df.to_csv(output_dir / "all_pdfs_latest.csv", index=False)
        df.to_json(output_dir / "all_pdfs_latest.json", orient='records', indent=2)
        
        print(f"\n💾 Results saved:")
        print(f"   📄 {csv_file}")
        print(f"   📄 {json_file}")
        
        # Show summary by category
        print(f"\n📊 SUMMARY BY CATEGORY:")
        category_counts = df['Category'].value_counts()
        for category, count in category_counts.items():
            print(f"   {category}: {count} records")
        
        # Show AI regulation details
        ai_reg = df[df['Category'] == 'AI_Regulation']
        if len(ai_reg) > 0:
            print(f"\n🏛️ AI_REGULATION DETAILS:")
            print(f"   Total records: {len(ai_reg)}")
            org_counts = ai_reg['Survey_Organisation'].value_counts()
            for org, count in org_counts.items():
                print(f"   • {org}: {count} questions")

def main():
    """Main execution function."""
    
    # Get API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY environment variable not set")
        return

    print("🚀 Starting comprehensive PDF extraction...")
    print(f"🔑 API key length: {len(api_key)} characters")
    
    # Initialize extractor
    extractor = RobustPDFExtractor(api_key=api_key)
    
    # Process all PDFs
    try:
        df = extractor.process_all_pdfs("polling_pdfs")
        
        if not df.empty:
            print(f"\n🎉 Extraction completed successfully!")
            print(f"📊 Final dataset: {len(df)} records from {len(df['Survey_Organisation'].unique())} organizations")
        else:
            print(f"\n❌ No data extracted")
            
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        raise

if __name__ == "__main__":
    main()