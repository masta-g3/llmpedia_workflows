import os, sys
from dotenv import load_dotenv

load_dotenv()

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import os
from pathlib import Path
import utils.paper_utils as pu

def convert_pdf_to_markdown_file(pdf_path: str, output_dir: str) -> bool:
    """Convert a PDF file to markdown and save images to the specified directory."""
    # Convert PDF to markdown and get images
    markdown_text, images = pu.convert_pdf_to_markdown(pdf_path)
    
    if markdown_text is None:
        print(f"Failed to convert PDF to markdown: {pdf_path}")
        return False
        
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save markdown file
    markdown_path = os.path.join(output_dir, "paper.md")
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    
    # Save images
    for img_name, img in images.items():
        img_path = os.path.join(output_dir, img_name)
        img.save(img_path, "PNG")
        
    return True
        

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert PDF to markdown with images')
    parser.add_argument('pdf_path', help='Path to the PDF file')
    parser.add_argument('output_dir', help='Directory to save markdown and images')
    
    args = parser.parse_args()
    
    success = convert_pdf_to_markdown_file(args.pdf_path, args.output_dir)
    if success:
        print(f"Successfully converted PDF to markdown in {args.output_dir}")