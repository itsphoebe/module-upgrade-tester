"""
This script replaces the 'version' of a Terraform module inside a provided input file given a source substring (module name).

Usage: 
  python replace_version.py <input_file> <source_substring> <new_version> [--dry-run]
  -- dry-run: Show changes without modifying the file

Notes: 
  - The script expects the input file to be a valid Terraform file.
  - Updates input file in place unless --dry-run is specified.
  - Module blocks are only modified if they contain a source line with the specified substring (module name).
"""
import re
import argparse

def replace_version_in_modules(input_file_path, source_substring, new_version, dry_run=False):
    with open(input_file_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    inside_module_block = False
    module_has_source = False

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith('module'):
            inside_module_block = True
            module_has_source = False
        if inside_module_block and stripped_line.startswith('source') and source_substring in stripped_line:
            module_has_source = True

        if inside_module_block and module_has_source and re.search(r'^\s*version\s*=', line):
            # Replace the version line with the new version
            line = re.sub(r'version\s*=\s*".*"', f'version = "{new_version}"', line) 
        if inside_module_block and stripped_line == '}':
            inside_module_block = False

        updated_lines.append(line)

    if dry_run:
        print("".join(updated_lines))
    else:
        # Overwrite the input file with the updated lines
        with open(input_file_path, 'w') as file:
            file.writelines(updated_lines)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replace version in Terraform module blocks.")
    parser.add_argument("input_file", help="Path to the input file")
    parser.add_argument("source_substring", help="Substring to match in the source line")
    parser.add_argument("new_version", help="New version to set after 'version ='")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying the file")

    args = parser.parse_args()

    replace_version_in_modules(args.input_file, args.source_substring, args.new_version, args.dry_run)