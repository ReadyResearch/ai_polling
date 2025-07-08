"""Data validation and quality assessment."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import date, datetime

from ..core.models import PollingQuestion, PollingDataset
from ..core.exceptions import DataQualityError
from ..core.logger import get_logger


@dataclass
class DataQualityReport:
    """Report on data quality issues and statistics."""
    
    total_questions: int
    valid_questions: int
    invalid_questions: int
    
    # Quality issues
    missing_dates: int
    missing_sample_sizes: int
    invalid_percentages: int
    duplicate_questions: int
    
    # Quality metrics
    date_coverage: Dict[str, Any]
    organization_coverage: Dict[str, int]
    country_coverage: Dict[str, int]
    category_coverage: Dict[str, int]
    
    # Issues list for detailed inspection
    issues: List[str]
    
    @property
    def quality_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        if self.total_questions == 0:
            return 0.0
        
        # Base score from valid questions
        validity_score = (self.valid_questions / self.total_questions) * 100
        
        # Penalties for missing data
        date_penalty = (self.missing_dates / self.total_questions) * 10
        sample_penalty = (self.missing_sample_sizes / self.total_questions) * 5
        
        # Bonus for good coverage
        org_bonus = min(len(self.organization_coverage) * 2, 10)
        country_bonus = min(len(self.country_coverage) * 1, 10)
        
        score = validity_score - date_penalty - sample_penalty + org_bonus + country_bonus
        return max(0.0, min(100.0, score))


def validate_polling_data(questions: List[PollingQuestion]) -> DataQualityReport:
    """Validate a list of polling questions and generate quality report.
    
    Args:
        questions: List of PollingQuestion objects to validate
        
    Returns:
        DataQualityReport with validation results and quality metrics
    """
    logger = get_logger(__name__)
    logger.info(f"Validating {len(questions)} polling questions...")
    
    # Initialize counters
    valid_questions = 0
    invalid_questions = 0
    missing_dates = 0
    missing_sample_sizes = 0
    invalid_percentages = 0
    duplicate_questions = 0
    issues = []
    
    # Track coverage
    organizations = {}
    countries = {}
    categories = {}
    dates = []
    
    # Track duplicates
    seen_questions = set()
    
    for i, question in enumerate(questions):
        question_id = f"{question.question_text}_{question.country}_{question.survey_organisation}"
        
        # Check for duplicates
        if question_id in seen_questions:
            duplicate_questions += 1
            issues.append(f"Question {i+1}: Duplicate question detected")
        else:
            seen_questions.add(question_id)
        
        # Validate individual question
        try:
            # This will raise ValidationError if invalid
            question.dict()  # Triggers Pydantic validation
            valid_questions += 1
            
            # Track coverage
            organizations[question.survey_organisation] = organizations.get(question.survey_organisation, 0) + 1
            countries[question.country] = countries.get(question.country, 0) + 1
            # Handle both enum and string categories
            cat_key = question.category.value if hasattr(question.category, 'value') else str(question.category)
            categories[cat_key] = categories.get(cat_key, 0) + 1
            
            # Check for missing data
            if question.fieldwork_date is None:
                missing_dates += 1
                issues.append(f"Question {i+1}: Missing fieldwork date")
            else:
                dates.append(question.fieldwork_date)
            
            if question.n_respondents is None:
                missing_sample_sizes += 1
                issues.append(f"Question {i+1}: Missing sample size")
            
            # Check percentage validity
            if (question.agreement is not None and 
                question.neutral is not None and 
                question.disagreement is not None):
                total = question.agreement + question.neutral + question.disagreement
                if total < 95 or total > 105:  # Allow 5% tolerance
                    invalid_percentages += 1
                    issues.append(f"Question {i+1}: Percentages sum to {total:.1f}%")
            
        except Exception as e:
            invalid_questions += 1
            issues.append(f"Question {i+1}: Validation error: {e}")
    
    # Calculate date coverage
    date_coverage = {}
    if dates:
        date_coverage = {
            "earliest": min(dates),
            "latest": max(dates),
            "span_years": (max(dates) - min(dates)).days / 365.25,
            "total_with_dates": len(dates)
        }
    
    # Create report
    report = DataQualityReport(
        total_questions=len(questions),
        valid_questions=valid_questions,
        invalid_questions=invalid_questions,
        missing_dates=missing_dates,
        missing_sample_sizes=missing_sample_sizes,
        invalid_percentages=invalid_percentages,
        duplicate_questions=duplicate_questions,
        date_coverage=date_coverage,
        organization_coverage=organizations,
        country_coverage=countries,
        category_coverage=categories,
        issues=issues
    )
    
    # Log summary
    logger.info(f"Validation complete: {valid_questions}/{len(questions)} valid questions")
    logger.info(f"Quality score: {report.quality_score:.1f}/100")
    
    if issues:
        logger.warning(f"Found {len(issues)} data quality issues")
        # Log first few issues as examples
        for issue in issues[:5]:
            logger.warning(f"  {issue}")
        if len(issues) > 5:
            logger.warning(f"  ... and {len(issues) - 5} more issues")
    
    return report


def clean_polling_data(questions: List[PollingQuestion], strict: bool = False) -> Tuple[List[PollingQuestion], DataQualityReport]:
    """Clean polling data by removing/fixing quality issues.
    
    Args:
        questions: List of questions to clean
        strict: If True, remove questions with any quality issues
        
    Returns:
        Tuple of (cleaned_questions, quality_report)
    """
    logger = get_logger(__name__)
    logger.info(f"Cleaning {len(questions)} polling questions (strict={strict})...")
    
    cleaned_questions = []
    
    for question in questions:
        # Skip if validation fails
        try:
            question.dict()  # Validate
        except Exception:
            continue
        
        # Apply cleaning rules
        if strict:
            # Strict mode: require complete data
            if (question.fieldwork_date is None or 
                question.n_respondents is None or
                question.agreement is None):
                continue
        
        # Fix common issues
        cleaned_question = question.copy()
        
        # Standardize country names
        country_mappings = {
            "USA": "United States",
            "US": "United States", 
            "UK": "United Kingdom",
            "GB": "United Kingdom",
        }
        
        if cleaned_question.country in country_mappings:
            cleaned_question.country = country_mappings[cleaned_question.country]
        
        # Clean organization names
        org_mappings = {
            "MITRE-Harris Poll": "MITRE-Harris Poll",
            "Harris Poll": "MITRE-Harris Poll",
            "Bentley-Gallup": "Bentley-Gallup",
            "Gallup": "Bentley-Gallup",
        }
        
        if cleaned_question.survey_organisation in org_mappings:
            cleaned_question.survey_organisation = org_mappings[cleaned_question.survey_organisation]
        
        cleaned_questions.append(cleaned_question)
    
    # Generate quality report on cleaned data
    report = validate_polling_data(cleaned_questions)
    
    logger.info(f"Cleaning complete: {len(cleaned_questions)}/{len(questions)} questions retained")
    
    return cleaned_questions, report


def create_polling_dataset(questions: List[PollingQuestion], validate: bool = True) -> PollingDataset:
    """Create a validated PollingDataset from questions.
    
    Args:
        questions: List of PollingQuestion objects
        validate: Whether to validate data quality
        
    Returns:
        PollingDataset object
        
    Raises:
        DataQualityError: If data quality is too poor
    """
    if validate:
        report = validate_polling_data(questions)
        
        # Check if data quality is acceptable
        if report.quality_score < 50:
            raise DataQualityError(
                f"Data quality too poor (score: {report.quality_score:.1f}/100). "
                f"Issues: {len(report.issues)}"
            )
    
    # Create dataset (Pydantic will calculate metadata automatically)
    dataset = PollingDataset(questions=questions)
    
    return dataset