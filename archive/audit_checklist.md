# 🔍 AI Polling Extraction Audit Checklist

## Phase 1: Quick Quality Assessment (Start Here)

### **1. Run Automated Audit Tools**
```bash
python audit_tools.py
```

**Check:**
- [ ] Overall extraction counts make sense
- [ ] No obvious data quality red flags
- [ ] Categories are distributed reasonably
- [ ] Missing data levels are acceptable

### **2. High-Level Validation (5 minutes)**
```bash
python -c "
from ai_polling.core.models import PollingDataset
import json

with open('extracted_data/polling_data_latest.json', 'r') as f:
    data = json.load(f)

print(f'Total questions: {len(data)}')
print(f'Files processed: {len(set(q.get(\"source_file\") for q in data))}')
print(f'Countries: {len(set(q.get(\"country\") for q in data))}')
print(f'Organizations: {len(set(q.get(\"survey_organisation\") for q in data))}')
"
```

**Sanity Check:**
- [ ] Total questions seem reasonable for the number of PDFs
- [ ] Country/organization diversity makes sense
- [ ] No completely empty extractions

## Phase 2: Targeted Deep Dives

### **3. Source-by-Source Audit**

**Pick 2-3 files you know well and manually verify:**

#### **File 1: [Your choice]**
- [ ] Open the original PDF/HTML
- [ ] Random sample 5-10 questions from extraction results
- [ ] Check: Question text accuracy
- [ ] Check: Response percentages match
- [ ] Check: Categorization makes sense
- [ ] Check: Methodology info captured

#### **File 2: [Your choice]**
- [ ] Repeat same process
- [ ] Look for patterns in errors
- [ ] Note any systematic issues

### **4. Edge Case Analysis**

**Check files that had issues:**
```bash
# Find files with validation issues
ls cache/validation_issues_*.json
```

**For each flagged file:**
- [ ] Review the validation issues
- [ ] Check if issues are real problems or acceptable quirks
- [ ] Verify Gemini handled complex tables correctly
- [ ] Check multi-country surveys were split properly

### **5. Category Validation**

**Use the categorization audit tool:**
- [ ] Sample 3-5 questions from each category
- [ ] Verify they actually belong in that category
- [ ] Check for obvious miscategorizations
- [ ] Look for questions that should be in different categories

## Phase 3: Statistical Validation

### **6. Percentage Sanity Checks**

**Run percentage anomaly detection:**
- [ ] Investigate any totals <80% or >120%
- [ ] Check extreme responses (>95% agree/disagree) 
- [ ] Verify high neutral responses make sense
- [ ] Cross-check suspicious numbers with source docs

### **7. Metadata Validation**

**Check enrichment accuracy:**
- [ ] Verify fieldwork dates were filled correctly
- [ ] Check sample sizes match your spreadsheet
- [ ] Confirm countries are accurate
- [ ] Validate organization names

### **8. Cross-File Consistency**

**Look for patterns across files:**
- [ ] Similar organizations should have consistent naming
- [ ] Date formats should be consistent
- [ ] Question styles from same pollster should be similar
- [ ] Response scales should make sense

## Phase 4: Known-Good Validation

### **9. Benchmark Against Manual Extraction**

**Pick one file you've manually extracted before:**
- [ ] Compare question counts
- [ ] Check 10-15 specific questions match exactly
- [ ] Verify percentages are within 1-2% (small rounding differences OK)
- [ ] Confirm no major questions were missed

### **10. Expert Domain Review**

**For questions you know well:**
- [ ] Do AI regulation questions capture the right sentiment?
- [ ] Are extinction risk questions properly identified?
- [ ] Do job displacement questions make sense?
- [ ] Are methodology notes helpful and accurate?

## Phase 5: Error Pattern Analysis

### **11. Common Error Types**

**Document patterns you find:**
- [ ] Question text truncation or corruption
- [ ] Percentage calculation errors
- [ ] Category misassignment patterns
- [ ] Missing context (multi-part questions)
- [ ] Table parsing issues

### **12. Systematic Issues**

**Look for:**
- [ ] Consistent problems with certain PDF formats
- [ ] Issues with specific pollsters' layouts
- [ ] Problems with particular question types
- [ ] HTML vs PDF extraction differences

## Red Flags 🚨

**Stop and investigate if you see:**
- ❌ Question text that's clearly wrong/corrupted
- ❌ Percentages that obviously don't match the source
- ❌ Major questions you know exist but weren't extracted
- ❌ Completely wrong categorization (e.g., job questions marked as regulation)
- ❌ Dates that are clearly wrong (future dates, wrong years)
- ❌ Sample sizes that are wildly off

## Green Flags ✅

**You're in good shape if:**
- ✅ 95%+ of spot-checked questions are accurate
- ✅ Percentages are within 2-3% of source (small differences OK)
- ✅ Categories make sense for 90%+ of questions
- ✅ No systematic patterns of errors
- ✅ Complex tables and charts were parsed reasonably well
- ✅ Multi-country data was split appropriately

## Quick Audit Commands

```bash
# Run full audit suite
python audit_tools.py

# Check specific file
python -c "
import json
with open('extracted_data/polling_data_latest.json', 'r') as f:
    data = json.load(f)
    
target_file = 'your_file.pdf'
questions = [q for q in data if q.get('source_file') == target_file]
print(f'Found {len(questions)} questions from {target_file}')
for i, q in enumerate(questions[:5]):
    print(f'{i+1}. {q[\"question_text\"][:80]}...')
"

# Check percentage totals
python -c "
import json
with open('extracted_data/polling_data_latest.json', 'r') as f:
    data = json.load(f)

anomalies = []
for q in data:
    if all(q.get(k) is not None for k in ['agreement', 'neutral', 'disagreement']):
        total = q['agreement'] + q['neutral'] + q['disagreement']
        if q.get('non_response'):
            total += q['non_response']
        if total < 80 or total > 120:
            anomalies.append((q['source_file'], total, q['question_text'][:50]))

print(f'Found {len(anomalies)} percentage anomalies')
for source, total, text in anomalies[:10]:
    print(f'{source}: {total:.1f}% - {text}...')
"
```

## Expected Accuracy Levels

**Realistic expectations for AI extraction:**
- **Question text**: 95-98% accurate (minor formatting differences OK)
- **Percentages**: 90-95% within 2% of source (rounding differences expected)
- **Categorization**: 85-90% accurate (subjective, some disagreement normal)
- **Metadata**: 80-90% accurate (dates/samples often missing from PDFs)
- **Overall extraction**: 90-95% of questions that exist in accessible format

## When to Adjust vs Accept

**Adjust the system if:**
- Major systematic errors (e.g., always missing certain question types)
- Consistent percentage calculation problems
- Poor handling of specific PDF formats
- Category assignment is consistently wrong

**Accept minor issues like:**
- Small percentage rounding differences (1-2%)
- Occasional missing context from complex layouts
- Minor formatting differences in question text
- Subjective category disagreements