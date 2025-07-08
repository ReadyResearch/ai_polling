"""Question categorization utilities."""

import re
from typing import List

from ..core.models import CategoryEnum
from ..core.config import get_config


def categorize_question(question_text: str, response_scale: str = "") -> CategoryEnum:
    """Automatically categorize a polling question based on its text.
    
    Args:
        question_text: The text of the polling question
        response_scale: The response scale (optional, for additional context)
        
    Returns:
        CategoryEnum representing the best category match
    """
    config = get_config()
    
    # Convert to lowercase for matching
    text_lower = question_text.lower()
    scale_lower = response_scale.lower()
    combined_text = f"{text_lower} {scale_lower}"
    
    # Category keyword matching with weights
    category_scores = {
        CategoryEnum.AI_REGULATION: 0,
        CategoryEnum.AI_RISK_CONCERN: 0,
        CategoryEnum.EXTINCTION_RISK: 0,
        CategoryEnum.JOB_DISPLACEMENT: 0,
        CategoryEnum.AI_SENTIMENT: 0,
        CategoryEnum.AI_KNOWLEDGE: 0,
        CategoryEnum.OTHER: 0
    }
    
    # AI Regulation keywords
    for keyword in config.categories.ai_regulation_keywords:
        if keyword.lower() in combined_text:
            category_scores[CategoryEnum.AI_REGULATION] += 2
            # Boost score for strong regulation indicators
            if keyword.lower() in ["regulation", "oversight", "governance", "testing"]:
                category_scores[CategoryEnum.AI_REGULATION] += 1
    
    # AI Risk keywords
    for keyword in config.categories.ai_risk_keywords:
        if keyword.lower() in combined_text:
            category_scores[CategoryEnum.AI_RISK_CONCERN] += 2
    
    # Extinction risk keywords (high weight due to specificity)
    for keyword in config.categories.extinction_risk_keywords:
        if keyword.lower() in combined_text:
            category_scores[CategoryEnum.EXTINCTION_RISK] += 3
    
    # Job displacement keywords
    for keyword in config.categories.job_displacement_keywords:
        if keyword.lower() in combined_text:
            category_scores[CategoryEnum.JOB_DISPLACEMENT] += 2
    
    # AI Knowledge indicators
    knowledge_patterns = [
        r"how much.*know",
        r"familiar.*with",
        r"heard.*of",
        r"understanding.*of",
        r"awareness.*of"
    ]
    
    for pattern in knowledge_patterns:
        if re.search(pattern, text_lower):
            category_scores[CategoryEnum.AI_KNOWLEDGE] += 2
    
    # AI Sentiment indicators
    sentiment_patterns = [
        r"feel.*about",
        r"opinion.*of",
        r"attitude.*toward",
        r"view.*of",
        r"excited.*about",
        r"optimistic.*about",
        r"pessimistic.*about"
    ]
    
    for pattern in sentiment_patterns:
        if re.search(pattern, text_lower):
            category_scores[CategoryEnum.AI_SENTIMENT] += 2
    
    # Special pattern-based rules
    
    # Strong regulation indicators
    regulation_patterns = [
        r"should.*regulat",
        r"government.*should",
        r"federal.*agency",
        r"international.*cooperation",
        r"safety.*standards",
        r"testing.*require",
        r"approval.*process"
    ]
    
    for pattern in regulation_patterns:
        if re.search(pattern, text_lower):
            category_scores[CategoryEnum.AI_REGULATION] += 3
    
    # Strong risk indicators
    risk_patterns = [
        r"worried.*about",
        r"concerned.*about",
        r"afraid.*of",
        r"dangerous",
        r"harmful",
        r"threat.*from"
    ]
    
    for pattern in risk_patterns:
        if re.search(pattern, text_lower):
            category_scores[CategoryEnum.AI_RISK_CONCERN] += 3
    
    # Find the category with the highest score
    best_category = max(category_scores.items(), key=lambda x: x[1])
    
    # If no category has a significant score, default to OTHER
    if best_category[1] == 0:
        return CategoryEnum.OTHER
    
    return best_category[0]


def validate_categorization(question_text: str, assigned_category: CategoryEnum) -> bool:
    """Validate that a question's category assignment makes sense.
    
    Args:
        question_text: The question text
        assigned_category: The currently assigned category
        
    Returns:
        True if the categorization seems reasonable, False otherwise
    """
    # Auto-categorize and compare
    auto_category = categorize_question(question_text)
    
    # If auto-categorization is confident (not OTHER) and differs significantly,
    # this might indicate a categorization issue
    if auto_category != CategoryEnum.OTHER and auto_category != assigned_category:
        # Allow some flexibility - only flag major mismatches
        major_mismatches = [
            (CategoryEnum.AI_REGULATION, CategoryEnum.AI_SENTIMENT),
            (CategoryEnum.EXTINCTION_RISK, CategoryEnum.AI_SENTIMENT),
            (CategoryEnum.JOB_DISPLACEMENT, CategoryEnum.AI_RISK_CONCERN),
        ]
        
        for cat1, cat2 in major_mismatches:
            if (assigned_category, auto_category) in [(cat1, cat2), (cat2, cat1)]:
                return False
    
    return True


def suggest_recategorization(questions: List[dict]) -> List[dict]:
    """Suggest recategorization for a list of questions.
    
    Args:
        questions: List of question dictionaries with 'question_text' and 'category'
        
    Returns:
        List of questions with suggested category corrections
    """
    suggestions = []
    
    for question in questions:
        current_category = question.get('category')
        question_text = question.get('question_text', '')
        
        # Get auto-categorization suggestion
        suggested_category = categorize_question(question_text)
        
        # Create suggestion entry
        suggestion = question.copy()
        suggestion['suggested_category'] = suggested_category.value
        suggestion['category_confidence'] = 'high' if suggested_category != CategoryEnum.OTHER else 'low'
        suggestion['needs_review'] = not validate_categorization(question_text, CategoryEnum(current_category))
        
        suggestions.append(suggestion)
    
    return suggestions