"""
Combined Image + Markdown Table Extractor with LLM Processing
Processes both table images (.png) and markdown files (.md) together for enhanced accuracy
Converts to structured JSON and CSV format
"""

# pip install openai requests python-dotenv pydantic openpyxl
import sys
import os
import json
import csv
import base64
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from openai import AzureOpenAI
from pydantic import BaseModel, Field, ValidationError
from openpyxl import Workbook
from openpyxl.styles import Alignment


# ==================== PYDANTIC MODELS ====================

class ExtractedTable(BaseModel):
    """Represents a single extracted table"""
    table_id: str = Field(..., description="Unique identifier for the table")
    table_title: Optional[str] = Field(None, description="Title or caption of the table if present")
    columns: List[str] = Field(..., description="List of all column headers in order")
    rows: List[Dict[str, str]] = Field(..., description="List of row data as dictionaries")
    row_count: Optional[int] = Field(None, description="Total number of data rows")
    column_count: Optional[int] = Field(None, description="Total number of columns")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata about the table")


class TableExtractionResponse(BaseModel):
    """Complete response containing all extracted tables"""
    tables: List[ExtractedTable] = Field(..., description="List of all tables extracted")
    source_file: Optional[str] = Field(None, description="Name of the source file")
    total_tables: Optional[int] = Field(None, description="Total number of tables found")


# ==================== CONFIGURATION ====================

# Azure OpenAI Configuration
AZURE_CONFIG = {
    "endpoint": "https://azureopenaids2025.openai.azure.com/",
    "api_version": "2024-12-01-preview",
    "deployment_name": "gpt-5",
    "subscription_key": "2c0042e00e4f418ba1af4ef6ea25ee7a"
}

# Processing Configuration
# Accept INPUT_DIRECTORY from command line argument, or use default
if len(sys.argv) > 1:
    INPUT_DIRECTORY = sys.argv[1]
else:
    INPUT_DIRECTORY = r"C:\Users\ZZ125LG\OneDrive - EY\Documents\Code_base\Task_repo\Extraction\Table Extractor\Adi_set2"

TABLE_IMAGES_FOLDER = "table_images"  # Folder containing PNG images
TABLES_FOLDER = "tables"  # Folder containing MD files


# ==================== COMPREHENSIVE EXTRACTION PROMPT ====================

COMBINED_EXTRACTION_PROMPT = """
You are an expert table data extraction system. You will receive:
1. A table IMAGE for layout and structure verification
2. A MARKDOWN table as the ground truth for data extraction

CORE PRINCIPLES:

MARKDOWN is the PRIMARY SOURCE for all data values. Extract all cell values EXACTLY as they appear in the markdown without any modification.

IMAGE is used ONLY for:
- Verifying table structure and layout
- Identifying multi-line cells that need line break separation
- Confirming column and row counts

EXTRACTION RULES:

1. COMPLETENESS
- Extract every column from left to right
- Extract every row from top to bottom
- Include all cell values without truncation
- Verify column and row counts match the image layout

2. DATA ACCURACY
- Copy all values EXACTLY from markdown
- Preserve all special characters: / - : ( ) . , % + # @ $ & * [ ] { }
- Preserve number formats: 1,234.56, (17,236), -1,234.56, $1,234.56
- CRITICAL: Keep parentheses in numbers as-is: (17,236) stays as (17,236), NOT -17,236
- Preserve date formats: 18-Dec-2024, 2024-12-18, 12/18/2024
- Preserve currency formats: $1,234.56, 162,365.50 USD, (50,673.84) USD, 0.00 USD
- Do not normalize, convert, or modify any values

3. MULTI-LINE CELLS
- If the image shows text on multiple lines within a single cell, join them with \\n
- Example: "CUSIP: 901384107" on line 1 and "ISIN: US9013841070" on line 2 becomes "CUSIP: 901384107\\nISIN: US9013841070"
- If markdown shows them merged on one line, split based on image layout

4. EMPTY CELLS
- Use empty string "" for empty cells
- Never use "N/A", "null", "None", or other placeholders

5. COLUMN HEADERS
- For multi-level headers, combine parent and child with space
- Example: "QUANTITY" over "TD" becomes "QUANTITY TD"
- Preserve exact capitalization and spacing from markdown

OUTPUT FORMAT:

Return valid JSON only:

{
  "tables": [
    {
      "table_id": "table_1",
      "table_title": "Title if present",
      "columns": ["Column1", "Column2", "Column3"],
      "rows": [
        {"Column1": "value1", "Column2": "value2", "Column3": "value3"},
        {"Column1": "value4", "Column2": "value5", "Column3": "value6"}
      ],
      "row_count": 2,
      "column_count": 3,
      "metadata": {
        "source": "markdown_with_image_verification"
      }
    }
  ],
  "source_file": "table_1",
  "total_tables": 1
}

JSON requirements:
- Valid parseable JSON
- Double quotes for strings
- Escape special characters: \\n for newline, \\" for quote, \\\\ for backslash
- No trailing commas

VALIDATION CHECKLIST:

- All columns extracted
- All rows extracted
- Multi-line cells joined with \\n
- Parentheses in numbers preserved: (17,236) NOT -17,236
- Number formats with commas and decimals preserved
- Currency symbols preserved
- Date formats preserved
- All special characters preserved
- Empty cells use ""
- Valid JSON syntax

EXAMPLE:

MARKDOWN:
| DESCRIPTION | QUANTITY TD | PRICE 2 |
| CUSIP: 901384107 ISIN: US9013841070 | (17,236) | 2.94 |

IMAGE shows "CMN CUSIP: 35104E100 ISIN: US35104E1001 ALBIREO PHARMA, INC. CMN " on separate lines in the cell.

OUTPUT:
{
  "tables": [{
    "table_id": "table_1",
    "columns": ["DESCRIPTION", "QUANTITY TD", "PRICE 2"],
    "rows": [
      {
        "DESCRIPTION": "CMN CUSIP: 35104E100 \n ISIN: US35104E1001\n ALBIREO PHARMA, INC. CMN ",
        "QUANTITY TD": "(17,236)",
        "PRICE 2": "2.94"
      }
    ],
    "row_count": 1,
    "column_count": 3
  }],
  "total_tables": 1
}

Note: (17,236) is preserved with parentheses exactly as shown in markdown.

BEGIN EXTRACTION:

Extract the table data from the provided image and markdown. Use markdown as ground truth for values, image for structure. Return only the JSON object.
"""


# ==================== HELPER FUNCTIONS ====================

def initialize_azure_client() -> AzureOpenAI:
    """Initialize Azure OpenAI client"""
    return AzureOpenAI(
        api_version=AZURE_CONFIG["api_version"],
        azure_endpoint=AZURE_CONFIG["endpoint"],
        api_key=AZURE_CONFIG["subscription_key"]
    )


def find_all_table_pairs(base_directory: Path) -> List[Dict[str, Path]]:
    """
    Find all matching pairs of table images and markdown files
    
    Returns:
        List of dicts with 'image_path', 'md_path', 'table_name', 'parent_folder', 'base_folder'
    """
    pairs = []
    
    # Helper function to process a directory
    def process_folder(folder: Path, parent_name: str):
        table_images_dir = folder / TABLE_IMAGES_FOLDER
        tables_dir = folder / TABLES_FOLDER
        
        # Check if both folders exist
        if not (table_images_dir.exists() and tables_dir.exists()):
            return
        
        # Find all PNG files in table_images
        image_files = list(table_images_dir.glob("*.png"))
        
        for image_file in image_files:
            # Find matching markdown file (same name)
            md_file = tables_dir / f"{image_file.stem}.md"
            
            if md_file.exists():
                pairs.append({
                    'image_path': image_file,
                    'md_path': md_file,
                    'table_name': image_file.stem,
                    'parent_folder': parent_name,
                    'base_folder': folder
                })
    
    # First check the base directory itself
    process_folder(base_directory, base_directory.name)
    
    # Then search for all subdirectories
    for subfolder in base_directory.iterdir():
        if not subfolder.is_dir():
            continue
        process_folder(subfolder, subfolder.name)
    
    return sorted(pairs, key=lambda x: (x['parent_folder'], x['table_name']))


def extract_table_combined(image_path: Path, md_path: Path, client: AzureOpenAI) -> Optional[TableExtractionResponse]:
    """
    Process both image and markdown file together for enhanced extraction
    
    Args:
        image_path: Path to the table image
        md_path: Path to the markdown file
        client: Azure OpenAI client
    
    Returns:
        TableExtractionResponse object or None if extraction fails
    """
    print(f"  Reading image: {image_path.name}")
    print(f"  Reading markdown: {md_path.name}")
    
    # Read image and convert to base64
    try:
        with open(image_path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        print(f"    Error reading image: {e}")
        return None
    
    # Read markdown content
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except Exception as e:
        print(f"    Error reading markdown: {e}")
        return None
    
    if not markdown_content.strip():
        print(f"    Warning: Empty markdown file, using image only")
        markdown_content = "[No markdown data available]"
    
    print(f"  Sending to LLM for dual-source extraction...")
    
    # Prepare LLM request with both image and markdown
    try:
        response = client.chat.completions.create(
            model=AZURE_CONFIG["deployment_name"],
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert table extraction system with dual-source processing capability. You analyze both visual (image) and structured (markdown) representations to extract tables with maximum accuracy. Always return valid JSON matching the specified schema."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{COMBINED_EXTRACTION_PROMPT}\n\n**MARKDOWN TABLE DATA:**\n\n{markdown_content}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_completion_tokens=16000
        )
        
        result_text = response.choices[0].message.content or ""
        
        if not result_text.strip():
            print(f"    Error: Empty response from LLM")
            return None
        
        print(f"  Parsing LLM response...")
        
        # Parse JSON response
        try:
            # Remove potential markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            json_data = json.loads(result_text.strip())
            
            # Validate with Pydantic
            extraction_response = TableExtractionResponse(**json_data)
            extraction_response.source_file = image_path.stem
            
            print(f"  [OK] Successfully extracted {len(extraction_response.tables)} table(s)")
            return extraction_response
            
        except json.JSONDecodeError as e:
            print(f"    Error: Invalid JSON response: {e}")
            print(f"    Response preview: {result_text[:500]}")
            return None
        except ValidationError as e:
            print(f"    Error: Response doesn't match expected schema: {e}")
            return None
            
    except Exception as e:
        print(f"    Error calling LLM: {e}")
        return None


def save_to_json(data: TableExtractionResponse, output_path: Path):
    """Save extraction response to JSON file"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"  [OK] JSON saved: {output_path.name}")


def save_to_csv(data: TableExtractionResponse, output_path: Path):
    """
    Save extraction response to CSV file with proper multi-line cell handling
    """
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = None
        
        for idx, table in enumerate(data.tables):
            # Write table separator if multiple tables
            if idx > 0 and writer:
                writer.writerow([])
                writer.writerow([f"--- Table {table.table_id} ---"])
            
            # Write headers
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=table.columns, quoting=csv.QUOTE_ALL)
                writer.writeheader()
            else:
                writer = csv.DictWriter(f, fieldnames=table.columns, quoting=csv.QUOTE_ALL)
                writer.writeheader()
            
            # Process rows to handle multi-line cells
            processed_rows = []
            for row in table.rows:
                processed_row = {}
                for col, value in row.items():
                    if isinstance(value, str):
                        # Convert \\n to actual newline for proper CSV formatting
                        processed_value = value.replace('\\n', '\n')
                        
                        # Smart splitting for DESCRIPTION columns with CUSIP/ISIN patterns
                        if 'DESCRIPTION' in col.upper() or 'CUSIP' in value or 'ISIN' in value:
                            cusip_match = re.search(r'(CUSIP:\s*[A-Z0-9]+)', value)
                            isin_match = re.search(r'(ISIN:\s*[A-Z0-9]+)', value)
                            
                            if cusip_match and isin_match:
                                cusip_part = cusip_match.group(1)
                                isin_part = isin_match.group(1)
                                isin_end = isin_match.end()
                                remaining = value[isin_end:].strip()
                                
                                if remaining:
                                    processed_value = f"{cusip_part} {isin_part}\n{remaining}"
                                else:
                                    processed_value = f"{cusip_part} {isin_part}"
                        
                        processed_row[col] = processed_value
                    else:
                        processed_row[col] = value
                processed_rows.append(processed_row)
            
            # Write rows
            writer.writerows(processed_rows)
    
    print(f"  [OK] CSV saved: {output_path.name}")


def save_to_xlsx(data: TableExtractionResponse, output_path: Path):
    """
    Save extraction response to XLSX file with text formatting to preserve parentheses
    This prevents Excel from converting (719) to -719
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted Table"
    
    for idx, table in enumerate(data.tables):
        # Add table separator if multiple tables
        if idx > 0:
            ws.append([])
            ws.append([f"--- Table {table.table_id} ---"])
        
        # Write headers
        ws.append(table.columns)
        
        # Process and write rows
        for row in table.rows:
            row_data = []
            for col in table.columns:
                value = row.get(col, "")
                if isinstance(value, str):
                    # Convert \\n to actual newline for Excel
                    processed_value = value.replace('\\n', '\n')
                    
                    # Smart splitting for DESCRIPTION columns with CUSIP/ISIN patterns
                    if 'DESCRIPTION' in col.upper() or 'CUSIP' in value or 'ISIN' in value:
                        cusip_match = re.search(r'(CUSIP:\s*[A-Z0-9]+)', value)
                        isin_match = re.search(r'(ISIN:\s*[A-Z0-9]+)', value)
                        
                        if cusip_match and isin_match:
                            cusip_part = cusip_match.group(1)
                            isin_part = isin_match.group(1)
                            isin_end = isin_match.end()
                            remaining = value[isin_end:].strip()
                            
                            if remaining:
                                processed_value = f"{cusip_part} {isin_part}\n{remaining}"
                            else:
                                processed_value = f"{cusip_part} {isin_part}"
                    
                    row_data.append(processed_value)
                else:
                    row_data.append(value)
            
            ws.append(row_data)
    
    # Apply text formatting to all cells to preserve parentheses and formatting
    for row in ws.iter_rows():
        for cell in row:
            if cell.value:
                # Store as text by prefixing with apostrophe to prevent Excel auto-conversion
                # But only for cells that contain parentheses with numbers
                if isinstance(cell.value, str) and re.search(r'\([\d,\.]+\)', cell.value):
                    # Force text format by setting number format
                    cell.number_format = '@'
                # Enable text wrapping for multi-line content
                cell.alignment = Alignment(wrap_text=True, vertical='top')
    
    wb.save(output_path)
    print(f"  [OK] XLSX saved: {output_path.name}")


# ==================== MAIN PROCESSING ====================

def main():
    """Main processing function"""
    print("="*80)
    print("COMBINED IMAGE + MARKDOWN TABLE EXTRACTOR")
    print("="*80)
    print(f"Base directory: {INPUT_DIRECTORY}")
    print(f"Looking for paired files in:")
    print(f"  - Images: {TABLE_IMAGES_FOLDER}/")
    print(f"  - Markdown: {TABLES_FOLDER}/\n")
    
    # Initialize client
    print("Initializing Azure OpenAI client...")
    client = initialize_azure_client()
    print(" Client initialized\n")
    
    # Find all table pairs
    base_dir = Path(INPUT_DIRECTORY)
    if not base_dir.exists():
        print(f"Error: Directory does not exist: {INPUT_DIRECTORY}")
        return
    
    print("Scanning for table image + markdown pairs...")
    table_pairs = find_all_table_pairs(base_dir)
    
    if not table_pairs:
        print(f"No matching table pairs found in {INPUT_DIRECTORY}")
        return
    
    print(f"[OK] Found {len(table_pairs)} table pair(s)\n")
    
    # Process each pair
    success_count = 0
    error_count = 0
    
    for pair in table_pairs:
        print(f"\n{'='*80}")
        print(f"Processing: {pair['parent_folder']} / {pair['table_name']}")
        print(f"{'='*80}")
        
        # Extract table data using both sources
        extraction_result = extract_table_combined(
            pair['image_path'],
            pair['md_path'],
            client
        )
        
        if extraction_result is None:
            print(f"  [ERROR] Extraction failed")
            error_count += 1
            continue
        
        # Generate output file paths (save in table_xl folder at base folder level)
        table_xl_folder = pair['base_folder'] / 'table_xl'
        table_xl_folder.mkdir(exist_ok=True)
        
        output_base = table_xl_folder / pair['table_name']
        json_output = output_base.with_suffix(".json")
        csv_output = output_base.with_suffix(".csv")
        xlsx_output = output_base.with_suffix(".xlsx")
        
        # Save outputs
        try:
            save_to_json(extraction_result, json_output)
            save_to_csv(extraction_result, csv_output)
            save_to_xlsx(extraction_result, xlsx_output)
            success_count += 1
        except Exception as e:
            print(f"  [ERROR] Error saving outputs: {e}")
            error_count += 1
    
    # Summary
    print(f"\n{'='*80}")
    print("PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total pairs processed: {len(table_pairs)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {error_count}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
