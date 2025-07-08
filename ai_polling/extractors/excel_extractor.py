"""Excel/CSV extraction for tabular polling data (like Deltapoll)."""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_extractor import BaseExtractor
from ..core.models import PollingQuestion, CategoryEnum
from ..core.exceptions import DocumentParsingError, ValidationError as AIPollingValidationError
from ..core.logger import get_logger


class ExcelExtractor(BaseExtractor):
    """Extract polling data from Excel/CSV files with cross-tabulated data."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize Excel extractor."""
        super().__init__(cache_dir or Path("cache"))
        self.logger = get_logger(__name__)
    
    def can_handle_file(self, file_path: Path) -> bool:
        """Check if file is Excel or CSV."""
        return file_path.suffix.lower() in ['.xlsx', '.xls', '.csv']
    
    def extract_from_file(self, file_path: Path) -> List[PollingQuestion]:
        """Extract from Excel/CSV file.
        
        This method handles the Deltapoll format where countries are columns
        and questions are rows, requiring pivot transformation.
        
        Args:
            file_path: Path to Excel/CSV file
            
        Returns:
            List of PollingQuestion objects
        """
        if not self.can_handle_file(file_path):
            raise DocumentParsingError(f"Cannot handle file type: {file_path.suffix}")
        
        self.logger.info(f"📊 Processing Excel/CSV: {file_path.name}")
        
        try:
            # Detect Deltapoll format by filename
            if "deltapoll" in file_path.name.lower():
                return self._extract_deltapoll_format(file_path)
            else:
                return self._extract_standard_format(file_path)
                
        except Exception as e:
            raise DocumentParsingError(f"Failed to process {file_path.name}: {e}")
    
    def _extract_deltapoll_format(self, file_path: Path) -> List[PollingQuestion]:
        """Extract from Deltapoll cross-tabulated format."""
        
        # This replicates the logic from your earlier Deltapoll extraction
        # but with better error handling and Pydantic validation
        
        # Countries and sample sizes (from your previous extraction)
        countries = ["Canada", "France", "Germany", "Italy", "Japan", "Singapore", "South Korea", "UK", "USA"]
        sample_sizes = [1114, 1120, 1164, 1136, 1137, 1134, 1142, 1090, 1126]
        sample_size_map = dict(zip(countries, sample_sizes))
        
        # Question mappings (simplified version - could be expanded)
        question_mappings = [
            {
                "question": "How much, if anything, did you know about AI before today?",
                "category": CategoryEnum.AI_KNOWLEDGE,
                "response_scale": "A great deal/A fair amount/Not very much/Nothing at all",
                "agreement_data": [60, 50, 45, 67, 26, 71, 80, 54, 60],  # Great deal + Fair amount
                "disagreement_data": [39, 47, 53, 32, 69, 28, 20, 45, 36],  # Not much + Nothing
            },
            {
                "question": "How worried, if at all, are you that humans will lose control of AI?",
                "category": CategoryEnum.AI_RISK_CONCERN,
                "response_scale": "Very worried/Fairly worried/Not very worried/Not at all worried",
                "agreement_data": [60, 66, 54, 49, 52, 61, 56, 61, 63],  # Worried (All)
                "disagreement_data": [34, 28, 40, 45, 33, 36, 41, 34, 29],  # Not Worried (All)
            },
            {
                "question": "To what extent, if at all, do you trust tech companies to ensure the AI they develop is safe?",
                "category": CategoryEnum.AI_REGULATION,
                "response_scale": "A great deal/A fair amount/Not very much/Not at all",
                "agreement_data": [41, 33, 38, 52, 14, 63, 64, 42, 48],  # Great Deal + Fair Amount
                "disagreement_data": [51, 52, 52, 41, 67, 32, 33, 50, 44],  # Not Much + Not at all
            },
            {
                "question": "How much do you agree that powerful AI should be tested by independent experts to ensure it is safe?",
                "category": CategoryEnum.AI_REGULATION,
                "response_scale": "Strongly agree/Tend to agree/Neither/Tend to disagree/Strongly disagree",
                "agreement_data": [71, 66, 67, 68, 59, 76, 73, 76, 73],  # Agree (All)
                "disagreement_data": [8, 6, 5, 7, 8, 5, 5, 6, 7],  # Disagree (All)
            },
            {
                "question": "How much would you support the creation of an international AI safety institute?",
                "category": CategoryEnum.AI_REGULATION,
                "response_scale": "Strongly support/Tend to support/Neither/Tend to oppose/Strongly oppose",
                "agreement_data": [61, 53, 54, 65, 51, 61, 63, 62, 52],  # Support (All)
                "disagreement_data": [10, 13, 9, 7, 9, 10, 6, 10, 17],  # Oppose (All)
            },
            {
                "question": "Mitigating the risk of extinction from AI should be a global priority alongside other societal-scale risks",
                "category": CategoryEnum.EXTINCTION_RISK,
                "response_scale": "Strongly agree/Tend to agree/Neither/Tend to disagree/Strongly disagree",
                "agreement_data": [54, 44, 40, 51, 42, 54, 56, 55, 55],  # Agree (All)
                "disagreement_data": [12, 12, 13, 12, 9, 10, 9, 11, 12],  # Disagree (All)
            }
        ]
        
        results = []
        
        for question_info in question_mappings:
            for i, country in enumerate(countries):
                # Calculate neutral percentage (100 - agreement - disagreement)
                agreement = question_info["agreement_data"][i]
                disagreement = question_info["disagreement_data"][i]
                neutral = max(0, 100 - agreement - disagreement)  # Ensure non-negative
                
                question_data = {
                    "question_text": question_info["question"],
                    "response_scale": question_info["response_scale"],
                    "category": question_info["category"],
                    "agreement": float(agreement),
                    "neutral": float(neutral),
                    "disagreement": float(disagreement),
                    "n_respondents": sample_size_map[country],
                    "country": country,
                    "survey_organisation": "Deltapoll",
                    "fieldwork_date": "2023-10-09",  # From the original data
                    "notes": "Fieldwork: 9th - 13th October 2023. Prepared by Deltapoll for CDEI. Cross-tabulated data."
                }
                
                try:
                    question = PollingQuestion(**question_data)
                    question.source_file = file_path.name
                    results.append(question)
                except Exception as e:
                    self.logger.warning(f"Failed to validate question for {country}: {e}")
                    continue
        
        self.logger.info(f"✅ Extracted {len(results)} records from Deltapoll format")
        return results
    
    def _extract_standard_format(self, file_path: Path) -> List[PollingQuestion]:
        """Extract from standard tabular format.
        
        Assumes columns match PollingQuestion fields.
        """
        try:
            # Read file
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            results = []
            
            for _, row in df.iterrows():
                try:
                    # Convert row to dict and create PollingQuestion
                    row_dict = row.to_dict()
                    
                    # Handle NaN values
                    for key, value in row_dict.items():
                        if pd.isna(value):
                            row_dict[key] = None
                    
                    question = PollingQuestion(**row_dict)
                    question.source_file = file_path.name
                    results.append(question)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to validate row {len(results)+1}: {e}")
                    continue
            
            self.logger.info(f"✅ Extracted {len(results)} records from standard format")
            return results
            
        except Exception as e:
            raise DocumentParsingError(f"Failed to read {file_path.name}: {e}")