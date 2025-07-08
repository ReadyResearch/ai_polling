"""Google Sheets upload functionality."""

import pandas as pd
from typing import List, Optional
from datetime import datetime
from pathlib import Path

try:
    import gspread
    from google.auth import default
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None

from ..core.models import PollingQuestion, PollingDataset
from ..core.config import get_config
from ..core.exceptions import SheetsUploadError
from ..core.logger import get_logger


class SheetsUploader:
    """Upload polling data to Google Sheets."""
    
    def __init__(self, sheet_id: Optional[str] = None):
        """Initialize sheets uploader.
        
        Args:
            sheet_id: Google Sheets ID (uses config default if not provided)
        """
        if gspread is None:
            raise SheetsUploadError("gspread not installed. Run: pip install gspread google-auth")
        
        self.config = get_config()
        self.sheet_id = sheet_id or self.config.output.google_sheet_id
        self.logger = get_logger(__name__)
        
        # Initialize Google Sheets client
        self._client = None
    
    def _get_client(self):
        """Get authenticated Google Sheets client."""
        if self._client is None:
            try:
                # Try service account authentication first
                service_account_path = Path.home() / ".config/gspread/service_account.json"
                if service_account_path.exists():
                    self.logger.info("🔑 Using service account authentication for Google Sheets")
                    creds = Credentials.from_service_account_file(
                        str(service_account_path),
                        scopes=[
                            'https://www.googleapis.com/auth/spreadsheets',
                            'https://www.googleapis.com/auth/drive'
                        ]
                    )
                    self._client = gspread.authorize(creds)
                    return self._client
                
                # Fallback to OAuth
                oauth_creds_path = Path.home() / ".config/gspread/credentials.json"
                if oauth_creds_path.exists():
                    self.logger.info("🔑 Using OAuth authentication for Google Sheets")
                    self._client = gspread.oauth()
                    return self._client
                
                # Try default credentials
                creds, _ = default()
                self._client = gspread.authorize(creds)
                
            except Exception as e:
                raise SheetsUploadError(f"Failed to authenticate with Google Sheets: {e}")
        
        return self._client
    
    def upload_dataset(self, dataset: PollingDataset, tab_name: Optional[str] = None) -> str:
        """Upload a complete dataset to Google Sheets.
        
        Args:
            dataset: PollingDataset to upload
            tab_name: Sheet tab name (uses config default if not provided)
            
        Returns:
            URL to the uploaded sheet
            
        Raises:
            SheetsUploadError: If upload fails
        """
        return self.upload_questions(dataset.questions, tab_name)
    
    def upload_questions(self, questions: List[PollingQuestion], tab_name: Optional[str] = None) -> str:
        """Upload questions to Google Sheets.
        
        Args:
            questions: List of PollingQuestion objects
            tab_name: Sheet tab name
            
        Returns:
            URL to the uploaded sheet
        """
        if not questions:
            raise SheetsUploadError("No questions to upload")
        
        tab_name = tab_name or self.config.output.sheet_tab_name
        
        self.logger.info(f"Uploading {len(questions)} questions to Google Sheets...")
        
        try:
            # Convert to DataFrame
            df = self._questions_to_dataframe(questions)
            
            # Get Google Sheets client and open spreadsheet
            client = self._get_client()
            spreadsheet = client.open_by_key(self.sheet_id)
            
            # Clear existing data and upload new data
            self._upload_dataframe_to_sheet(spreadsheet, df, tab_name)
            
            # Create summary sheet
            summary_df = self._create_summary_dataframe(questions)
            self._upload_dataframe_to_sheet(spreadsheet, summary_df, f"{tab_name} Summary")
            
            sheet_url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
            self.logger.info(f"✅ Successfully uploaded to Google Sheets: {sheet_url}")
            
            return sheet_url
            
        except Exception as e:
            raise SheetsUploadError(f"Failed to upload to Google Sheets: {e}")
    
    def _questions_to_dataframe(self, questions: List[PollingQuestion]) -> pd.DataFrame:
        """Convert questions to pandas DataFrame."""
        data = []
        
        for question in questions:
            # Convert to dict and flatten
            question_dict = question.dict()
            
            # Convert enum to string
            question_dict['category'] = question_dict['category']
            
            # Convert lists to strings for Google Sheets compatibility
            if 'quality_issues' in question_dict and question_dict['quality_issues']:
                question_dict['quality_issues'] = '; '.join(question_dict['quality_issues'])
            
            # Format dates
            if question_dict.get('fieldwork_date'):
                question_dict['fieldwork_date'] = question_dict['fieldwork_date'].strftime('%Y-%m-%d')
            
            if question_dict.get('extraction_date'):
                question_dict['extraction_date'] = question_dict['extraction_date'].strftime('%Y-%m-%d %H:%M:%S')
            
            data.append(question_dict)
        
        df = pd.DataFrame(data)
        
        # Handle NaN values that cause JSON serialization issues
        df = df.fillna('')  # Replace NaN with empty strings
        
        # Convert any remaining float NaN to None for numeric columns
        numeric_columns = ['agreement', 'neutral', 'disagreement', 'non_response', 'n_respondents']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].where(pd.notna(df[col]), None)
        
        # Reorder columns for better readability
        column_order = [
            'question_text', 'category', 'survey_organisation', 'country',
            'fieldwork_date', 'agreement', 'neutral', 'disagreement', 'non_response',
            'n_respondents', 'response_scale', 'notes', 'source_file',
            'extraction_date', 'data_quality', 'quality_issues'
        ]
        
        # Only include columns that exist in the DataFrame
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]
        
        return df
    
    def _create_summary_dataframe(self, questions: List[PollingQuestion]) -> pd.DataFrame:
        """Create summary statistics DataFrame."""
        from ..processors.aggregator import get_summary_statistics
        
        stats = get_summary_statistics(questions)
        
        # Create summary data
        summary_data = [
            {'Metric': 'Total Questions', 'Value': stats.get('total_questions', 0)},
            {'Metric': 'Unique Organizations', 'Value': stats.get('unique_organizations', 0)},
            {'Metric': 'Unique Countries', 'Value': stats.get('unique_countries', 0)},
        ]
        
        # Add date range if available
        if stats.get('date_range'):
            date_range = stats['date_range']
            summary_data.extend([
                {'Metric': 'Earliest Survey', 'Value': date_range['earliest'].strftime('%Y-%m-%d')},
                {'Metric': 'Latest Survey', 'Value': date_range['latest'].strftime('%Y-%m-%d')},
                {'Metric': 'Date Span (days)', 'Value': date_range['span_days']},
            ])
        
        # Add agreement statistics if available
        if stats.get('agreement_statistics'):
            agree_stats = stats['agreement_statistics']
            summary_data.extend([
                {'Metric': 'Mean Agreement %', 'Value': f"{agree_stats['mean']:.1f}"},
                {'Metric': 'Median Agreement %', 'Value': f"{agree_stats['median']:.1f}"},
            ])
        
        # Add category breakdown
        if stats.get('category_breakdown'):
            summary_data.append({'Metric': '', 'Value': ''})  # Spacer
            summary_data.append({'Metric': 'CATEGORY BREAKDOWN', 'Value': ''})
            
            for category, count in stats['category_breakdown'].items():
                summary_data.append({'Metric': f"  {category}", 'Value': count})
        
        # Add timestamp
        summary_data.append({'Metric': '', 'Value': ''})  # Spacer
        summary_data.append({
            'Metric': 'Last Updated', 
            'Value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        return pd.DataFrame(summary_data)
    
    def _upload_dataframe_to_sheet(self, spreadsheet, df: pd.DataFrame, tab_name: str) -> None:
        """Upload DataFrame to a specific sheet tab."""
        try:
            # Try to get existing worksheet
            worksheet = spreadsheet.worksheet(tab_name)
            self.logger.info(f"Found existing '{tab_name}' worksheet")
        except gspread.WorksheetNotFound:
            # Create new worksheet if it doesn't exist
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=20)
            self.logger.info(f"Created new '{tab_name}' worksheet")
        
        # Clear existing content
        worksheet.clear()
        
        # Convert DataFrame to list of lists for gspread
        data = [df.columns.tolist()] + df.values.tolist()
        
        # Clean values to avoid API errors
        clean_data = []
        for row in data:
            clean_row = []
            for cell in row:
                if pd.isna(cell):
                    clean_row.append('')
                elif isinstance(cell, (list, dict)):
                    clean_row.append(str(cell))
                else:
                    clean_row.append(cell)
            clean_data.append(clean_row)
        
        # Upload data using the working method
        if clean_data:
            worksheet.update(values=clean_data, range_name='A1')
        
        # Format header row
        worksheet.format('A1:Z1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0}
        })
        
        self.logger.info(f"✅ Uploaded {len(df)} rows to '{tab_name}' tab")
    
    def create_validation_sheet(self, questions: List[PollingQuestion]) -> str:
        """Create a validation sheet highlighting potential data quality issues.
        
        Args:
            questions: List of questions to validate
            
        Returns:
            URL to the validation sheet
        """
        from ..processors.validator import validate_polling_data
        
        # Generate validation report
        report = validate_polling_data(questions)
        
        # Create validation DataFrame
        validation_data = []
        
        for i, question in enumerate(questions):
            issues = []
            
            # Check for various issues
            if question.fieldwork_date is None:
                issues.append("Missing date")
            
            if question.n_respondents is None:
                issues.append("Missing sample size")
            
            if (question.agreement is not None and 
                question.neutral is not None and 
                question.disagreement is not None):
                total = question.agreement + question.neutral + question.disagreement
                if total < 95 or total > 105:
                    issues.append(f"Percentages sum to {total:.1f}%")
            
            validation_data.append({
                'Row': i + 1,
                'Organization': question.survey_organisation,
                'Country': question.country,
                'Question': question.question_text[:100] + "..." if len(question.question_text) > 100 else question.question_text,
                'Issues': "; ".join(issues) if issues else "OK",
                'Quality_Score': "Good" if not issues else "Needs Review"
            })
        
        df = pd.DataFrame(validation_data)
        
        try:
            client = self._get_client()
            spreadsheet = client.open_by_key(self.sheet_id)
            self._upload_dataframe_to_sheet(spreadsheet, df, "Data Validation")
            
            # Color-code rows based on quality
            worksheet = spreadsheet.worksheet("Data Validation")
            
            # Highlight problematic rows
            for i, row in df.iterrows():
                if row['Quality_Score'] == "Needs Review":
                    cell_range = f'A{i+2}:F{i+2}'  # +2 because of header and 0-indexing
                    worksheet.format(cell_range, {
                        'backgroundColor': {'red': 1.0, 'green': 0.9, 'blue': 0.9}
                    })
            
            return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
            
        except Exception as e:
            raise SheetsUploadError(f"Failed to create validation sheet: {e}")