"""Metadata enrichment using Google Sheets poll database."""

import re
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Any
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from ..core.models import PollingQuestion
from ..core.config import get_config
from ..core.logger import get_logger
from ..core.exceptions import AIPollingError


class MetadataEnricher:
    """Enrich extracted polling questions with metadata from Google Sheets."""
    
    def __init__(self, sheet_id: Optional[str] = None):
        """Initialize metadata enricher.
        
        Args:
            sheet_id: Google Sheets ID containing poll metadata
        """
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.sheet_id = sheet_id or self.config.output.google_sheet_id
        
        # Initialize Google Sheets client
        self._setup_sheets_client()
        
        # Cache for metadata
        self._metadata_cache: Optional[pd.DataFrame] = None
    
    def _setup_sheets_client(self):
        """Setup Google Sheets client with authentication."""
        try:
            # Try service account authentication first
            service_account_path = Path.home() / ".config/gspread/service_account.json"
            if service_account_path.exists():
                self.logger.info("🔑 Using service account authentication")
                creds = Credentials.from_service_account_file(
                    str(service_account_path),
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly'
                    ]
                )
                self.gc = gspread.authorize(creds)
                self.logger.info("✅ Connected to Google Sheets via service account")
                return
            
            # Try config-specified service account path
            if hasattr(self.config.output, 'service_account_path') and self.config.output.service_account_path:
                service_account_path = Path(self.config.output.service_account_path)
                if service_account_path.exists():
                    self.logger.info("🔑 Using config-specified service account")
                    creds = Credentials.from_service_account_file(
                        str(service_account_path),
                        scopes=[
                            'https://www.googleapis.com/auth/spreadsheets.readonly',
                            'https://www.googleapis.com/auth/drive.readonly'
                        ]
                    )
                    self.gc = gspread.authorize(creds)
                    self.logger.info("✅ Connected to Google Sheets via config service account")
                    return
            
            # Fallback to OAuth (only if no service account found)
            oauth_creds_path = Path.home() / ".config/gspread/credentials.json"
            if oauth_creds_path.exists():
                self.logger.info("🔑 Using OAuth authentication")
                self.gc = gspread.oauth()
                self.logger.info("✅ Connected to Google Sheets via OAuth")
                return
            
            # No authentication available
            raise Exception("No authentication method available. Set up service account or OAuth credentials.")
            
        except Exception as e:
            self.logger.warning(f"Failed to setup Google Sheets client: {e}")
            self.gc = None
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats from spreadsheet."""
        if not date_str or pd.isna(date_str):
            return None
        
        date_str = str(date_str).strip()
        if not date_str:
            return None
        
        # Common date formats to try
        formats = [
            "%Y-%m-%d",           # 2023-04-15
            "%d %B %Y",           # 25 October 2024
            "%B %d, %Y",          # October 25, 2024
            "%b %d, %Y",          # Oct 25, 2024
            "%d/%m/%Y",           # 25/10/2024
            "%m/%d/%Y",           # 10/25/2024
            "%Y-%m",              # 2023-04
            "%B %Y",              # October 2024
            "%b %Y",              # Oct 2024
            "%Y",                 # 2024
        ]
        
        # Handle date ranges (take the start date)
        if " until " in date_str:
            date_str = date_str.split(" until ")[0].strip()
        elif " to " in date_str:
            date_str = date_str.split(" to ")[0].strip()
        elif " - " in date_str:
            date_str = date_str.split(" - ")[0].strip()
        
        # Handle month abbreviations
        month_mapping = {
            'Jan.': 'Jan', 'Feb.': 'Feb', 'Mar.': 'Mar', 'Apr.': 'Apr',
            'May.': 'May', 'Jun.': 'Jun', 'Jul.': 'Jul', 'Aug.': 'Aug',
            'Sep.': 'Sep', 'Oct.': 'Oct', 'Nov.': 'Nov', 'Dec.': 'Dec'
        }
        
        for abbrev, full in month_mapping.items():
            date_str = date_str.replace(abbrev, full)
        
        # Try parsing with different formats
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                return parsed_date
            except ValueError:
                continue
        
        # Try extracting year and month if possible
        year_match = re.search(r'\b(20\d{2})\b', date_str)
        month_match = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', date_str, re.IGNORECASE)
        
        if year_match:
            year = int(year_match.group(1))
            if month_match:
                month_str = month_match.group(1).capitalize()
                try:
                    month_date = datetime.strptime(f"{month_str} {year}", "%b %Y").date()
                    return month_date
                except ValueError:
                    pass
            
            # Just year
            try:
                return datetime(year, 1, 1).date()
            except ValueError:
                pass
        
        self.logger.debug(f"Could not parse date: '{date_str}'")
        return None
    
    def _normalize_filename(self, filename: str) -> str:
        """Normalize filename for matching."""
        if not filename:
            return ""
        
        # Remove extension
        name = Path(filename).stem
        
        # Convert to lowercase
        name = name.lower()
        
        # Replace underscores and hyphens with spaces
        name = re.sub(r'[_-]', ' ', name)
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _normalize_organization(self, org_name: str) -> str:
        """Normalize organization name for matching."""
        if not org_name:
            return ""
        
        # Convert to lowercase
        name = org_name.lower()
        
        # Remove common suffixes/prefixes
        name = re.sub(r'\b(inc|corp|corporation|company|institute|university|research|center|centre|poll|polls|polling)\b', '', name)
        
        # Remove punctuation
        name = re.sub(r'[^\w\s]', ' ', name)
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _load_metadata_from_sheets(self) -> pd.DataFrame:
        """Load metadata from Google Sheets."""
        if not self.gc:
            raise AIPollingError("Google Sheets client not initialized")
        
        try:
            # Open the spreadsheet
            sheet = self.gc.open_by_key(self.sheet_id)
            
            # Get the first worksheet (assumes metadata is in first sheet)
            worksheet = sheet.get_worksheet(0)
            
            # Get all records
            records = worksheet.get_all_records()
            
            if not records:
                raise AIPollingError("No data found in spreadsheet")
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            
            self.logger.info(f"📊 Loaded {len(df)} poll entries from Google Sheets")
            return df
            
        except Exception as e:
            raise AIPollingError(f"Failed to load metadata from Google Sheets: {e}")
    
    def _load_metadata_from_csv(self, csv_path: Path) -> pd.DataFrame:
        """Load metadata from CSV file as fallback."""
        try:
            df = pd.read_csv(csv_path)
            self.logger.info(f"📊 Loaded {len(df)} poll entries from CSV: {csv_path}")
            return df
        except Exception as e:
            raise AIPollingError(f"Failed to load metadata from CSV: {e}")
    
    def load_metadata(self, csv_fallback: Optional[Path] = None) -> pd.DataFrame:
        """Load poll metadata from Google Sheets or CSV fallback."""
        try:
            # Try Google Sheets first
            if self.gc and self.sheet_id:
                df = self._load_metadata_from_sheets()
                self._metadata_cache = df
                return df
        except Exception as e:
            self.logger.warning(f"Failed to load from Google Sheets: {e}")
        
        # Try CSV fallback
        if csv_fallback and csv_fallback.exists():
            df = self._load_metadata_from_csv(csv_fallback)
            self._metadata_cache = df
            return df
        
        raise AIPollingError("Could not load metadata from Google Sheets or CSV fallback")
    
    def _find_matching_poll(self, question: PollingQuestion, metadata_df: pd.DataFrame) -> Optional[pd.Series]:
        """Find matching poll entry for a question."""
        if question.source_file is None:
            return None
        
        source_normalized = self._normalize_filename(question.source_file)
        org_normalized = self._normalize_organization(question.survey_organisation)
        
        # Try multiple matching strategies
        for _, row in metadata_df.iterrows():
            
            # Strategy 1: Exact filename match (removing extensions)
            if 'PDF' in row and row['PDF']:
                pdf_normalized = self._normalize_filename(str(row['PDF']))
                if pdf_normalized and pdf_normalized == source_normalized:
                    return row
            
            # Strategy 2: Pollster name match
            if 'Pollster' in row and row['Pollster']:
                pollster_normalized = self._normalize_organization(str(row['Pollster']))
                if pollster_normalized and org_normalized and pollster_normalized in org_normalized:
                    return row
            
            # Strategy 3: Poll name contains source filename parts
            if 'Poll Name' in row and row['Poll Name']:
                poll_name_normalized = self._normalize_filename(str(row['Poll Name']))
                # Check if significant parts of the filename appear in poll name
                source_parts = source_normalized.split()
                poll_parts = poll_name_normalized.split()
                
                if len(source_parts) >= 2:
                    # Check if at least 2 significant words match
                    matches = sum(1 for part in source_parts if len(part) > 3 and part in poll_parts)
                    if matches >= 2:
                        return row
        
        return None
    
    def enrich_questions(
        self, 
        questions: List[PollingQuestion], 
        metadata_df: Optional[pd.DataFrame] = None,
        csv_fallback: Optional[Path] = None
    ) -> List[PollingQuestion]:
        """Enrich questions with metadata from spreadsheet.
        
        Args:
            questions: List of questions to enrich
            metadata_df: Pre-loaded metadata DataFrame (optional)
            csv_fallback: CSV file to use if Google Sheets fails
            
        Returns:
            List of enriched questions
        """
        # Load metadata if not provided
        if metadata_df is None:
            if self._metadata_cache is not None:
                metadata_df = self._metadata_cache
            else:
                metadata_df = self.load_metadata(csv_fallback)
        
        enriched_questions = []
        matches_found = 0
        
        for question in questions:
            enriched_question = question.model_copy()
            
            # Find matching poll entry
            matching_poll = self._find_matching_poll(question, metadata_df)
            
            if matching_poll is not None:
                matches_found += 1
                
                # Enrich fieldwork date if missing
                if not enriched_question.fieldwork_date and 'Fieldwork Date (Raw)' in matching_poll:
                    parsed_date = self._parse_date(str(matching_poll['Fieldwork Date (Raw)']))
                    if parsed_date:
                        # Use object.__setattr__ to avoid validation recursion
                        object.__setattr__(enriched_question, 'fieldwork_date', parsed_date)
                
                # Enrich sample size if missing
                if not enriched_question.n_respondents and 'Sample Size' in matching_poll:
                    try:
                        sample_size = matching_poll['Sample Size']
                        if sample_size and not pd.isna(sample_size):
                            sample_size_int = int(float(str(sample_size).replace(',', '')))
                            if sample_size_int > 0:
                                object.__setattr__(enriched_question, 'n_respondents', sample_size_int)
                    except (ValueError, TypeError):
                        pass
                
                # Enrich country if missing or generic
                if (not enriched_question.country or 
                    enriched_question.country.lower() in ['unknown', 'global', 'international']) and 'Country/Region' in matching_poll:
                    country = str(matching_poll['Country/Region']).strip()
                    if country and not pd.isna(country):
                        object.__setattr__(enriched_question, 'country', country)
                
                # Add methodology notes if missing
                if not enriched_question.notes and 'Methodology Notes' in matching_poll:
                    notes = str(matching_poll['Methodology Notes']).strip()
                    if notes and not pd.isna(notes) and notes.lower() != 'nan':
                        object.__setattr__(enriched_question, 'notes', notes)
                
                # Update survey organization with more complete name if available
                if 'Poll Name' in matching_poll:
                    poll_name = str(matching_poll['Poll Name']).strip()
                    if poll_name and not pd.isna(poll_name):
                        # Keep the original but add poll name context if useful
                        if len(poll_name) > len(enriched_question.survey_organisation):
                            object.__setattr__(enriched_question, 'survey_organisation', poll_name)
            
            enriched_questions.append(enriched_question)
        
        self.logger.info(f"✅ Enriched {matches_found}/{len(questions)} questions with metadata")
        
        if matches_found < len(questions) * 0.5:  # Less than 50% matched
            self.logger.warning(
                f"⚠️ Low match rate: {matches_found}/{len(questions)} questions matched. "
                "Consider checking filename patterns or poll names in spreadsheet."
            )
        
        return enriched_questions
    
    def get_enrichment_summary(self, original_questions: List[PollingQuestion], enriched_questions: List[PollingQuestion]) -> Dict[str, Any]:
        """Generate summary of enrichment results."""
        
        def count_missing(questions: List[PollingQuestion], field: str) -> int:
            return sum(1 for q in questions if getattr(q, field) is None)
        
        original_missing_dates = count_missing(original_questions, 'fieldwork_date')
        enriched_missing_dates = count_missing(enriched_questions, 'fieldwork_date')
        
        original_missing_samples = count_missing(original_questions, 'n_respondents')
        enriched_missing_samples = count_missing(enriched_questions, 'n_respondents')
        
        return {
            'total_questions': len(original_questions),
            'fieldwork_dates_filled': original_missing_dates - enriched_missing_dates,
            'sample_sizes_filled': original_missing_samples - enriched_missing_samples,
            'remaining_missing_dates': enriched_missing_dates,
            'remaining_missing_samples': enriched_missing_samples,
            'enrichment_rate': 1 - (enriched_missing_dates + enriched_missing_samples) / (original_missing_dates + original_missing_samples) if (original_missing_dates + original_missing_samples) > 0 else 0
        }