#!/usr/bin/env python3
"""
Check and fix unescaped dollar signs in markdown files for MyST/LaTeX.
Identifies dollar signs used for currency that need escaping as \$
"""

import re
import sys
from pathlib import Path
import argparse


def check_dollar_signs(file_path):
    """Check for potentially unescaped dollar signs in a markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    issues = []

    for line_num, line in enumerate(lines, 1):
        # Skip code blocks (lines starting with 4 spaces or tab, or inside ```)
        if line.startswith('    ') or line.startswith('\t'):
            continue

        # Skip inline code (very basic check)
        if '`' in line:
            # Remove inline code sections
            line = re.sub(r'`[^`]*`', '', line)

        # Find dollar signs followed by numbers (likely currency)
        # Pattern: $ followed by digit, comma, or decimal
        currency_pattern = r'(?<!\\)\$(?=\d|,)'

        matches = list(re.finditer(currency_pattern, line))

        for match in matches:
            col = match.start() + 1
            # Extract context around the match
            start = max(0, match.start() - 20)
            end = min(len(line), match.end() + 30)
            context = line[start:end]

            issues.append({
                'line': line_num,
                'column': col,
                'context': context,
                'full_line': line
            })

    return issues


def fix_dollar_signs(file_path):
    """Fix unescaped dollar signs in a markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    fixed_lines = []
    fixes_made = 0

    for line in lines:
        # Skip code blocks
        if line.startswith('    ') or line.startswith('\t') or line.strip().startswith('```'):
            fixed_lines.append(line)
            continue

        # Replace unescaped dollar signs followed by numbers
        # Pattern: $ not preceded by backslash, followed by digit or comma
        new_line, count = re.subn(r'(?<!\\)\$(?=\d|,\d)', r'\\$', line)
        fixes_made += count
        fixed_lines.append(new_line)

    if fixes_made > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))

    return fixes_made


def main():
    parser = argparse.ArgumentParser(description='Check or fix unescaped dollar signs in markdown files')
    parser.add_argument('path', help='File or directory to check')
    parser.add_argument('--fix', action='store_true', help='Automatically fix issues')
    args = parser.parse_args()

    path = Path(args.path)

    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = list(path.glob('**/*.md'))
    else:
        print(f"Error: {path} is not a valid file or directory")
        sys.exit(1)

    total_issues = 0
    total_fixes = 0

    for file_path in files:
        if args.fix:
            fixes = fix_dollar_signs(file_path)
            if fixes > 0:
                print(f"✓ Fixed {fixes} dollar sign(s) in {file_path}")
                total_fixes += fixes
        else:
            issues = check_dollar_signs(file_path)
            if issues:
                print(f"\n{'='*80}")
                print(f"File: {file_path}")
                print(f"Found {len(issues)} potential issue(s)")
                print('='*80)

                for issue in issues[:5]:  # Show first 5
                    print(f"\nLine {issue['line']}, Column {issue['column']}:")
                    print(f"  Context: ...{issue['context']}...")
                    print(f"  Suggestion: Replace $ with \\$")

                if len(issues) > 5:
                    print(f"\n... and {len(issues) - 5} more issues")

                total_issues += len(issues)

    print(f"\n{'='*80}")

    if args.fix:
        print(f"Total files processed: {len(files)}")
        print(f"Total fixes made: {total_fixes}")
        if total_fixes > 0:
            print("✓ All dollar signs have been escaped!")
        else:
            print("✓ No issues found!")
    else:
        print(f"Total files checked: {len(files)}")
        print(f"Total potential issues: {total_issues}")
        if total_issues > 0:
            print("\nRun with --fix to automatically escape dollar signs")
            sys.exit(1)
        else:
            print("\n✓ No unescaped dollar signs found!")

    print('='*80)
    sys.exit(0)


if __name__ == '__main__':
    main()
