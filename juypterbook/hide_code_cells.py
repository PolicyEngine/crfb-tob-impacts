import json
import sys

def hide_code_cells(notebook_path):
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            if 'metadata' not in cell:
                cell['metadata'] = {}
            if 'tags' not in cell['metadata']:
                cell['metadata']['tags'] = []
            if 'hide-input' not in cell['metadata']['tags']:
                cell['metadata']['tags'].append('hide-input')

    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)

    print(f"Successfully added hide-input tags to all code cells in {notebook_path}")

if __name__ == "__main__":
    hide_code_cells('household_impacts.ipynb')