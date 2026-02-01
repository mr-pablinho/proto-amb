import csv
import json
import re

# Input and Output filenames
#INPUT_CSV = "./data/checklist/Checklist Borrador - Gemini 2.csv"
INPUT_CSV = "./data/checklist/Checklist Borrador - Gemini 2.xlsx - check_reduced.csv"
OUTPUT_JSON = "./data/audit_checklist.json"

def convert_csv_to_json():
    checklist = []
    
    # This variable will "remember" the last chapter seen
    current_chapter = ""

    # Regex pattern to match numbering at the start (e.g., "3.1 ", "3.5.2 ")
    # Matches digits and dots followed by a space at the beginning of the string
    numbering_pattern = r'^\d+(\.\d+)*\s+'

    try:
        with open(INPUT_CSV, mode='r', encoding='utf-8') as csvfile:
            # Using comma as delimiter based on your file preview
            reader = csv.DictReader(csvfile)
            
            for i, row in enumerate(reader):
                # 1. HANDLE FORWARD FILL (MEMORY)
                raw_chapter = row.get('Capítulo y Sección', '').strip()
                
                if raw_chapter:
                    # If there's a new value, clean the numbering and update memory
                    current_chapter = re.sub(numbering_pattern, '', raw_chapter)
                
                # 2. SKIP EMPTY ROWS
                # Only process if 'Requisito' has content
                requirement = row.get('Requisito', '').strip()
                if not requirement:
                    continue
                
                # 3. BUILD THE ITEM
                item = {
                    "id": f"REQ-{len(checklist) + 1:03d}",
                    "chapter": current_chapter, # Uses the "remembered" value
                    "requirement": requirement,
                    "criteria": row.get('Criterio de Cumplimiento', '').strip(),
                    "expected_evidence": row.get('Evidencia', '').strip()
                }
                checklist.append(item)

        # Write the resulting list to JSON
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(checklist, f, indent=4, ensure_ascii=False)
    
        print(f"Successfully converted {len(checklist)} requirements to {OUTPUT_JSON}")

    except FileNotFoundError:
        print(f"Error: The file {INPUT_CSV} was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    convert_csv_to_json()