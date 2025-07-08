#!/usr/bin/env python3
"""Debug validation issues in extracted data."""

from ai_polling.extractors.pdf_extractor import PDFExtractor
from ai_polling.processors.validator import validate_polling_data
from pathlib import Path
import json

def analyze_validation_issues():
    """Analyze what's causing validation failures."""
    
    # Test files with known issues
    test_files = [
        "kantar_nov_2022.pdf",
        "rand_oct_2022.pdf", 
        "yougov_sep_2023.pdf"
    ]
    
    extractor = PDFExtractor()
    
    for filename in test_files:
        file_path = Path("polling_pdfs") / filename
        if not file_path.exists():
            continue
            
        print(f"\n=== Analyzing {filename} ===")
        
        try:
            # Extract raw data
            questions = extractor.extract_from_file(file_path)
            print(f"Total extracted: {len(questions)}")
            
            # Validate
            report = validate_polling_data(questions)
            print(f"Valid: {report.valid_questions}/{report.total_questions}")
            print(f"Quality score: {report.quality_score}")
            
            # Show first few issues
            if report.issues:
                print(f"\nFirst 5 issues:")
                for i, issue in enumerate(report.issues[:5]):
                    print(f"  {i+1}. {issue}")
            
            # Analyze invalid records
            invalid_count = 0
            for i, question in enumerate(questions):
                try:
                    # Try to validate individual question
                    question.model_validate(question.dict())
                except Exception as e:
                    invalid_count += 1
                    if invalid_count <= 3:  # Show first 3 invalid records
                        print(f"\nInvalid record {i+1}: {e}")
                        print(f"  Question: {question.question_text[:100]}...")
                        print(f"  Category: {question.category}")
                        print(f"  Agreement: {question.agreement}")
                        print(f"  Sample size: {question.n_respondents}")
                        
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    analyze_validation_issues()