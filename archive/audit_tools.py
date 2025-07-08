#!/usr/bin/env python3
"""Auditing tools for validating Gemini extraction quality."""

import json
import random
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ai_polling.core.models import PollingQuestion

console = Console()

def load_latest_results() -> List[PollingQuestion]:
    """Load the most recent extraction results."""
    results_file = Path("extracted_data/polling_data_latest.json")
    if not results_file.exists():
        console.print("❌ No recent results found. Run extraction first.", style="red")
        return []
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    return [PollingQuestion(**item) for item in data]

def audit_sample_questions(questions: List[PollingQuestion], sample_size: int = 10) -> None:
    """Display a random sample of questions for manual review."""
    
    if len(questions) < sample_size:
        sample_size = len(questions)
    
    sample = random.sample(questions, sample_size)
    
    console.print(Panel.fit(f"🔍 Random Sample Audit ({sample_size} questions)", style="bold blue"))
    
    for i, q in enumerate(sample, 1):
        console.print(f"\n📝 **Question {i}/{sample_size}**")
        
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("**Source**", q.source_file or "Unknown")
        table.add_row("**Organization**", q.survey_organisation)
        table.add_row("**Country**", q.country)
        table.add_row("**Date**", str(q.fieldwork_date) if q.fieldwork_date else "Missing")
        table.add_row("**Sample Size**", str(q.n_respondents) if q.n_respondents else "Missing")
        table.add_row("**Category**", q.category)
        table.add_row("**Question**", q.question_text[:100] + "..." if len(q.question_text) > 100 else q.question_text)
        table.add_row("**Response Scale**", q.response_scale)
        
        # Results
        total_pct = 0
        if q.agreement is not None:
            total_pct += q.agreement
            table.add_row("**Agreement**", f"{q.agreement:.1f}%")
        if q.neutral is not None:
            total_pct += q.neutral
            table.add_row("**Neutral**", f"{q.neutral:.1f}%")
        if q.disagreement is not None:
            total_pct += q.disagreement
            table.add_row("**Disagreement**", f"{q.disagreement:.1f}%")
        if q.non_response is not None:
            total_pct += q.non_response
            table.add_row("**Non-response**", f"{q.non_response:.1f}%")
        
        table.add_row("**Total %**", f"{total_pct:.1f}%")
        table.add_row("**Quality**", f"{q.data_quality}" if q.data_quality else "Not assessed")
        
        if q.quality_issues:
            table.add_row("**Issues**", ", ".join(q.quality_issues))
        
        console.print(table)
        
        # Ask for user feedback
        console.print("\n🤔 **Your Assessment:**")
        console.print("1. Does the question text look accurate?")
        console.print("2. Are the percentages reasonable?")
        console.print("3. Is the categorization correct?")
        console.print("4. Does the organization/country make sense?")
        
        input("\nPress Enter to continue to next question...")

def audit_by_source_file(questions: List[PollingQuestion]) -> None:
    """Show summary by source file for targeted auditing."""
    
    console.print(Panel.fit("📊 Extraction Summary by Source File", style="bold green"))
    
    by_source = {}
    for q in questions:
        source = q.source_file or "Unknown"
        if source not in by_source:
            by_source[source] = {
                'count': 0,
                'categories': set(),
                'countries': set(),
                'organizations': set(),
                'date_range': [],
                'quality_issues': 0
            }
        
        by_source[source]['count'] += 1
        by_source[source]['categories'].add(q.category)
        by_source[source]['countries'].add(q.country)
        by_source[source]['organizations'].add(q.survey_organisation)
        
        if q.fieldwork_date:
            by_source[source]['date_range'].append(q.fieldwork_date)
        
        if q.quality_issues:
            by_source[source]['quality_issues'] += len(q.quality_issues)
    
    table = Table(title="Source File Analysis")
    table.add_column("File", style="cyan")
    table.add_column("Questions", style="magenta")
    table.add_column("Categories", style="green") 
    table.add_column("Countries", style="blue")
    table.add_column("Organizations", style="yellow")
    table.add_column("Quality Issues", style="red")
    
    for source, stats in sorted(by_source.items(), key=lambda x: x[1]['count'], reverse=True):
        table.add_row(
            source[:30] + "..." if len(source) > 30 else source,
            str(stats['count']),
            str(len(stats['categories'])),
            str(len(stats['countries'])),
            str(len(stats['organizations'])),
            str(stats['quality_issues'])
        )
    
    console.print(table)
    
    # Recommendations
    console.print("\n🎯 **Audit Recommendations:**")
    high_volume_files = [s for s, stats in by_source.items() if stats['count'] > 20]
    high_issue_files = [s for s, stats in by_source.items() if stats['quality_issues'] > 5]
    
    if high_volume_files:
        console.print(f"📋 **High-volume files** (>20 questions): {len(high_volume_files)} files")
        console.print("   → Priority for manual spot-checking")
    
    if high_issue_files:
        console.print(f"⚠️  **High-issue files** (>5 quality issues): {len(high_issue_files)} files")
        console.print("   → Check these files first")

def audit_categorization(questions: List[PollingQuestion]) -> None:
    """Audit category assignments."""
    
    console.print(Panel.fit("🏷️ Category Audit", style="bold yellow"))
    
    by_category = {}
    for q in questions:
        cat = q.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(q)
    
    for category, qs in by_category.items():
        console.print(f"\n📂 **{category}** ({len(qs)} questions)")
        
        # Show a few sample question texts
        samples = random.sample(qs, min(3, len(qs)))
        for i, q in enumerate(samples, 1):
            console.print(f"   {i}. {q.question_text[:80]}...")
        
        if len(qs) > 3:
            console.print(f"   ... and {len(qs) - 3} more")

def find_percentage_anomalies(questions: List[PollingQuestion]) -> None:
    """Find questions with unusual percentage distributions."""
    
    console.print(Panel.fit("🚨 Percentage Anomalies", style="bold red"))
    
    anomalies = []
    
    for q in questions:
        if all(x is not None for x in [q.agreement, q.neutral, q.disagreement]):
            total = q.agreement + q.neutral + q.disagreement
            if q.non_response:
                total += q.non_response
            
            # Flag unusual patterns
            if total < 80 or total > 120:
                anomalies.append(('Total %', q, f"Total: {total:.1f}%"))
            elif q.agreement > 95 or q.disagreement > 95:
                anomalies.append(('Extreme Response', q, f"Agree: {q.agreement:.1f}%, Disagree: {q.disagreement:.1f}%"))
            elif q.neutral > 50:
                anomalies.append(('High Neutral', q, f"Neutral: {q.neutral:.1f}%"))
    
    if anomalies:
        table = Table(title=f"Found {len(anomalies)} Percentage Anomalies")
        table.add_column("Type", style="red")
        table.add_column("Source", style="cyan")
        table.add_column("Question", style="white", max_width=50)
        table.add_column("Issue", style="yellow")
        
        for anomaly_type, q, issue in anomalies[:20]:  # Show first 20
            table.add_row(
                anomaly_type,
                q.source_file or "Unknown",
                q.question_text[:50] + "..." if len(q.question_text) > 50 else q.question_text,
                issue
            )
        
        console.print(table)
        
        if len(anomalies) > 20:
            console.print(f"\n... and {len(anomalies) - 20} more anomalies")
    else:
        console.print("✅ No significant percentage anomalies found")

def generate_audit_report(questions: List[PollingQuestion]) -> None:
    """Generate comprehensive audit report."""
    
    console.print(Panel.fit("📋 Comprehensive Audit Report", style="bold magenta"))
    
    total_questions = len(questions)
    
    # Basic stats
    console.print(f"\n📊 **Basic Statistics:**")
    console.print(f"   Total Questions: {total_questions}")
    
    # Missing data analysis
    missing_dates = sum(1 for q in questions if q.fieldwork_date is None)
    missing_samples = sum(1 for q in questions if q.n_respondents is None)
    missing_countries = sum(1 for q in questions if not q.country or q.country.lower() in ['unknown', 'global'])
    
    console.print(f"\n🚩 **Missing Data:**")
    console.print(f"   Missing Dates: {missing_dates}/{total_questions} ({missing_dates/total_questions*100:.1f}%)")
    console.print(f"   Missing Sample Sizes: {missing_samples}/{total_questions} ({missing_samples/total_questions*100:.1f}%)")
    console.print(f"   Missing/Vague Countries: {missing_countries}/{total_questions} ({missing_countries/total_questions*100:.1f}%)")
    
    # Quality distribution
    quality_dist = {}
    for q in questions:
        qual = q.data_quality or "Unknown"
        quality_dist[qual] = quality_dist.get(qual, 0) + 1
    
    console.print(f"\n⭐ **Quality Distribution:**")
    for qual, count in sorted(quality_dist.items()):
        console.print(f"   {qual}: {count}/{total_questions} ({count/total_questions*100:.1f}%)")
    
    # Category distribution
    cat_dist = {}
    for q in questions:
        cat_dist[q.category] = cat_dist.get(q.category, 0) + 1
    
    console.print(f"\n🏷️ **Category Distribution:**")
    for cat, count in sorted(cat_dist.items(), key=lambda x: x[1], reverse=True):
        console.print(f"   {cat}: {count} questions")

def main():
    """Main auditing interface."""
    questions = load_latest_results()
    
    if not questions:
        return
    
    while True:
        console.print("\n" + "="*60)
        console.print("🔍 **AI Polling Extraction Audit Tools**")
        console.print("="*60)
        
        console.print("\n📋 **Available Audits:**")
        console.print("1. Random sample review (manual)")
        console.print("2. Source file summary")
        console.print("3. Category audit")
        console.print("4. Percentage anomalies")
        console.print("5. Comprehensive report")
        console.print("6. Exit")
        
        choice = input("\nSelect audit type (1-6): ").strip()
        
        if choice == "1":
            sample_size = input("Sample size (default 10): ").strip()
            sample_size = int(sample_size) if sample_size.isdigit() else 10
            audit_sample_questions(questions, sample_size)
        elif choice == "2":
            audit_by_source_file(questions)
        elif choice == "3":
            audit_categorization(questions)
        elif choice == "4":
            find_percentage_anomalies(questions)
        elif choice == "5":
            generate_audit_report(questions)
        elif choice == "6":
            break
        else:
            console.print("Invalid choice. Please select 1-6.")

if __name__ == "__main__":
    main()