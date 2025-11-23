# Markdown Templating System

This project uses a Jinja2-based templating system to automatically populate markdown files with data from the analysis, preventing manual update errors and ensuring all numbers stay synchronized with the underlying data.

## How It Works

1. **Templates**: Markdown template files with `{{ placeholder }}` syntax in `jupyterbook/templates/`
2. **Data Source**: `data/revenue_impacts.csv` contains all revenue impact estimates
3. **Script**: `generate_markdown.py` reads data, calculates values, and populates templates
4. **Output**: Generated markdown files in `jupyterbook/`

## When to Regenerate

Run the generation script whenever:
- ✅ The underlying data changes (`data/revenue_impacts.csv` is updated)
- ✅ You want to modify how numbers are formatted
- ✅ You add new placeholders to templates

**Do NOT manually edit generated markdown files** - they will be overwritten!

## Usage

### Basic Usage
```bash
# From project root
uv run python generate_markdown.py
```

This will:
1. Read `data/revenue_impacts.csv`
2. Calculate 10-year totals for each reform option
3. Populate all templates in `jupyterbook/templates/`
4. Write output to `jupyterbook/`

### Output
```
✓ Generated jupyterbook/external-estimates.md

Populated values:
  opt1_10yr: -1,509
  opt2_10yr: 424
  ...
```

## File Structure

```
crfb-tob-impacts/
├── data/
│   └── revenue_impacts.csv          # Source data (75 years × 8 options × 2 scoring types)
├── generate_markdown.py             # Template population script
└── jupyterbook/
    ├── templates/
    │   └── external-estimates.md.tpl   # Template with {{ placeholders }}
    └── external-estimates.md           # Generated output (DO NOT EDIT MANUALLY)
```

## Template Syntax

Templates use Jinja2 syntax with `{{ variable_name }}` placeholders:

```markdown
### Option 1: Full Repeal
**10-Year Impact:** ${{ opt1_10yr }} billion

### Option 2: 85% Taxation
**10-Year Impact:** ${{ opt2_10yr }} billion
```

## Available Variables

Current variables (all in billions, rounded to nearest whole number):

- `opt1_10yr` through `opt8_10yr`: 10-year static totals (2026-2035)
- `opt1_10yr_with_sign`: Option 1 formatted as trillions with sign

## Adding New Templates

To add a new template:

1. **Create template file**: `jupyterbook/templates/your-file.md.tpl`
2. **Add placeholders**: Use `{{ variable_name }}` syntax
3. **Update script**: Add function to `generate_markdown.py`:
   ```python
   def generate_your_file():
       df = load_revenue_data()
       # Calculate your values
       variables = {
           'your_var': format_billions(value),
       }

       template_path = Path('jupyterbook/templates/your-file.md.tpl')
       with open(template_path) as f:
           template = Template(f.read())

       output = template.render(**variables)

       output_path = Path('jupyterbook/your-file.md')
       with open(output_path, 'w') as f:
           f.write(output)
   ```
4. **Call from main**: Add `generate_your_file()` to the main block

## Formatting Functions

### `format_billions(value, decimals=0)`
Formats a number as billions with specified decimal places.
- `format_billions(1509.31)` → `"1,509"`
- `format_billions(1509.31, decimals=1)` → `"1,509.3"`

### `format_trillions(value, decimals=1)`
Formats a number as trillions with specified decimal places.
- `format_trillions(1509.31)` → `"1.5"`

## Workflow for Data Updates

When new data arrives:

1. **Update CSV**: Replace `data/revenue_impacts.csv` with new data
2. **Regenerate markdown**: Run `uv run python generate_markdown.py`
3. **Re-execute notebooks**:
   ```bash
   cd jupyterbook
   uv run jupyter nbconvert --to notebook --execute --inplace revenue-impacts.ipynb
   ```
4. **Commit changes**:
   ```bash
   git add data/revenue_impacts.csv jupyterbook/external-estimates.md jupyterbook/revenue-impacts.ipynb
   git commit -m "Update with new data from [date]"
   ```

## Benefits

✅ **Consistency**: All numbers guaranteed to match source data
✅ **No manual errors**: Eliminates typos and outdated figures
✅ **Auditability**: Clear trail from data → template → output
✅ **Easy updates**: One command regenerates all dependent files
✅ **Version control**: Templates are small and easy to review in diffs

## Troubleshooting

### "Template not found" error
- Ensure you're running from project root
- Check that `jupyterbook/templates/` directory exists

### Numbers don't match expectations
- Verify `data/revenue_impacts.csv` has correct data
- Check the calculation logic in `generate_markdown.py`
- Confirm you're using the right year range (2026-2035)

### Changes not appearing
- Make sure you edited the `.tpl` template file, not the generated `.md` file
- Re-run `generate_markdown.py` after template changes
- Check console output for error messages

## Example: Yankees Beer Project

This templating system is based on the pattern used in the `yankee-stadium-beer-price-controls` repository, which uses similar Jinja2 templates with `{{ variable }}` placeholders populated from simulation results.
