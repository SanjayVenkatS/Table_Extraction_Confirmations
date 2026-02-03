
import os
import sys
import subprocess
import shutil
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter


class PDFExtractionWorkflow:
    """Orchestrates the complete PDF extraction workflow"""
    
    def __init__(self, workspace_root=None):
        if workspace_root is None:
            self.workspace_root = Path(__file__).parent
        else:
            self.workspace_root = Path(workspace_root)
        
        self.output_folder = self.workspace_root / "output_folder"
        self.trimmed_pdf_folder = self.workspace_root / "trimmed_pdfs"
        
    def parse_page_numbers(self, page_input):
        pages = set()
        parts = page_input.replace(" ", "").split(",")
        
        for part in parts:
            if "-" in part:
                # Handle range like "5-190"
                start, end = part.split("-")
                pages.update(range(int(start), int(end) + 1))
            else:
                # Handle single page like "235"
                pages.add(int(part))
        
        return sorted(list(pages))
    
    def trim_pdf(self, input_pdf_path, page_numbers, output_filename=None):
        
        input_pdf_path = Path(input_pdf_path)
        
        if not input_pdf_path.exists():
            raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")
        
        # Create output directory if it doesn't exist
        self.trimmed_pdf_folder.mkdir(exist_ok=True)
        
        # Generate output filename
        if output_filename is None:
            output_filename = f"{input_pdf_path.stem}_trimmed.pdf"
        
        output_path = self.trimmed_pdf_folder / output_filename
        
        # Read the input PDF
        reader = PdfReader(str(input_pdf_path))
        writer = PdfWriter()
        
        total_pages = len(reader.pages)
        print(f"Total pages in PDF: {total_pages}")
        print(f"Extracting {len(page_numbers)} pages...")
        
        # Add specified pages to writer (convert 1-indexed to 0-indexed)
        for page_num in page_numbers:
            if page_num < 1 or page_num > total_pages:
                print(f"Warning: Page {page_num} is out of range. Skipping.")
                continue
            writer.add_page(reader.pages[page_num - 1])
        
        # Write to output file
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        print(f"✓ Trimmed PDF saved to: {output_path}")
        return output_path
    
    def run_adi_extraction(self, pdf_path):
        pdf_path = Path(pdf_path)
        pdf_folder = pdf_path.parent
        
        # Create output folder
        self.output_folder.mkdir(exist_ok=True)
        
        # Path to run_pipeline.py
        pipeline_script = self.workspace_root / "ADI_Extraction_new" / "run_pipeline.py"
        
        if not pipeline_script.exists():
            raise FileNotFoundError(f"Pipeline script not found: {pipeline_script}")
        
        # Change to ADI_Extraction_new directory
        adi_dir = self.workspace_root / "ADI_Extraction_new"
        
        # Prepare the command
        command = [
            sys.executable,
            "run_pipeline.py",
            "--input-dir", str(pdf_folder),
            "--output-dir", str(self.output_folder)
        ]
        
        print(f"\n{'='*60}")
        print(f"Running ADI Extraction Pipeline...")
        print(f"Input directory: {pdf_folder}")
        print(f"Output directory: {self.output_folder}")
        print(f"{'='*60}\n")
        
        # Run the pipeline
        result = subprocess.run(
            command,
            cwd=str(adi_dir),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ ADI Extraction completed successfully")
        else:
            print(f"✗ ADI Extraction failed with return code: {result.returncode}")
            if result.stderr:
                print(f"Error output:\n{result.stderr}")
        
        # Return the output path where ADI created the folder
        # It creates a folder named after the PDF file
        adi_output_path = self.output_folder / pdf_path.stem
        
        return result.returncode, result.stdout, result.stderr, adi_output_path
    
    def run_table_extractor(self, input_directory):
        """
        Run the Table Extractor script.
        
        Args:
            input_directory: Path to the directory containing table images and markdown files
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        extractor_script = self.workspace_root / "Table Extractor" / "image_md_tab_extract_repo.py"
        
        if not extractor_script.exists():
            raise FileNotFoundError(f"Table extractor script not found: {extractor_script}")
        
        # Clear Python cache to ensure latest code runs
        cache_dir = self.workspace_root / "Table Extractor" / "__pycache__"
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir, ignore_errors=True)
            except Exception as e:
                # Ignore cache clearing errors
                pass
        
        print(f"\n{'='*60}")
        print(f"Running Table Extractor...")
        print(f"Input directory: {input_directory}")
        print(f"{'='*60}\n")
        
        # Run the table extractor with input directory argument
        result = subprocess.run(
            [sys.executable, str(extractor_script), str(input_directory)],
            cwd=str(self.workspace_root / "Table Extractor"),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Table Extraction completed successfully")
        else:
            print(f"✗ Table Extraction failed with return code: {result.returncode}")
            if result.stderr:
                print(f"Error output:\n{result.stderr}")
        
        return result.returncode, result.stdout, result.stderr
    
    def run_workflow(self, input_pdf_path, page_input, output_filename=None):
        """
        Run the complete workflow.
        
        Args:
            input_pdf_path: Path to the input PDF file
            page_input: String with page numbers/ranges (e.g., "5-190,235,246,257")
            output_filename: Optional custom output filename
        """
        print(f"\n{'#'*60}")
        print(f"# PDF EXTRACTION WORKFLOW")
        print(f"{'#'*60}\n")
        
        try:
            # Step 1: Parse page numbers
            print(f"Step 1: Parsing page numbers...")
            page_numbers = self.parse_page_numbers(page_input)
            print(f"Pages to extract: {page_numbers[:10]}{'...' if len(page_numbers) > 10 else ''}")
            print(f"Total pages: {len(page_numbers)}\n")
            
            # Step 2: Trim PDF
            print(f"Step 2: Trimming PDF...")
            trimmed_pdf_path = self.trim_pdf(input_pdf_path, page_numbers, output_filename)
            print()
            
            # Step 3: Run ADI Extraction
            print(f"Step 3: Running ADI Extraction Pipeline...")
            adi_returncode, adi_stdout, adi_stderr, adi_output_path = self.run_adi_extraction(trimmed_pdf_path)
            if adi_stdout:
                print(adi_stdout)
            print()
            
            # Step 4: Run Table Extractor
            print(f"Step 4: Running Table Extractor...")
            table_returncode, table_stdout, table_stderr = self.run_table_extractor(adi_output_path)
            if table_stdout:
                print(table_stdout)
            print()
            
            # Summary
            print(f"\n{'#'*60}")
            print(f"# WORKFLOW COMPLETED")
            print(f"{'#'*60}")
            print(f"Trimmed PDF: {trimmed_pdf_path}")
            print(f"Output folder: {self.output_folder}")
            print(f"ADI Extraction: {'✓ Success' if adi_returncode == 0 else '✗ Failed'}")
            print(f"Table Extraction: {'✓ Success' if table_returncode == 0 else '✗ Failed'}")
            print(f"{'#'*60}\n")
            
        except Exception as e:
            print(f"\n✗ Workflow failed with error: {str(e)}")
            raise


def main():
    """Main function to run the workflow interactively"""
    print("PDF Extraction Workflow Orchestrator")
    print("=" * 60)
    
    # Get input PDF path
    input_pdf = "C:\\Users\\ZZ125LG\\Downloads\\FW_ Securities Confirmations - initial extracts and finding discussion\\HH.27 - CF8C -  BNP PARIBAS SA - JP Morgan - Forwards.pdf"
    
    if not os.path.exists(input_pdf):
        print(f"Error: File not found: {input_pdf}")
        return
    
    # Display total number of pages
    print(f"\nAnalyzing PDF: {os.path.basename(input_pdf)}")
    print("-" * 60)
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    print(f"📄 Total pages in PDF: {total_pages}")
    print("-" * 60)
    
    # Get page numbers for tables
    print("\nEnter the page numbers that contain tables to be extracted.")
    print('Format: "5-190,235,246,257" (ranges and individual pages)')
    page_input = input('Page numbers: ').strip()
    
    # Optional: Custom output filename
    output_filename = input("\nEnter custom output filename (or press Enter for default): ").strip()
    if not output_filename:
        output_filename = None
    
    # Initialize and run workflow
    workflow = PDFExtractionWorkflow()
    workflow.run_workflow(input_pdf, page_input, output_filename)


if __name__ == "__main__":
    main()
