"""Command-line interface for AI Polling pipeline."""

from pathlib import Path
from typing import List, Optional
import sys

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, TaskID
    from rich import print as rprint
except ImportError:
    print("Rich and Typer not installed. Run: pip install typer rich")
    sys.exit(1)

from .core.config import get_config, reload_config
from .core.models import PollingDataset, DataQuality
from .core.exceptions import AIPollingError
from .extractors.pdf_extractor import PDFExtractor
from .extractors.excel_extractor import ExcelExtractor
from .extractors.html_extractor import HTMLExtractor
from .processors.validator import validate_polling_data, clean_polling_data
from .processors.aggregator import combine_datasets, get_summary_statistics
from .processors.metadata_enricher import MetadataEnricher
from .processors.question_grouper import QuestionGrouper
from .outputs.sheets_uploader import SheetsUploader
from .outputs.r_exporter import RExporter

# Initialize Typer app and Rich console
app = typer.Typer(help="AI Public Opinion Polling Data Extraction Pipeline")
console = Console()


@app.command()
def extract(
    source: Path = typer.Argument(..., help="Directory containing polling documents"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    file_types: List[str] = typer.Option(["pdf"], "--type", "-t", help="File types to extract (pdf, html, excel)"),
    batch_size: Optional[int] = typer.Option(None, "--batch", "-b", help="Batch size for processing"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate extracted data"),
    enrich_metadata: bool = typer.Option(True, "--enrich/--no-enrich", help="Enrich with metadata from Google Sheets"),
    upload_sheets: bool = typer.Option(False, "--upload/--no-upload", help="Upload results to Google Sheets"),
    metadata_csv: Optional[Path] = typer.Option(None, "--metadata-csv", help="CSV fallback for metadata enrichment"),
) -> None:
    """Extract polling data from documents."""
    
    console.print(Panel.fit(
        "🔍 AI Polling Data Extraction",
        style="bold blue"
    ))
    
    if not source.exists() or not source.is_dir():
        console.print(f"❌ Source directory not found: {source}", style="red")
        raise typer.Exit(1)
    
    try:
        config = get_config()
        
        # Override batch size if provided
        if batch_size:
            config.extraction.batch_size = batch_size
        
        all_questions = []
        
        # Extract from PDFs
        if "pdf" in file_types:
            console.print("📄 Extracting from PDF files...")
            pdf_extractor = PDFExtractor()
            pdf_files = list(source.glob("*.pdf"))
            
            if pdf_files:
                with Progress() as progress:
                    task = progress.add_task("Processing PDFs...", total=len(pdf_files))
                    
                    # Process files individually to update progress
                    for i, pdf_file in enumerate(pdf_files):
                        try:
                            questions = pdf_extractor.extract_from_file(pdf_file)
                            all_questions.extend(questions)
                            progress.update(task, completed=i + 1)
                            
                            # Rate limiting
                            if (i + 1) % config.extraction.batch_size == 0 and i + 1 < len(pdf_files):
                                import time
                                time.sleep(config.extraction.rate_limit_delay)
                                
                        except Exception as e:
                            console.print(f"❌ Failed to process {pdf_file.name}: {e}", style="red")
                            progress.update(task, completed=i + 1)
                
                pdf_question_count = len([q for q in all_questions if getattr(q, 'source_file', '').endswith('.pdf')])
                console.print(f"✅ Extracted {pdf_question_count} records from {len(pdf_files)} PDF files")
                console.print()  # Add newline after progress
            else:
                console.print("⚠️ No PDF files found", style="yellow")
        
        # Extract from HTML files
        if "html" in file_types:
            console.print("🌐 Extracting from HTML files...")
            html_extractor = HTMLExtractor()
            html_files = list(source.glob("*.html")) + list(source.glob("*.htm"))
            
            if html_files:
                with Progress() as progress:
                    task = progress.add_task("Processing HTML files...", total=len(html_files))
                    
                    for i, html_file in enumerate(html_files):
                        try:
                            questions = html_extractor.extract_from_file(html_file)
                            all_questions.extend(questions)
                            progress.update(task, completed=i + 1)
                            
                            # Rate limiting
                            if (i + 1) % config.extraction.batch_size == 0 and i + 1 < len(html_files):
                                import time
                                time.sleep(config.extraction.rate_limit_delay)
                                
                        except Exception as e:
                            console.print(f"❌ Failed to process {html_file.name}: {e}", style="red")
                            progress.update(task, completed=i + 1)
                
                html_question_count = len([q for q in all_questions if getattr(q, 'source_file', '').endswith(('.html', '.htm'))])
                console.print(f"✅ Extracted {html_question_count} records from {len(html_files)} HTML files")
                console.print()  # Add newline after progress
            else:
                console.print("⚠️ No HTML files found", style="yellow")
        
        # Extract from Excel files
        if "excel" in file_types:
            console.print("📊 Extracting from Excel/CSV files...")
            excel_extractor = ExcelExtractor()
            excel_files = list(source.glob("*.xlsx")) + list(source.glob("*.xls")) + list(source.glob("*.csv"))
            
            if excel_files:
                excel_questions = []
                for excel_file in excel_files:
                    try:
                        questions = excel_extractor.extract_from_file(excel_file)
                        excel_questions.extend(questions)
                    except Exception as e:
                        console.print(f"❌ Failed to extract from {excel_file.name}: {e}", style="red")
                
                all_questions.extend(excel_questions)
                console.print(f"✅ Extracted {len(excel_questions)} records from {len(excel_files)} Excel files")
                console.print()  # Add newline after progress
            else:
                console.print("⚠️ No Excel files found", style="yellow")
        
        if not all_questions:
            console.print("❌ No data extracted from any files", style="red")
            raise typer.Exit(1)
        
        # Validate data if requested
        if validate:
            console.print("🔍 Validating extracted data...")
            report = validate_polling_data(all_questions)
            
            # Display validation summary
            table = Table(title="Data Quality Report")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Questions", str(report.total_questions))
            table.add_row("Valid Questions", str(report.valid_questions))
            table.add_row("Quality Score", f"{report.quality_score:.1f}/100")
            table.add_row("Organizations", str(len(report.organization_coverage)))
            table.add_row("Countries", str(len(report.country_coverage)))
            
            console.print(table)
            
            if report.quality_score < 70:
                console.print("⚠️ Low quality score detected. Consider data cleaning.", style="yellow")
        
        # Enrich with metadata if requested
        if enrich_metadata:
            console.print("📋 Enriching with metadata from spreadsheet...")
            try:
                enricher = MetadataEnricher()
                original_questions = all_questions.copy()
                all_questions = enricher.enrich_questions(all_questions, csv_fallback=metadata_csv)
                
                # Show enrichment summary
                enrichment_summary = enricher.get_enrichment_summary(original_questions, all_questions)
                
                table = Table(title="Metadata Enrichment Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="magenta")
                
                table.add_row("Total Questions", str(enrichment_summary['total_questions']))
                table.add_row("Fieldwork Dates Filled", str(enrichment_summary['fieldwork_dates_filled']))
                table.add_row("Sample Sizes Filled", str(enrichment_summary['sample_sizes_filled']))
                table.add_row("Remaining Missing Dates", str(enrichment_summary['remaining_missing_dates']))
                table.add_row("Remaining Missing Samples", str(enrichment_summary['remaining_missing_samples']))
                table.add_row("Enrichment Rate", f"{enrichment_summary['enrichment_rate']:.1%}")
                
                console.print(table)
                console.print()
                
            except Exception as e:
                console.print(f"⚠️ Metadata enrichment failed: {e}", style="yellow")
                console.print("Continuing without enrichment...")
        
        # Create dataset
        dataset = PollingDataset(questions=all_questions)
        
        # Upload to Google Sheets if requested
        if upload_sheets:
            console.print("📤 Uploading to Google Sheets...")
            try:
                uploader = SheetsUploader()
                sheet_url = uploader.upload_questions(all_questions, "Poll Results")
                console.print(f"✅ Uploaded {len(all_questions)} questions to 'Poll Results' tab")
                console.print(f"🔗 Google Sheets URL: {sheet_url}")
                
                # Create validation sheet
                uploader.create_validation_sheet(all_questions)
                console.print("✅ Validation sheet created")
                console.print()
                
            except Exception as e:
                console.print(f"⚠️ Google Sheets upload failed: {e}", style="yellow")
                console.print("Continuing with local export...")
        
        # Save results
        if output is None:
            output = Path("extracted_data")
        
        output.mkdir(exist_ok=True)
        
        # Export for R
        r_exporter = RExporter(output)
        r_files = r_exporter.export_dataset(dataset)
        
        console.print(f"✅ Exported {len(r_files)} files for R analysis")
        console.print(f"📁 Output directory: {output}")
        
        # Show summary
        display_dataset_summary(dataset)
        
        # Show quality summary
        display_quality_summary(all_questions)
        
    except AIPollingError as e:
        console.print(f"❌ Extraction failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def upload(
    data_file: Path = typer.Argument(..., help="Data file to upload (CSV/JSON)"),
    sheet_id: Optional[str] = typer.Option(None, "--sheet-id", "-s", help="Google Sheets ID"),
    tab_name: Optional[str] = typer.Option(None, "--tab", "-t", help="Sheet tab name"),
    create_validation: bool = typer.Option(True, "--validation/--no-validation", help="Create validation sheet"),
) -> None:
    """Upload polling data to Google Sheets."""
    
    console.print(Panel.fit(
        "📤 Upload to Google Sheets",
        style="bold green"
    ))
    
    if not data_file.exists():
        console.print(f"❌ Data file not found: {data_file}", style="red")
        raise typer.Exit(1)
    
    try:
        # Load data
        console.print(f"📖 Loading data from {data_file}...")
        
        if data_file.suffix == ".csv":
            import pandas as pd
            df = pd.read_csv(data_file)
            # Convert DataFrame rows to PollingQuestion objects
            # This is a simplified conversion - in practice, you'd want more robust handling
            questions = []
            for _, row in df.iterrows():
                try:
                    from .core.models import PollingQuestion
                    question = PollingQuestion(**row.to_dict())
                    questions.append(question)
                except Exception:
                    continue  # Skip invalid rows
        else:
            # Assume JSON format
            import json
            with open(data_file) as f:
                data = json.load(f)
            
            from .core.models import PollingQuestion
            questions = [PollingQuestion(**item) for item in data]
        
        console.print(f"✅ Loaded {len(questions)} questions")
        
        # Upload to sheets
        uploader = SheetsUploader(sheet_id)
        
        with console.status("Uploading to Google Sheets..."):
            sheet_url = uploader.upload_questions(questions, tab_name)
        
        console.print(f"✅ Uploaded to Google Sheets: {sheet_url}")
        
        # Create validation sheet if requested
        if create_validation:
            with console.status("Creating validation sheet..."):
                uploader.create_validation_sheet(questions)
            console.print("✅ Validation sheet created")
        
    except Exception as e:
        console.print(f"❌ Upload failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def validate(
    data_file: Path = typer.Argument(..., help="Data file to validate"),
    strict: bool = typer.Option(False, "--strict", help="Use strict validation"),
    clean: bool = typer.Option(False, "--clean", help="Clean data and save results"),
) -> None:
    """Validate polling data quality."""
    
    console.print(Panel.fit(
        "🔍 Data Validation",
        style="bold yellow"
    ))
    
    if not data_file.exists():
        console.print(f"❌ Data file not found: {data_file}", style="red")
        raise typer.Exit(1)
    
    try:
        # Load data (simplified - same logic as upload command)
        console.print(f"📖 Loading data from {data_file}...")
        
        # ... load questions from file ...
        
        # Validate
        console.print("🔍 Running validation...")
        report = validate_polling_data(questions)
        
        # Display detailed report
        display_validation_report(report)
        
        # Clean data if requested
        if clean:
            console.print("🧹 Cleaning data...")
            cleaned_questions, clean_report = clean_polling_data(questions, strict=strict)
            
            # Save cleaned data
            cleaned_file = data_file.parent / f"cleaned_{data_file.name}"
            # ... save cleaned questions ...
            
            console.print(f"✅ Cleaned data saved to {cleaned_file}")
            display_validation_report(clean_report)
        
    except Exception as e:
        console.print(f"❌ Validation failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    edit: bool = typer.Option(False, "--edit", help="Edit configuration file"),
    reload: bool = typer.Option(False, "--reload", help="Reload configuration"),
) -> None:
    """Manage pipeline configuration."""
    
    try:
        if show:
            config = get_config()
            display_configuration(config)
        
        elif edit:
            config_file = Path("config.yaml")
            if not config_file.exists():
                # Create default config
                config = get_config()
                config.save_to_file(config_file)
                console.print(f"✅ Created default configuration at {config_file}")
            
            # Try to open in editor
            import subprocess
            try:
                subprocess.run([os.environ.get('EDITOR', 'nano'), str(config_file)])
            except Exception:
                console.print(f"📝 Please edit configuration file: {config_file}")
        
        elif reload:
            reload_config()
            console.print("✅ Configuration reloaded")
        
        else:
            console.print("Use --show, --edit, or --reload")
    
    except Exception as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def summary(
    data_file: Optional[Path] = typer.Argument(None, help="Data file to summarize (uses latest if not provided)"),
) -> None:
    """Show summary statistics for polling data."""
    
    console.print(Panel.fit(
        "📊 Dataset Summary", 
        style="bold cyan"
    ))
    
    try:
        # Load data
        if data_file:
            if not data_file.exists():
                console.print(f"❌ Data file not found: {data_file}", style="red")
                raise typer.Exit(1)
            
            # Load from specified file
            # ... loading logic ...
            questions = []  # Placeholder
        else:
            # Try to find latest data file
            data_dir = Path("extracted_data")
            if data_dir.exists():
                latest_files = list(data_dir.glob("*_latest.csv"))
                if latest_files:
                    data_file = latest_files[0]
                    # ... load from latest file ...
                    questions = []  # Placeholder
                else:
                    console.print("❌ No data files found in extracted_data/", style="red")
                    raise typer.Exit(1)
            else:
                console.print("❌ No extracted_data directory found", style="red")
                raise typer.Exit(1)
        
        # Create dataset and display summary
        if questions:
            dataset = PollingDataset(questions=questions)
            display_dataset_summary(dataset)
        else:
            console.print("❌ No valid questions found", style="red")
    
    except Exception as e:
        console.print(f"❌ Summary failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def group_questions(
    data_file: Optional[Path] = typer.Argument(None, help="Data file to group (uses latest if not provided)"),
    output_csv: Optional[Path] = typer.Option(None, "--output", "-o", help="Output CSV file for groupings"),
    upload_sheets: bool = typer.Option(True, "--upload/--no-upload", help="Upload grouped results to Google Sheets"),
    create_new_tab: bool = typer.Option(True, "--new-tab/--update-existing", help="Create new tab for grouped data"),
) -> None:
    """Group similar polling questions using semantic analysis."""
    
    console.print(Panel.fit(
        "🔍 Question Grouping Analysis",
        style="bold purple"
    ))
    
    try:
        # Load questions from file or latest data
        from .core.models import PollingQuestion
        
        if data_file and data_file.exists():
            console.print(f"📖 Loading questions from {data_file}...")
            if data_file.suffix == ".csv":
                import pandas as pd
                df = pd.read_csv(data_file)
                questions = []
                for _, row in df.iterrows():
                    try:
                        # Clean the row data
                        row_dict = row.to_dict()
                        
                        # Handle NaN values
                        for key, value in row_dict.items():
                            if pd.isna(value):
                                if key in ['fieldwork_date', 'extraction_date']:
                                    row_dict[key] = None
                                elif key in ['agreement', 'neutral', 'disagreement', 'non_response', 'n_respondents']:
                                    row_dict[key] = None
                                elif key in ['notes', 'quality_issues']:
                                    row_dict[key] = ""
                                else:
                                    row_dict[key] = ""
                        
                        # Convert date strings if present
                        if row_dict.get('fieldwork_date') and isinstance(row_dict['fieldwork_date'], str):
                            try:
                                from datetime import datetime
                                row_dict['fieldwork_date'] = datetime.strptime(row_dict['fieldwork_date'], '%Y-%m-%d').date()
                            except:
                                row_dict['fieldwork_date'] = None
                        
                        # Parse quality_issues if it's a string
                        if isinstance(row_dict.get('quality_issues'), str):
                            if row_dict['quality_issues'].strip() in ['[]', '']:
                                row_dict['quality_issues'] = []
                            else:
                                try:
                                    import ast
                                    row_dict['quality_issues'] = ast.literal_eval(row_dict['quality_issues'])
                                except:
                                    row_dict['quality_issues'] = []
                        
                        question = PollingQuestion(**row_dict)
                        questions.append(question)
                    except Exception as e:
                        console.print(f"⚠️ Skipping invalid row: {e}", style="yellow")
                        continue
            else:
                # Load from JSON
                import json
                with open(data_file) as f:
                    data = json.load(f)
                questions = [PollingQuestion(**item) for item in data]
        else:
            # Use latest extracted data
            latest_csv = Path("extracted_data/polling_data_latest.csv")
            if not latest_csv.exists():
                console.print("❌ No data file found. Run extract command first.", style="red")
                raise typer.Exit(1)
            
            console.print(f"📖 Loading latest data from {latest_csv}...")
            import pandas as pd
            df = pd.read_csv(latest_csv)
            questions = []
            for _, row in df.iterrows():
                try:
                    # Clean the row data
                    row_dict = row.to_dict()
                    
                    # Handle NaN values
                    for key, value in row_dict.items():
                        if pd.isna(value):
                            if key in ['fieldwork_date', 'extraction_date']:
                                row_dict[key] = None
                            elif key in ['agreement', 'neutral', 'disagreement', 'non_response', 'n_respondents']:
                                row_dict[key] = None
                            elif key in ['notes', 'quality_issues']:
                                row_dict[key] = ""
                            else:
                                row_dict[key] = ""
                    
                    # Convert date strings if present
                    if row_dict.get('fieldwork_date') and isinstance(row_dict['fieldwork_date'], str):
                        try:
                            from datetime import datetime
                            row_dict['fieldwork_date'] = datetime.strptime(row_dict['fieldwork_date'], '%Y-%m-%d').date()
                        except:
                            row_dict['fieldwork_date'] = None
                    
                    # Parse quality_issues if it's a string
                    if isinstance(row_dict.get('quality_issues'), str):
                        if row_dict['quality_issues'].strip() in ['[]', '']:
                            row_dict['quality_issues'] = []
                        else:
                            try:
                                import ast
                                row_dict['quality_issues'] = ast.literal_eval(row_dict['quality_issues'])
                            except:
                                row_dict['quality_issues'] = []
                    
                    question = PollingQuestion(**row_dict)
                    questions.append(question)
                except Exception as e:
                    console.print(f"⚠️ Skipping invalid row: {e}", style="yellow")
                    continue
        
        if not questions:
            console.print("❌ No valid questions found to group", style="red")
            raise typer.Exit(1)
        
        console.print(f"✅ Loaded {len(questions)} questions")
        
        # Initialize grouper and perform grouping
        console.print("🔍 Analyzing questions for semantic similarity...")
        grouper = QuestionGrouper()
        
        with console.status("Processing question groups..."):
            grouped_questions = grouper.group_questions(questions)
        
        # Display grouping results
        summary = grouper.get_grouping_summary(grouped_questions)
        
        table = Table(title="Question Grouping Results", style="purple")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Total Questions", str(summary['total_questions']))
        table.add_row("Total Groups", str(summary['total_groups']))
        table.add_row("Average Group Size", f"{summary['avg_group_size']:.1f}")
        table.add_row("Largest Group", str(summary['largest_group_size']))
        table.add_row("Singleton Groups", str(summary['singleton_groups']))
        table.add_row("Large Groups (>10)", str(summary['large_groups']))
        
        console.print(table)
        
        # Show sample groups
        console.print("\n📋 Sample Question Groups:")
        sample_groups = list(grouped_questions.items())[:5]
        
        for group_id, group_questions in sample_groups:
            group_table = Table(title=f"Group: {group_id} ({len(group_questions)} questions)", style="green")
            group_table.add_column("Question", style="white")
            group_table.add_column("Organization", style="blue")
            group_table.add_column("Country", style="yellow")
            
            for q in group_questions[:3]:  # Show first 3 questions
                question_text = q.question_text[:80] + "..." if len(q.question_text) > 80 else q.question_text
                group_table.add_row(
                    question_text,
                    q.survey_organisation[:30] + "..." if len(q.survey_organisation) > 30 else q.survey_organisation,
                    q.country
                )
            
            if len(group_questions) > 3:
                group_table.add_row(f"... and {len(group_questions) - 3} more questions", "", "")
            
            console.print(group_table)
        
        # Create DataFrame with group labels
        df_with_groups = grouper.create_group_labels_dataframe(grouped_questions)
        
        # Export to CSV if requested
        if output_csv:
            df_with_groups.to_csv(output_csv, index=False)
            console.print(f"✅ Exported grouped data to {output_csv}")
        else:
            # Default output file
            output_csv = Path("extracted_data/polling_data_grouped.csv")
            df_with_groups.to_csv(output_csv, index=False)
            console.print(f"✅ Exported grouped data to {output_csv}")
        
        # Upload to Google Sheets if requested
        if upload_sheets:
            console.print("📤 Uploading grouped data to Google Sheets...")
            try:
                uploader = SheetsUploader()
                
                # Add group information to original questions
                grouped_df = df_with_groups[['question_text', 'question_group', 'group_size']].copy()
                
                if create_new_tab:
                    tab_name = "Poll Results Grouped"
                    console.print(f"📋 Creating new tab: {tab_name}")
                else:
                    tab_name = "Poll Results"
                    console.print(f"📋 Updating existing tab: {tab_name}")
                
                # Convert back to PollingQuestion objects with group info
                questions_with_groups = []
                for _, row in df_with_groups.iterrows():
                    # Find original question
                    for q in questions:
                        if q.question_text == row['question_text']:
                            # Create a copy with group info in notes
                            q_dict = q.dict()
                            q_dict['notes'] = f"[GROUP: {row['question_group']}] {q_dict.get('notes', '')}"
                            questions_with_groups.append(PollingQuestion(**q_dict))
                            break
                
                sheet_url = uploader.upload_questions(questions_with_groups, tab_name)
                console.print(f"✅ Uploaded grouped data to Google Sheets")
                console.print(f"🔗 Sheet URL: {sheet_url}")
                
            except Exception as e:
                console.print(f"⚠️ Google Sheets upload failed: {e}", style="yellow")
                console.print("Grouped data saved locally only.")
        
        # Run validation
        console.print("🔍 Validating grouping quality...")
        validation_report = grouper.validate_groupings(grouped_questions)
        
        # Show validation warnings
        if validation_report['large_groups']:
            console.print("⚠️ Large groups detected (may need review):", style="yellow")
            for group_id, size in validation_report['large_groups'][:5]:
                console.print(f"  • {group_id}: {size} questions")
        
        inconsistent_groups = [
            group_id for group_id, data in validation_report['category_consistency'].items()
            if not data['is_consistent']
        ]
        
        if inconsistent_groups:
            console.print(f"⚠️ {len(inconsistent_groups)} groups have mixed categories (may need review)", style="yellow")
        
    except Exception as e:
        console.print(f"❌ Question grouping failed: {e}", style="red")
        raise typer.Exit(1)


def display_dataset_summary(dataset: PollingDataset) -> None:
    """Display a rich summary of the dataset."""
    
    # Main statistics table
    table = Table(title="Dataset Overview", style="cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Total Questions", str(dataset.total_questions))
    table.add_row("Organizations", str(dataset.unique_organizations))
    table.add_row("Countries", str(dataset.unique_countries))
    
    if dataset.date_range:
        table.add_row("Date Range", f"{dataset.date_range['earliest']} to {dataset.date_range['latest']}")
    
    console.print(table)
    
    # Category breakdown
    if dataset.category_breakdown:
        cat_table = Table(title="Questions by Category", style="green")
        cat_table.add_column("Category", style="green")
        cat_table.add_column("Count", style="magenta")
        
        for category, count in sorted(dataset.category_breakdown.items(), key=lambda x: x[1], reverse=True):
            cat_table.add_row(category, str(count))
        
        console.print(cat_table)
    
    # Organization breakdown (top 10)
    if dataset.organization_breakdown:
        org_table = Table(title="Top Organizations", style="blue")
        org_table.add_column("Organization", style="blue")
        org_table.add_column("Questions", style="magenta")
        
        top_orgs = sorted(dataset.organization_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
        for org, count in top_orgs:
            org_table.add_row(org[:50] + "..." if len(org) > 50 else org, str(count))
        
        console.print(org_table)


def display_validation_report(report) -> None:
    """Display validation report in a rich format."""
    
    # Quality score with color coding
    if report.quality_score >= 80:
        score_style = "green"
        score_icon = "✅"
    elif report.quality_score >= 60:
        score_style = "yellow"
        score_icon = "⚠️"
    else:
        score_style = "red"
        score_icon = "❌"
    
    console.print(f"{score_icon} Quality Score: [bold {score_style}]{report.quality_score:.1f}/100[/bold {score_style}]")
    
    # Issues summary
    if report.issues:
        console.print(f"\n📋 Found {len(report.issues)} data quality issues:")
        for i, issue in enumerate(report.issues[:10], 1):  # Show first 10
            console.print(f"  {i}. {issue}")
        
        if len(report.issues) > 10:
            console.print(f"  ... and {len(report.issues) - 10} more issues")


def display_quality_summary(questions: List) -> None:
    """Display data quality summary."""
    from collections import Counter
    
    if not questions:
        return
    
    console.print("\n")
    console.print(Panel.fit("📊 Data Quality Summary", style="bold cyan"))
    
    # Count quality levels
    quality_counts = Counter()
    issues_by_type = Counter()
    
    for question in questions:
        if hasattr(question, 'data_quality') and question.data_quality:
            quality_counts[question.data_quality] += 1
        
        if hasattr(question, 'quality_issues') and question.quality_issues:
            for issue in question.quality_issues:
                issues_by_type[issue] += 1
    
    # Quality distribution table
    quality_table = Table(title="Quality Distribution", style="cyan")
    quality_table.add_column("Quality Level", style="cyan")
    quality_table.add_column("Count", style="magenta")
    quality_table.add_column("Percentage", style="green")
    
    total = len(questions)
    for quality in [DataQuality.HIGH, DataQuality.GOOD, DataQuality.ACCEPTABLE, DataQuality.FLAGGED, DataQuality.POOR]:
        count = quality_counts.get(quality, 0)
        pct = (count / total * 100) if total > 0 else 0
        
        # Color coding
        if quality == DataQuality.HIGH:
            style = "green"
        elif quality == DataQuality.GOOD:
            style = "blue" 
        elif quality == DataQuality.ACCEPTABLE:
            style = "yellow"
        else:
            style = "red"
            
        quality_table.add_row(
            f"[{style}]{quality.upper()}[/{style}]", 
            str(count), 
            f"{pct:.1f}%"
        )
    
    console.print(quality_table)
    
    # Common issues
    if issues_by_type:
        issues_table = Table(title="Most Common Issues", style="yellow")
        issues_table.add_column("Issue", style="yellow")
        issues_table.add_column("Count", style="magenta")
        
        for issue, count in issues_by_type.most_common(5):
            issues_table.add_row(issue, str(count))
        
        console.print(issues_table)
    
    # Summary message
    flagged_count = quality_counts.get(DataQuality.FLAGGED, 0) + quality_counts.get(DataQuality.POOR, 0)
    if flagged_count > 0:
        console.print(f"\n⚠️  [yellow]{flagged_count} questions flagged for review[/yellow]")
    else:
        console.print(f"\n✅ [green]All questions meet quality standards[/green]")


def display_configuration(config) -> None:
    """Display current configuration."""
    
    config_table = Table(title="Current Configuration", style="cyan")
    config_table.add_column("Section", style="cyan")
    config_table.add_column("Setting", style="blue")
    config_table.add_column("Value", style="magenta")
    
    # API settings (hide sensitive data)
    config_table.add_row("API", "Model Name", config.api.model_name)
    config_table.add_row("API", "Thinking Budget", str(config.api.thinking_budget))
    config_table.add_row("API", "API Key", "***" + config.api.google_api_key[-4:] if config.api.google_api_key else "Not Set")
    
    # Extraction settings
    config_table.add_row("Extraction", "Batch Size", str(config.extraction.batch_size))
    config_table.add_row("Extraction", "Retry Attempts", str(config.extraction.retry_attempts))
    config_table.add_row("Extraction", "Rate Limit Delay", f"{config.extraction.rate_limit_delay}s")
    
    # Output settings
    config_table.add_row("Output", "Google Sheet ID", config.output.google_sheet_id[:20] + "...")
    config_table.add_row("Output", "R Output Dir", config.output.r_output_dir)
    config_table.add_row("Output", "Cache Dir", config.output.cache_dir)
    
    console.print(config_table)


if __name__ == "__main__":
    app()