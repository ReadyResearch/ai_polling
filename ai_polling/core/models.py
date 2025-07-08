"""Pydantic data models for polling data."""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class CategoryEnum(str, Enum):
    """Question category enumeration."""
    
    AI_REGULATION = "AI_Regulation"
    AI_RISK_CONCERN = "AI_Risk_Concern" 
    AI_SENTIMENT = "AI_Sentiment"
    JOB_DISPLACEMENT = "Job_Displacement"
    EXTINCTION_RISK = "Extinction_Risk"
    AI_KNOWLEDGE = "AI_Knowledge"
    OTHER = "Other"


class DataQuality(str, Enum):
    """Data quality classification."""
    
    HIGH = "high"           # All fields complete, percentages sum 95-105%
    GOOD = "good"           # Minor issues (missing date, sample size, etc.)
    ACCEPTABLE = "acceptable"  # Percentages sum 80-95% or 105-115%
    FLAGGED = "flagged"     # Significant issues, needs review
    POOR = "poor"           # Major data problems


class PollingQuestion(BaseModel):
    """Individual polling question with results."""
    
    # Core question data
    question_text: str = Field(..., description="Exact question wording from survey")
    response_scale: str = Field(..., description="Available response options")
    category: CategoryEnum = Field(..., description="Question category")
    
    # Results data
    agreement: Optional[float] = Field(None, ge=0, le=100, description="Percentage of positive responses")
    neutral: Optional[float] = Field(None, ge=0, le=100, description="Percentage of neutral responses") 
    disagreement: Optional[float] = Field(None, ge=0, le=100, description="Percentage of negative responses")
    non_response: Optional[float] = Field(None, ge=0, le=100, description="Don't know/No answer/Missing response percentage")
    
    # Sample data
    n_respondents: Optional[int] = Field(None, gt=0, description="Number of survey respondents")
    
    # Context data
    country: str = Field(..., description="Country or region where conducted")
    survey_organisation: str = Field(..., description="Organization that conducted survey")
    fieldwork_date: Optional[date] = Field(None, description="When survey was conducted")
    
    # Metadata
    notes: Optional[str] = Field(None, description="Methodology details and caveats")
    
    # Processing metadata (added automatically)
    extraction_date: Optional[datetime] = Field(default_factory=datetime.now, description="When data was extracted")
    source_file: Optional[str] = Field(None, description="Source document filename")
    
    # Quality assessment (calculated automatically)
    data_quality: Optional[DataQuality] = Field(None, description="Data quality classification")
    quality_issues: Optional[List[str]] = Field(default_factory=list, description="List of quality issues found")
    
    @field_validator("question_text")
    @classmethod
    def validate_question_text(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError("Question text must be at least 10 characters")
        return v.strip()
    
    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError("Country must be specified")
        return v.strip()
    
    @field_validator("survey_organisation")
    @classmethod
    def validate_organisation(cls, v: str) -> str:
        if not v or len(v.strip()) < 3:
            raise ValueError("Survey organisation must be specified")
        return v.strip()
    
    def model_post_init(self, __context) -> None:
        """Assess data quality after model initialization."""
        # Use object.__setattr__ to avoid triggering validation
        quality_issues = []
        
        # Calculate percentage total if we have the main components
        if all(x is not None for x in [self.agreement, self.neutral, self.disagreement]):
            total = self.agreement + self.neutral + self.disagreement
            
            # Add non_response if available
            if self.non_response is not None:
                total += self.non_response
            
            # Stage 2: Quality assessment (no hard validation here)
            if 95 <= total <= 105:
                pass  # No percentage issues
            elif 85 <= total <= 115:
                quality_issues.append(f"Percentages sum to {total}% (acceptable range)")
            elif 70 <= total <= 120:
                quality_issues.append(f"Percentages sum to {total}% (needs review)")
            else:
                quality_issues.append(f"Percentages sum to {total}% (outside normal range)")
        
        # Check for missing critical data
        if self.fieldwork_date is None:
            quality_issues.append("Missing fieldwork date")
        
        if self.n_respondents is None:
            quality_issues.append("Missing sample size")
        
        if not self.response_scale or len(self.response_scale.strip()) < 5:
            quality_issues.append("Missing or unclear response scale")
        
        # Assign quality classification
        if not quality_issues:
            data_quality = DataQuality.HIGH
        elif len(quality_issues) == 1 and any(issue.startswith("Missing") for issue in quality_issues):
            data_quality = DataQuality.GOOD
        elif any("acceptable range" in issue for issue in quality_issues):
            data_quality = DataQuality.ACCEPTABLE
        elif any("needs review" in issue for issue in quality_issues):
            data_quality = DataQuality.FLAGGED
        else:
            data_quality = DataQuality.POOR
        
        # Set quality fields directly to avoid validation recursion
        object.__setattr__(self, 'data_quality', data_quality)
        object.__setattr__(self, 'quality_issues', quality_issues)
    
    @model_validator(mode='after')
    def validate_percentages_relaxed(self) -> 'PollingQuestion':
        """Basic percentage validation with relaxed constraints."""
        agreement = self.agreement
        neutral = self.neutral 
        disagreement = self.disagreement
        non_response = self.non_response
        
        # Only do basic validation if we have the main components
        if all(x is not None for x in [agreement, neutral, disagreement]):
            total = agreement + neutral + disagreement
            
            # Add non_response if available
            if non_response is not None:
                total += non_response
            
            # Very relaxed validation - only reject obviously wrong data
            if total < 50 or total > 150:
                raise ValueError(f"Percentages sum to {total}%, clearly invalid")
        
        return self
    
    @field_validator("fieldwork_date", mode='before')
    @classmethod
    def parse_fieldwork_date(cls, v: Any) -> Optional[date]:
        """Parse various date formats."""
        if v is None or v == "":
            return None
        
        if isinstance(v, date):
            return v
        
        if isinstance(v, str):
            v = v.strip()
            
            # Try common formats
            formats = [
                "%Y-%m-%d",  # 2023-04-15
                "%Y-%m",     # 2023-04
                "%Y",        # 2023
                "%m/%d/%Y",  # 04/15/2023
                "%d/%m/%Y",  # 15/04/2023
            ]
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(v, fmt).date()
                    return parsed_date
                except ValueError:
                    continue
            
            # If all formats fail, return None and let validation handle it
            return None
        
        return v
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = "forbid"  # Don't allow extra fields


class PollingDataset(BaseModel):
    """Collection of polling questions with metadata."""
    
    questions: List[PollingQuestion] = Field(..., description="List of polling questions")
    
    # Dataset metadata (calculated automatically)
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    total_questions: int = Field(0, description="Total number of questions")
    unique_organizations: int = Field(0, description="Number of unique survey organizations")
    unique_countries: int = Field(0, description="Number of unique countries")
    date_range: Optional[Dict[str, Optional[date]]] = Field(None, description="Date range of surveys")
    
    # Summary statistics (calculated automatically)
    category_breakdown: Dict[CategoryEnum, int] = Field(default_factory=dict, description="Questions per category")
    organization_breakdown: Dict[str, int] = Field(default_factory=dict, description="Questions per organization")
    
    @field_validator("questions")
    @classmethod
    def validate_questions_not_empty(cls, v: List[PollingQuestion]) -> List[PollingQuestion]:
        if not v:
            raise ValueError("Dataset must contain at least one question")
        return v
    
    def model_post_init(self, __context) -> None:
        """Calculate metadata after model initialization."""
        questions = self.questions
        
        if not questions:
            return
        
        # Basic counts
        self.total_questions = len(questions)
        self.unique_organizations = len(set(q.survey_organisation for q in questions))
        self.unique_countries = len(set(q.country for q in questions))
        
        # Date range
        dates = [q.fieldwork_date for q in questions if q.fieldwork_date]
        if dates:
            self.date_range = {
                "earliest": min(dates),
                "latest": max(dates)
            }
        
        # Category breakdown
        category_counts = {}
        for question in questions:
            category_counts[question.category] = category_counts.get(question.category, 0) + 1
        self.category_breakdown = category_counts
        
        # Organization breakdown
        org_counts = {}
        for question in questions:
            org_counts[question.survey_organisation] = org_counts.get(question.survey_organisation, 0) + 1
        self.organization_breakdown = org_counts
    
    def get_ai_regulation_questions(self) -> List[PollingQuestion]:
        """Get all AI regulation questions."""
        return [q for q in self.questions if q.category == CategoryEnum.AI_REGULATION]
    
    def get_questions_by_organization(self, organization: str) -> List[PollingQuestion]:
        """Get all questions from a specific organization."""
        return [q for q in self.questions if q.survey_organisation == organization]
    
    def get_questions_by_country(self, country: str) -> List[PollingQuestion]:
        """Get all questions from a specific country."""
        return [q for q in self.questions if q.country == country]
    
    def to_dataframe(self) -> "pd.DataFrame":
        """Convert to pandas DataFrame for analysis."""
        import pandas as pd
        
        data = []
        for question in self.questions:
            data.append(question.dict())
        
        return pd.DataFrame(data)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True