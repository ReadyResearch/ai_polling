"""HTML extraction using BeautifulSoup and Google Gemini."""

import json
import hashlib
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import ValidationError

from .base_extractor import BaseExtractor
from ..core.models import PollingQuestion, CategoryEnum
from ..core.config import get_config
from ..core.exceptions import (
    APIError, APIRateLimitError, APIAuthenticationError,
    DocumentParsingError, ValidationError as AIPollingValidationError
)
from ..core.logger import get_logger


class HTMLExtractor(BaseExtractor):
    """Extract polling data from HTML files using Google Gemini."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize HTML extractor.
        
        Args:
            cache_dir: Directory for caching extracted data
        """
        config = get_config()
        
        if cache_dir is None:
            cache_dir = Path(config.output.cache_dir)
        
        super().__init__(cache_dir)
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=config.api.google_api_key)
        self.config = config
        self.logger = get_logger(__name__)
        
        # System prompt for Gemini
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with current category keywords."""
        categories = self.config.categories
        
        return f"""You are an expert at extracting polling data from HTML survey reports. Extract individual polling questions and their results.

CRITICAL: Your response must be ONLY a valid JSON array. No markdown formatting, no explanations, no additional text.

Extract binary questions (Yes/No, Agree/Disagree) and Likert scale questions (3-7 point scales).
Skip multi-select, ranking, or open-ended questions.

Return a JSON array where each object has these exact fields:
{{
  "question_text": "exact question wording",
  "response_scale": "exact response options", 
  "category": "AI_Regulation|AI_Risk_Concern|AI_Sentiment|Job_Displacement|Extinction_Risk|AI_Knowledge|Other",
  "agreement": number,
  "neutral": number,
  "disagreement": number,
  "non_response": number_or_null,
  "n_respondents": number,
  "country": "country name",
  "survey_organisation": "organization name", 
  "fieldwork_date": "YYYY-MM-DD or YYYY-MM or YYYY",
  "notes": "methodology details"
}}

CATEGORIZATION RULES:
- AI_Regulation: Questions about {', '.join(categories.ai_regulation_keywords)}
- AI_Risk_Concern: Questions about {', '.join(categories.ai_risk_keywords)}  
- Extinction_Risk: Questions about {', '.join(categories.extinction_risk_keywords)}
- Job_Displacement: Questions about {', '.join(categories.job_displacement_keywords)}
- AI_Sentiment: General feelings/attitudes about AI
- AI_Knowledge: Questions about AI knowledge/familiarity
- Other: AI-related questions not fitting above categories

IMPORTANT:
- Calculate Agreement/Neutral/Disagreement by combining appropriate response percentages
- Include non_response for "Don't know", "No answer", "Prefer not to say", etc. (use null if not available)
- For multi-country surveys, create separate records per country
- Extract from tables and charts carefully
- It's OK if percentages don't sum to exactly 100% - capture what's available
- Return ONLY the JSON array, nothing else"""
    
    def can_handle_file(self, file_path: Path) -> bool:
        """Check if file is an HTML file."""
        return file_path.suffix.lower() in ['.html', '.htm']
    
    def can_handle_url(self, url: str) -> bool:
        """Check if URL points to HTML content."""
        try:
            response = requests.head(url, timeout=10)
            content_type = response.headers.get('content-type', '').lower()
            return 'text/html' in content_type
        except Exception:
            return False
    
    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key based on file content and config."""
        stat = file_path.stat()
        content_hash = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        config_hash = hashlib.md5(self.system_prompt.encode()).hexdigest()[:8]
        return hashlib.md5(f"{content_hash}_{config_hash}".encode()).hexdigest()
    
    def _get_url_cache_key(self, url: str) -> str:
        """Generate cache key for URL-based content."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        config_hash = hashlib.md5(self.system_prompt.encode()).hexdigest()[:8]
        return hashlib.md5(f"{url_hash}_{config_hash}".encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Load cached extraction results."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # Remove corrupted cache file
                cache_file.unlink(missing_ok=True)
        return None
    
    def _save_to_cache(self, cache_key: str, data: List[Dict[str, Any]]) -> None:
        """Save extraction results to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self.logger.warning(f"Failed to save cache: {e}")
    
    def _clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and extract relevant text."""
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text from specific elements that are likely to contain survey data
            content_selectors = [
                'main', 'article', 'section', '.content', '.main-content',
                '.survey-results', '.poll-results', '.data', '.findings',
                'table', '.methodology', '.results'
            ]
            
            extracted_content = []
            
            # Try to find content with specific selectors
            for selector in content_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) > 100:  # Only include substantial content
                        extracted_content.append(text)
            
            # If no specific content found, get all text
            if not extracted_content:
                extracted_content = [soup.get_text(strip=True)]
            
            # Join all content
            clean_text = '\n\n'.join(extracted_content)
            
            # Clean up whitespace
            clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
            clean_text = re.sub(r' +', ' ', clean_text)
            
            return clean_text
            
        except Exception as e:
            self.logger.warning(f"Failed to clean HTML content: {e}")
            # Fallback: return raw HTML
            return html_content
    
    def _clean_json_response(self, response_text: str) -> str:
        """Clean JSON response from Gemini, handling partial responses."""
        # Remove invalid control characters more aggressively
        import re
        
        # Remove all control characters except newlines and tabs
        response_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', response_text)
        
        # Also remove any remaining problematic Unicode characters
        response_text = response_text.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Remove markdown formatting
        if "```json" in response_text:
            pattern = r'```json\s*(.*?)\s*```'
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        
        # Find JSON boundaries
        first_bracket = min(
            response_text.find('[') if '[' in response_text else len(response_text),
            response_text.find('{') if '{' in response_text else len(response_text)
        )
        
        if first_bracket < len(response_text):
            response_text = response_text[first_bracket:]
        
        # Handle potential truncated responses
        if response_text.startswith('['):
            # For arrays, ensure proper closing
            last_bracket = response_text.rfind(']')
            if last_bracket < 0:
                # Response is truncated, try to find last complete object
                last_complete_brace = response_text.rfind('}')
                if last_complete_brace > 0:
                    response_text = response_text[:last_complete_brace + 1] + '\n]'
                else:
                    response_text = response_text + ']'
            else:
                response_text = response_text[:last_bracket + 1]
        else:
            # For objects
            last_bracket = response_text.rfind('}')
            if last_bracket >= 0:
                response_text = response_text[:last_bracket + 1]
        
        return response_text.strip()
    
    def _attempt_json_repair(self, broken_json: str) -> Optional[List[Dict[str, Any]]]:
        """Attempt to repair broken JSON by extracting valid objects."""
        try:
            objects = []
            
            # Split by object boundaries and try to parse each
            parts = broken_json.split('},{')
            
            for i, part in enumerate(parts):
                # Reconstruct object boundaries
                if i == 0:
                    test_json = part
                    if not test_json.strip().startswith('['):
                        test_json = '[' + test_json
                    if not test_json.strip().endswith('}'):
                        test_json = test_json + '}'
                elif i == len(parts) - 1:
                    test_json = '{' + part
                    if not test_json.strip().endswith(']'):
                        test_json = test_json.rstrip(']').rstrip('}') + '}]'
                else:
                    test_json = '{' + part + '}'
                
                # Try to extract just the object part
                try:
                    if test_json.strip().startswith('[') and test_json.strip().endswith(']'):
                        parsed = json.loads(test_json)
                        if isinstance(parsed, list):
                            objects.extend(parsed)
                    else:
                        obj_start = test_json.find('{')
                        obj_end = test_json.rfind('}')
                        if obj_start >= 0 and obj_end > obj_start:
                            obj_json = test_json[obj_start:obj_end + 1]
                            parsed = json.loads(obj_json)
                            if isinstance(parsed, dict):
                                objects.append(parsed)
                except (json.JSONDecodeError, ValueError):
                    continue
            
            return objects if objects else None
            
        except Exception:
            return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10)
    )
    def _call_gemini_api(self, html_content: str) -> str:
        """Call Gemini API with HTML content."""
        try:
            # Clean the HTML content first
            clean_content = self._clean_html_content(html_content)
            
            # Truncate if too long (Gemini has input limits)
            max_input_chars = 1000000  # ~1M characters
            if len(clean_content) > max_input_chars:
                clean_content = clean_content[:max_input_chars] + "\n... [Content truncated]"
            
            response = self.client.models.generate_content(
                model=self.config.api.model_name,
                contents=[
                    "Extract all polling questions about AI, technology, or automation from this HTML document:",
                    clean_content
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    response_mime_type='application/json',
                    temperature=self.config.extraction.temperature,
                    max_output_tokens=self.config.extraction.max_output_tokens,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=self.config.api.thinking_budget
                    )
                )
            )
            
            if not response:
                raise APIError("No response received from API")
            
            # Check for blocking
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                    raise APIError(f"Request blocked: {response.prompt_feedback.block_reason}")
            
            # Get response text
            try:
                response_text = response.text
                if not response_text or response_text.strip() == "":
                    raise APIError("Empty response from API")
                return response_text
            except Exception as e:
                raise APIError(f"Error accessing response text: {e}")
                
        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "quota" in error_msg:
                raise APIRateLimitError(f"Rate limit exceeded: {e}")
            elif "auth" in error_msg or "key" in error_msg:
                raise APIAuthenticationError(f"Authentication failed: {e}")
            else:
                raise APIError(f"API call failed: {e}")
    
    def _validate_and_convert_data(self, raw_data: List[Dict[str, Any]], source_name: str) -> List[PollingQuestion]:
        """Validate raw data and convert to PollingQuestion objects."""
        validated_questions = []
        validation_errors = []
        invalid_records = []
        
        for i, item in enumerate(raw_data):
            try:
                # Clean and validate survey organization
                if 'survey_organisation' in item:
                    org = item['survey_organisation']
                    if not org or str(org).strip() == '' or str(org).lower() in ['unknown', 'na', 'n/a']:
                        # Try to infer from source file name or set default
                        if source_name:
                            # Extract organization from filename
                            filename_parts = Path(source_name).stem.replace('_', ' ').replace('-', ' ').split()
                            if filename_parts:
                                item['survey_organisation'] = ' '.join(filename_parts[:2]).title()
                            else:
                                item['survey_organisation'] = "Unknown Organization"
                        else:
                            item['survey_organisation'] = "Unknown Organization"
                
                # Ensure category is valid
                if 'category' in item:
                    category_str = item['category']
                    try:
                        CategoryEnum(category_str)
                    except ValueError:
                        # Map common variations
                        category_mapping = {
                            'ai_regulation': CategoryEnum.AI_REGULATION,
                            'regulation': CategoryEnum.AI_REGULATION,
                            'ai_risk': CategoryEnum.AI_RISK_CONCERN,
                            'risk': CategoryEnum.AI_RISK_CONCERN,
                            'sentiment': CategoryEnum.AI_SENTIMENT,
                            'jobs': CategoryEnum.JOB_DISPLACEMENT,
                            'extinction': CategoryEnum.EXTINCTION_RISK,
                            'knowledge': CategoryEnum.AI_KNOWLEDGE,
                        }
                        
                        normalized_category = category_str.lower().replace(' ', '_')
                        if normalized_category in category_mapping:
                            item['category'] = category_mapping[normalized_category]
                        else:
                            item['category'] = CategoryEnum.OTHER
                
                # Create PollingQuestion object
                question = PollingQuestion(**item)
                question.source_file = source_name
                validated_questions.append(question)
                
            except ValidationError as e:
                error_msg = f"Record {i+1}: {e}"
                validation_errors.append(error_msg)
                
                invalid_records.append({
                    'record_number': i + 1,
                    'error': str(e),
                    'raw_data': item,
                    'error_type': 'ValidationError'
                })
                continue
            except Exception as e:
                error_msg = f"Record {i+1}: Unexpected error: {e}"
                validation_errors.append(error_msg)
                
                invalid_records.append({
                    'record_number': i + 1,
                    'error': str(e),
                    'raw_data': item,
                    'error_type': 'UnexpectedError'
                })
                continue
        
        # Log validation results and save diagnostics
        if validation_errors:
            self.logger.warning(
                f"Validation issues in {source_name}: "
                f"{len(validated_questions)}/{len(raw_data)} records valid"
            )
            for error in validation_errors[:5]:  # Log first 5 errors
                self.logger.debug(f"  {error}")
            
            # Save diagnostic file
            if invalid_records:
                safe_name = re.sub(r'[^\w\-_\.]', '_', source_name)
                diagnostic_file = self.cache_dir / f"validation_issues_{safe_name}.json"
                try:
                    with open(diagnostic_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'source': source_name,
                            'total_extracted': len(raw_data),
                            'valid_records': len(validated_questions),
                            'invalid_records': len(invalid_records),
                            'validation_errors': validation_errors,
                            'invalid_data': invalid_records
                        }, f, indent=2, ensure_ascii=False, default=str)
                    
                    self.logger.info(f"📋 Saved validation diagnostics to {diagnostic_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to save diagnostic file: {e}")
        
        if not validated_questions:
            raise AIPollingValidationError(
                f"No valid records found in {source_name}. Validation errors: {validation_errors[:3]}"
            )
        
        return validated_questions
    
    def extract_from_file(self, file_path: Path) -> List[PollingQuestion]:
        """Extract polling questions from an HTML file."""
        if not self.can_handle_file(file_path):
            raise DocumentParsingError(f"Cannot handle file type: {file_path.suffix}")
        
        # Check cache first
        cache_key = self._get_cache_key(file_path)
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data is not None:
            self.logger.debug(f"📦 Using cached data for {file_path.name}")
            return self._validate_and_convert_data(cached_data, file_path.name)
        
        self.logger.info(f"🌐 Processing HTML: {file_path.name}")
        
        try:
            # Read HTML file
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Call Gemini API
            response_text = self._call_gemini_api(html_content)
            
            # Parse JSON response
            try:
                cleaned_text = self._clean_json_response(response_text)
                raw_data = json.loads(cleaned_text)
                
                if not isinstance(raw_data, list):
                    raise DocumentParsingError("API response is not a JSON array")
                
            except json.JSONDecodeError as e:
                # Try JSON repair
                self.logger.warning(f"Initial JSON parse failed for {file_path.name}: {e}")
                
                repaired_data = self._attempt_json_repair(cleaned_text)
                if repaired_data:
                    self.logger.info(f"✅ Recovered partial data from {file_path.name}: {len(repaired_data)} questions")
                    raw_data = repaired_data
                else:
                    # Save problematic response for debugging
                    debug_file = self.cache_dir / f"debug_html_{cache_key}.txt"
                    with open(debug_file, 'w') as f:
                        f.write(f"File: {file_path.name}\n")
                        f.write(f"Error: {e}\n")
                        f.write(f"Cleaned response:\n{cleaned_text}\n")
                        f.write(f"Original response:\n{response_text}\n")
                    
                    raise DocumentParsingError(f"Failed to parse JSON response: {e}")
            
            # Validate and convert data
            validated_questions = self._validate_and_convert_data(raw_data, file_path.name)
            
            # Cache successful results
            self._save_to_cache(cache_key, raw_data)
            
            self.logger.info(f"✅ Extracted {len(validated_questions)} records from {file_path.name}")
            return validated_questions
            
        except (APIError, DocumentParsingError, AIPollingValidationError):
            raise
        except Exception as e:
            raise DocumentParsingError(f"Unexpected error processing {file_path.name}: {e}")
    
    def extract_from_url(self, url: str) -> List[PollingQuestion]:
        """Extract polling questions from a URL."""
        if not self.can_handle_url(url):
            raise DocumentParsingError(f"Cannot handle URL content type: {url}")
        
        # Check cache first
        cache_key = self._get_url_cache_key(url)
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data is not None:
            self.logger.debug(f"📦 Using cached data for {url}")
            return self._validate_and_convert_data(cached_data, url)
        
        self.logger.info(f"🌐 Processing URL: {url}")
        
        try:
            # Fetch HTML content
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            # Call Gemini API
            response_text = self._call_gemini_api(html_content)
            
            # Parse JSON response (same logic as file extraction)
            try:
                cleaned_text = self._clean_json_response(response_text)
                raw_data = json.loads(cleaned_text)
                
                if not isinstance(raw_data, list):
                    raise DocumentParsingError("API response is not a JSON array")
                
            except json.JSONDecodeError as e:
                # Try JSON repair
                self.logger.warning(f"Initial JSON parse failed for {url}: {e}")
                
                repaired_data = self._attempt_json_repair(cleaned_text)
                if repaired_data:
                    self.logger.info(f"✅ Recovered partial data from {url}: {len(repaired_data)} questions")
                    raw_data = repaired_data
                else:
                    # Save problematic response for debugging
                    debug_file = self.cache_dir / f"debug_url_{cache_key}.txt"
                    with open(debug_file, 'w') as f:
                        f.write(f"URL: {url}\n")
                        f.write(f"Error: {e}\n")
                        f.write(f"Cleaned response:\n{cleaned_text}\n")
                        f.write(f"Original response:\n{response_text}\n")
                    
                    raise DocumentParsingError(f"Failed to parse JSON response: {e}")
            
            # Validate and convert data
            validated_questions = self._validate_and_convert_data(raw_data, url)
            
            # Cache successful results
            self._save_to_cache(cache_key, raw_data)
            
            self.logger.info(f"✅ Extracted {len(validated_questions)} records from {url}")
            return validated_questions
            
        except requests.RequestException as e:
            raise DocumentParsingError(f"Failed to fetch URL {url}: {e}")
        except (APIError, DocumentParsingError, AIPollingValidationError):
            raise
        except Exception as e:
            raise DocumentParsingError(f"Unexpected error processing {url}: {e}")