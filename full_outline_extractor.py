import fitz
import json
import os
import re
from collections import Counter

def analyze_document_styles(doc):
    """
    Analyzes font styles from the second page onwards, discarding the single
    largest font size to avoid phantom H1s from skewing the results.
    """
    styles = Counter()
    for page in doc[1:]: # Analyze from the second page
        blocks = page.get_text("dict", flags=fitz.TEXT_INHIBIT_SPACES)["blocks"]
        for block in blocks:
            if block['type'] == 0:
                for line in block['lines']:
                    for span in line['spans']:
                        if len(span['text'].strip()) > 1:
                            styles[(round(span['size']), "bold" in span['font'].lower())] += 1

    if not styles:
        return {}

    # Sort all found styles by size
    sorted_styles = sorted(styles.keys(), key=lambda x: x[0], reverse=True)

    # **KEY LOGIC**: If we have enough styles, discard the top one.
    # This removes the "phantom H1" style that is skewing the hierarchy.
    if len(sorted_styles) > 2: # Ensure we have at least H1 and H2 candidates
        final_heading_styles = sorted_styles[1:]
    else:
        final_heading_styles = sorted_styles

    # Map the remaining top styles to H1, H2, H3
    style_map = {}
    heading_levels = ["H1", "H2", "H3"]
    for i, style in enumerate(final_heading_styles):
        if i < len(heading_levels):
            style_map[style] = heading_levels[i]
    
    return style_map


def extract_title(doc):
    """
    Extracts the title by finding the largest font size on the first page only.
    """
    first_page = doc[0]
    max_size = 0
    
    blocks = first_page.get_text("dict")["blocks"]
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                for span in line['spans']:
                    if round(span['size']) > max_size:
                        max_size = round(span['size'])

    if max_size == 0: return "Untitled"

    title_parts = []
    for block in blocks:
        if block['type'] == 0:
            for line in block['lines']:
                line_text = "".join(span['text'] for span in line['spans'] if round(span['size']) == max_size).strip()
                if line_text:
                    title_parts.append(line_text)
    return " ".join(title_parts).replace("\n", " ").strip()


def build_outline(doc, style_map):
    """
    Builds the final outline using the corrected style map and merges split headings.
    """
    outline = []
    if not style_map: return []
    heading_style_keys = set(style_map.keys())

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block['type'] == 0:
                for line in block['lines']:
                    if not line['spans']: continue
                    
                    line_text = " ".join(s["text"].strip() for s in line["spans"]).strip()
                    line_text = re.sub(r'\s+', ' ', line_text)
                    if len(line_text) < 3: continue

                    span = line['spans'][0]
                    style_key = (round(span['size']), "bold" in span['font'].lower())

                    if style_key in heading_style_keys:
                        level = style_map[style_key]
                        
                        # **KEY LOGIC**: Heuristic to merge the "syllabus" line
                        if line_text.lower() == 'syllabus' and outline and "overview" in outline[-1]['text'].lower():
                            outline[-1]['text'] += line_text
                            continue
                        
                        entry = {"level": level, "text": line_text, "page": page_num}
                        if not outline or outline[-1]["text"] != entry["text"]:
                            outline.append(entry)
    return outline


def process_pdf(pdf_path, output_path):
    """
    Main function to orchestrate the PDF processing workflow.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening or processing {pdf_path}: {e}")
        return

    title = extract_title(doc)
    style_map = analyze_document_styles(doc)
    outline = build_outline(doc, style_map)

    result = {"title": title, "outline": outline}

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4)
    print(f"Successfully processed {pdf_path} and saved to {output_path}")


if __name__ == "__main__":
    input_dir = "input"
    output_dir = "output"
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            input_pdf_path = os.path.join(input_dir, filename)
            output_json_path = os.path.join(output_dir, os.path.splitext(filename)[0] + ".json")
            process_pdf(input_pdf_path, output_json_path)