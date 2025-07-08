"""Data aggregation and combination utilities."""

from typing import List, Dict, Set, Tuple
from collections import defaultdict

from ..core.models import PollingQuestion, PollingDataset
from ..core.logger import get_logger


def deduplicate_questions(questions: List[PollingQuestion]) -> List[PollingQuestion]:
    """Remove duplicate questions based on key fields.
    
    Args:
        questions: List of potentially duplicate questions
        
    Returns:
        List with duplicates removed (keeps first occurrence)
    """
    logger = get_logger(__name__)
    
    seen = set()
    unique_questions = []
    
    for question in questions:
        # Create unique key from core identifying fields
        key = (
            question.question_text.strip().lower(),
            question.country.strip().lower(),
            question.survey_organisation.strip().lower(),
            question.fieldwork_date
        )
        
        if key not in seen:
            seen.add(key)
            unique_questions.append(question)
    
    removed_count = len(questions) - len(unique_questions)
    if removed_count > 0:
        logger.info(f"Removed {removed_count} duplicate questions")
    
    return unique_questions


def combine_datasets(*datasets: PollingDataset) -> PollingDataset:
    """Combine multiple polling datasets into one.
    
    Args:
        *datasets: Variable number of PollingDataset objects
        
    Returns:
        Combined PollingDataset with duplicates removed
    """
    logger = get_logger(__name__)
    
    all_questions = []
    for dataset in datasets:
        all_questions.extend(dataset.questions)
    
    logger.info(f"Combining {len(datasets)} datasets with {len(all_questions)} total questions")
    
    # Remove duplicates
    unique_questions = deduplicate_questions(all_questions)
    
    # Create new combined dataset
    combined = PollingDataset(questions=unique_questions)
    
    logger.info(f"Combined dataset: {len(unique_questions)} unique questions from {combined.unique_organizations} organizations")
    
    return combined


def merge_question_lists(*question_lists: List[PollingQuestion]) -> List[PollingQuestion]:
    """Merge multiple lists of questions and remove duplicates.
    
    Args:
        *question_lists: Variable number of question lists
        
    Returns:
        Merged list with duplicates removed
    """
    all_questions = []
    for question_list in question_lists:
        all_questions.extend(question_list)
    
    return deduplicate_questions(all_questions)


def group_questions_by_organization(questions: List[PollingQuestion]) -> Dict[str, List[PollingQuestion]]:
    """Group questions by survey organization.
    
    Args:
        questions: List of questions to group
        
    Returns:
        Dictionary mapping organization names to question lists
    """
    groups = defaultdict(list)
    
    for question in questions:
        groups[question.survey_organisation].append(question)
    
    return dict(groups)


def group_questions_by_country(questions: List[PollingQuestion]) -> Dict[str, List[PollingQuestion]]:
    """Group questions by country.
    
    Args:
        questions: List of questions to group
        
    Returns:
        Dictionary mapping country names to question lists
    """
    groups = defaultdict(list)
    
    for question in questions:
        groups[question.country].append(question)
    
    return dict(groups)


def group_questions_by_category(questions: List[PollingQuestion]) -> Dict[str, List[PollingQuestion]]:
    """Group questions by category.
    
    Args:
        questions: List of questions to group
        
    Returns:
        Dictionary mapping category names to question lists
    """
    groups = defaultdict(list)
    
    for question in questions:
        cat_key = question.category.value if hasattr(question.category, 'value') else str(question.category)
        groups[cat_key].append(question)
    
    return dict(groups)


def get_summary_statistics(questions: List[PollingQuestion]) -> Dict[str, any]:
    """Calculate summary statistics for a list of questions.
    
    Args:
        questions: List of questions to analyze
        
    Returns:
        Dictionary with summary statistics
    """
    if not questions:
        return {}
    
    # Basic counts
    total_questions = len(questions)
    unique_orgs = len(set(q.survey_organisation for q in questions))
    unique_countries = len(set(q.country for q in questions))
    
    # Date range
    dates = [q.fieldwork_date for q in questions if q.fieldwork_date]
    date_range = None
    if dates:
        date_range = {
            "earliest": min(dates),
            "latest": max(dates),
            "span_days": (max(dates) - min(dates)).days
        }
    
    # Agreement statistics (for questions with agreement data)
    agreement_values = [q.agreement for q in questions if q.agreement is not None]
    agreement_stats = {}
    if agreement_values:
        agreement_stats = {
            "mean": sum(agreement_values) / len(agreement_values),
            "median": sorted(agreement_values)[len(agreement_values) // 2],
            "min": min(agreement_values),
            "max": max(agreement_values)
        }
    
    # Category breakdown
    category_counts = defaultdict(int)
    for question in questions:
        cat_key = question.category.value if hasattr(question.category, 'value') else str(question.category)
        category_counts[cat_key] += 1
    
    return {
        "total_questions": total_questions,
        "unique_organizations": unique_orgs,
        "unique_countries": unique_countries,
        "date_range": date_range,
        "agreement_statistics": agreement_stats,
        "category_breakdown": dict(category_counts)
    }