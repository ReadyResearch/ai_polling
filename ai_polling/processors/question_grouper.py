"""Question grouping using Gemini API for semantic similarity analysis."""

import json
import pandas as pd
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
from datetime import datetime
import hashlib

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from ..core.models import PollingQuestion
from ..core.config import get_config
from ..core.exceptions import AIPollingError
from ..core.logger import get_logger


class QuestionGrouper:
    """Group similar polling questions using Gemini API."""
    
    def __init__(self):
        """Initialize question grouper."""
        if genai is None:
            raise AIPollingError("google-generativeai not installed. Run: pip install google-generativeai")
        
        self.config = get_config()
        self.logger = get_logger(__name__)
        
        # Configure Gemini API - Use Pro for better grouping quality
        genai.configure(api_key=self.config.api.google_api_key)
        self.model = genai.GenerativeModel(
            "gemini-2.5-pro",
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=65536,
                temperature=0.0
            ),
            system_instruction="You are an expert in public opinion polling and survey methodology. Use your thinking capabilities to create high-quality question groupings."
        )
        
        # Cache for API calls
        self.cache = {}
    
    def group_questions(self, questions: List[PollingQuestion]) -> Dict[str, List[PollingQuestion]]:
        """Group questions by semantic similarity.
        
        Args:
            questions: List of PollingQuestion objects
            
        Returns:
            Dictionary mapping group IDs to lists of questions
        """
        self.logger.info(f"🔍 Grouping {len(questions)} questions by semantic similarity...")
        
        # Extract unique question texts
        unique_questions = self._extract_unique_questions(questions)
        self.logger.info(f"📋 Found {len(unique_questions)} unique question texts")
        
        # Group questions in batches
        question_groups = self._group_questions_batch(unique_questions)
        
        # Map original questions to groups
        grouped_questions = self._map_questions_to_groups(questions, question_groups)
        
        self.logger.info(f"✅ Created {len(grouped_questions)} question groups")
        return grouped_questions
    
    def _extract_unique_questions(self, questions: List[PollingQuestion]) -> List[str]:
        """Extract unique question texts from the dataset."""
        seen_questions = set()
        unique_questions = []
        
        for question in questions:
            # Create a normalized version for deduplication
            normalized = question.question_text.strip().lower()
            if normalized not in seen_questions:
                seen_questions.add(normalized)
                unique_questions.append(question.question_text)
        
        return unique_questions
    
    def _group_questions_batch(self, questions: List[str]) -> Dict[str, List[str]]:
        """Group questions using Gemini API with full context."""
        # Use Gemini's full 1M token context window - much faster than batching!
        self.logger.info(f"🚀 Processing all {len(questions)} questions in single API call...")
        
        # For very large datasets (>800 questions), we might still need to batch
        if len(questions) > 800:
            self.logger.info("📊 Large dataset detected - using optimized batching...")
            return self._group_questions_large_batch(questions)
        else:
            # Single API call for optimal performance
            return self._analyze_question_batch(questions)
    
    def _group_questions_large_batch(self, questions: List[str]) -> Dict[str, List[str]]:
        """Handle very large question sets with smart batching."""
        # For 800+ questions, use larger chunks but still minimize API calls
        chunk_size = 200  # Sweet spot for Gemini
        all_groups = {}
        
        for i in range(0, len(questions), chunk_size):
            chunk = questions[i:i + chunk_size]
            self.logger.info(f"📊 Processing chunk {i//chunk_size + 1}/{(len(questions) + chunk_size - 1)//chunk_size} ({len(chunk)} questions)")
            
            chunk_groups = self._analyze_question_batch(chunk)
            
            # Merge with existing groups
            for group_id, group_questions in chunk_groups.items():
                if group_id in all_groups:
                    all_groups[group_id].extend(group_questions)
                else:
                    all_groups[group_id] = group_questions
        
        return all_groups
    
    def _analyze_question_batch(self, questions: List[str]) -> Dict[str, List[str]]:
        """Analyze a batch of questions for semantic similarity."""
        # Create cache key for this batch
        cache_key = hashlib.md5(json.dumps(sorted(questions), sort_keys=True).encode()).hexdigest()
        
        if cache_key in self.cache:
            self.logger.info("📂 Using cached results for batch")
            return self.cache[cache_key]
        
        prompt = self._create_grouping_prompt(questions)
        
        try:
            # Use thinking mode with higher budget for better grouping
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=65536,
                temperature=0.0
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            result = self._parse_grouping_response(response.text, questions)
            
            # Cache the result
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to group questions: {e}")
            # Return each question as its own group
            return {f"group_{i}": [q] for i, q in enumerate(questions)}
    
    def _create_grouping_prompt(self, questions: List[str]) -> str:
        """Create prompt for Gemini to group questions."""
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        
        return f"""
You are an expert in public opinion polling and survey methodology. Your task is to intelligently group polling questions that measure the same underlying concept, creating meaningful clusters for trend analysis.

CORE MISSION: Create groups that will produce meaningful trend plots over time. Questions in the same group should measure the same attitude/policy so we can track how public opinion on that specific topic changes.

GROUPING CRITERIA:
- Group questions measuring the SAME specific policy, attitude, or concept
- Group semantic variations (e.g., "regulate AI" = "government oversight of AI" = "AI should be controlled")
- Group different wordings of the same underlying question
- Keep distinct policies separate (6-month pause ≠ permanent ban)
- Keep different scopes separate (national ≠ international)
- Keep different risk types separate (job loss ≠ extinction risk)

EXAMPLES OF GOOD GROUPING:
✅ "Support 6-month AI moratorium" + "Do you support a 6-month pause on AI development?"
✅ "Create national AI safety institute" + "Should government establish AI safety agency?"
✅ "AI will replace human jobs" + "AI poses threat to employment"
✅ "Government should regulate AI" + "More government oversight of AI needed"
✅ "Worried about AI risks" + "Concerned about AI dangers"

EXAMPLES OF BAD GROUPING:
❌ "6-month moratorium" + "permanent ban" (different policies)
❌ "National AI institute" + "International AI cooperation" (different scope)
❌ "AI is beneficial" + "Support AI regulation" (different concepts)
❌ "Job displacement" + "Extinction risk" (different types of risk)

INSTRUCTIONS FOR GROUPING:
1. Look for questions asking about the SAME specific policy or attitude
2. Group variations in wording that ask essentially the same thing
3. Group positive/negative forms of the same question (e.g., "support X" and "oppose X" measure the same concept)
4. Consider semantic equivalence: "regulate", "oversight", "control", "govern" can be similar
5. BUT keep distinct policies separate even if related
6. Create meaningful group names that capture the core concept

QUESTIONS TO GROUP:
{questions_text}

OUTPUT FORMAT:
Return a JSON object where each key is a descriptive group name and each value is a list of question numbers that belong to that group.

Focus on finding groups of 2-10 questions that genuinely measure the same concept.

Example output:
{{
  "Support_6Month_AI_Moratorium": [1, 15, 23],
  "Create_National_AI_Safety_Institute": [2, 8],
  "AI_Job_Displacement_Concern": [3, 12, 19],
  "AI_Extinction_Risk_Concern": [4, 7],
  "General_AI_Regulation_Support": [5, 11, 21]
}}

Be thoughtful about grouping - aim for meaningful groups rather than all singletons.
"""
    
    def _parse_grouping_response(self, response: str, questions: List[str]) -> Dict[str, List[str]]:
        """Parse Gemini's grouping response."""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[json_start:json_end]
            groups_data = json.loads(json_str)
            
            # Convert question numbers to actual questions
            result = {}
            for group_name, question_numbers in groups_data.items():
                group_questions = []
                for num in question_numbers:
                    if isinstance(num, int) and 1 <= num <= len(questions):
                        group_questions.append(questions[num - 1])
                
                if group_questions:
                    result[group_name] = group_questions
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse grouping response: {e}")
            self.logger.error(f"Response: {response}")
            
            # Fallback: each question as its own group
            return {f"group_{i}": [q] for i, q in enumerate(questions)}
    
    def _map_questions_to_groups(self, questions: List[PollingQuestion], 
                                question_groups: Dict[str, List[str]]) -> Dict[str, List[PollingQuestion]]:
        """Map original questions to their assigned groups."""
        # Create mapping from question text to group
        text_to_group = {}
        for group_id, group_questions in question_groups.items():
            for question_text in group_questions:
                text_to_group[question_text.strip().lower()] = group_id
        
        # Group original questions
        grouped_questions = defaultdict(list)
        for question in questions:
            normalized_text = question.question_text.strip().lower()
            group_id = text_to_group.get(normalized_text, f"ungrouped_{len(grouped_questions)}")
            grouped_questions[group_id].append(question)
        
        return dict(grouped_questions)
    
    def create_group_labels_dataframe(self, grouped_questions: Dict[str, List[PollingQuestion]]) -> pd.DataFrame:
        """Create a DataFrame mapping questions to their group labels."""
        data = []
        
        for group_id, questions in grouped_questions.items():
            for question in questions:
                data.append({
                    'question_text': question.question_text,
                    'question_group': group_id,
                    'group_size': len(questions),
                    'survey_organisation': question.survey_organisation,
                    'country': question.country,
                    'source_file': question.source_file
                })
        
        df = pd.DataFrame(data)
        
        # Add summary statistics
        group_stats = df.groupby('question_group').agg({
            'question_text': 'count',
            'survey_organisation': 'nunique',
            'country': 'nunique'
        }).rename(columns={
            'question_text': 'total_questions',
            'survey_organisation': 'unique_organizations',
            'country': 'unique_countries'
        })
        
        # Merge back with main data
        df = df.merge(group_stats, left_on='question_group', right_index=True, suffixes=('', '_stats'))
        
        return df
    
    def validate_groupings(self, grouped_questions: Dict[str, List[PollingQuestion]]) -> Dict[str, any]:
        """Validate the quality of question groupings."""
        validation_report = {
            'total_groups': len(grouped_questions),
            'total_questions': sum(len(questions) for questions in grouped_questions.values()),
            'group_sizes': {},
            'large_groups': [],
            'singleton_groups': [],
            'category_consistency': {}
        }
        
        # Analyze group sizes
        for group_id, questions in grouped_questions.items():
            group_size = len(questions)
            validation_report['group_sizes'][group_id] = group_size
            
            if group_size > 10:
                validation_report['large_groups'].append((group_id, group_size))
            elif group_size == 1:
                validation_report['singleton_groups'].append(group_id)
        
        # Check category consistency within groups
        for group_id, questions in grouped_questions.items():
            categories = set(q.category for q in questions)
            validation_report['category_consistency'][group_id] = {
                'categories': list(categories),
                'is_consistent': len(categories) == 1
            }
        
        return validation_report
    
    def export_groupings_to_csv(self, grouped_questions: Dict[str, List[PollingQuestion]], 
                               output_path: str) -> None:
        """Export question groupings to CSV file."""
        df = self.create_group_labels_dataframe(grouped_questions)
        df.to_csv(output_path, index=False)
        self.logger.info(f"✅ Exported question groupings to {output_path}")
    
    def get_grouping_summary(self, grouped_questions: Dict[str, List[PollingQuestion]]) -> Dict[str, any]:
        """Get summary statistics for question groupings."""
        group_sizes = [len(questions) for questions in grouped_questions.values()]
        
        return {
            'total_groups': len(grouped_questions),
            'total_questions': sum(group_sizes),
            'avg_group_size': sum(group_sizes) / len(group_sizes) if group_sizes else 0,
            'largest_group_size': max(group_sizes) if group_sizes else 0,
            'smallest_group_size': min(group_sizes) if group_sizes else 0,
            'singleton_groups': sum(1 for size in group_sizes if size == 1),
            'large_groups': sum(1 for size in group_sizes if size > 10)
        }