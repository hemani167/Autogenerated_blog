import sys
import os
import getpass
from fpdf import FPDF

def convert_md_to_pdf(source_md, output_filename):
    class PDF(FPDF):
        pass

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    lines = source_md.split('\n')
    for line in lines:
        # Simple encoding handling for standard fonts
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        
        if clean_line.startswith('# '):
            pdf.set_font("Helvetica", 'B', 16)
            pdf.cell(0, 10, clean_line.replace('# ', ''), new_x="LMARGIN", new_y="NEXT")
        elif clean_line.startswith('## '):
            pdf.set_font("Helvetica", 'B', 14)
            pdf.cell(0, 10, clean_line.replace('## ', ''), new_x="LMARGIN", new_y="NEXT")
        elif clean_line.startswith('### '):
            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(0, 10, clean_line.replace('### ', ''), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", size=12)
            pdf.multi_cell(0, 6, clean_line, new_x="LMARGIN", new_y="NEXT")
    
    pdf.output(output_filename)
    print(f"PDF report saved to {output_filename}")

def main():
    if "GOOGLE_API_KEY" not in os.environ:
        print("GOOGLE_API_KEY not found in environment variables.")
        key = getpass.getpass("Please enter your Google API Key: ")
        os.environ["GOOGLE_API_KEY"] = key.strip()

    # Import graph AFTER setting the key so that nodes.py sees the environment variable
    try:
        from graph import app
    except Exception as e:
        print(f"Error importing graph: {e}")
        return

    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = input("Enter the topic for the blog post: ")
    
    print(f"Starting blog generation for topic: {topic}")
    
    try:
        # Use invoke to run the graph and get the final state
        result = app.invoke({"topic": topic})
        
        print("\n\n=== FINAL REPORT ===\n")
        print(result.get("final_report"))
        
        # Save to file
        base_filename = topic.replace(' ', '_').lower()
        md_filename = f"{base_filename}_blog.md"
        pdf_filename = f"{base_filename}_blog.pdf"
        
        # Save Markdown
        with open(md_filename, "w") as f:
            f.write(result.get("final_report"))
        print(f"\nMarkdown report saved to {md_filename}")
        
        # Save PDF
        print("Generating PDF...")
        convert_md_to_pdf(result.get("final_report"), pdf_filename)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

