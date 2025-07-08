#!/usr/bin/env python3
"""Generate quality summary reports for extracted data."""

from typing import List, Dict, Any
from collections import defaultdict, Counter
from ai_polling.core.models import PollingQuestion, DataQuality

def generate_quality_summary(questions: List[PollingQuestion]) -> Dict[str, Any]:
    """Generate comprehensive quality summary."""
    
    quality_counts = Counter()
    issues_by_type = defaultdict(int)
    quality_by_source = defaultdict(list)
    
    for question in questions:
        # Count quality levels
        if question.data_quality:
            quality_counts[question.data_quality] += 1
            
        # Count issue types
        if question.quality_issues:
            for issue in question.quality_issues:
                issues_by_type[issue] += 1
        
        # Track quality by source file
        if question.source_file:
            quality_by_source[question.source_file].append(question.data_quality)
    
    # Calculate percentages
    total_questions = len(questions)
    quality_percentages = {
        quality: (count / total_questions * 100) if total_questions > 0 else 0
        for quality, count in quality_counts.items()
    }
    
    # Source file quality summary
    source_quality = {}
    for source, qualities in quality_by_source.items():
        quality_counter = Counter(qualities)
        source_quality[source] = {
            'total': len(qualities),
            'high': quality_counter.get(DataQuality.HIGH, 0),
            'good': quality_counter.get(DataQuality.GOOD, 0),
            'acceptable': quality_counter.get(DataQuality.ACCEPTABLE, 0),
            'flagged': quality_counter.get(DataQuality.FLAGGED, 0),
            'poor': quality_counter.get(DataQuality.POOR, 0),
        }
    
    return {
        'total_questions': total_questions,
        'quality_distribution': dict(quality_counts),
        'quality_percentages': quality_percentages,
        'common_issues': dict(issues_by_type),
        'source_file_quality': source_quality,
        'flagged_questions': [
            {
                'question_text': q.question_text[:100] + "...",
                'source_file': q.source_file,
                'quality': q.data_quality,
                'issues': q.quality_issues
            }
            for q in questions 
            if q.data_quality in [DataQuality.FLAGGED, DataQuality.POOR]
        ]
    }

def print_quality_report(summary: Dict[str, Any]) -> None:
    """Print a formatted quality report."""
    
    print("\n" + "="*60)
    print("📊 DATA QUALITY SUMMARY REPORT")
    print("="*60)
    
    print(f"\n📈 Overall Statistics:")
    print(f"  Total Questions: {summary['total_questions']}")
    
    print(f"\n🎯 Quality Distribution:")
    for quality, count in summary['quality_distribution'].items():
        pct = summary['quality_percentages'][quality]
        print(f"  {quality.upper()}: {count} ({pct:.1f}%)")
    
    print(f"\n⚠️ Common Issues:")
    sorted_issues = sorted(summary['common_issues'].items(), key=lambda x: x[1], reverse=True)
    for issue, count in sorted_issues[:10]:
        print(f"  {issue}: {count} questions")
    
    print(f"\n📄 Quality by Source File:")
    for source, stats in summary['source_file_quality'].items():
        high_pct = (stats['high'] / stats['total'] * 100) if stats['total'] > 0 else 0
        flagged = stats['flagged'] + stats['poor']
        print(f"  {source}: {stats['total']} total, {stats['high']} high quality ({high_pct:.1f}%), {flagged} flagged")
    
    if summary['flagged_questions']:
        print(f"\n🚩 Questions Needing Review ({len(summary['flagged_questions'])}):")
        for i, q in enumerate(summary['flagged_questions'][:5]):
            print(f"  {i+1}. {q['source_file']}: {q['question_text']}")
            print(f"     Issues: {', '.join(q['issues'])}")
        
        if len(summary['flagged_questions']) > 5:
            print(f"     ... and {len(summary['flagged_questions']) - 5} more")

if __name__ == "__main__":
    # This can be used as a standalone script
    pass