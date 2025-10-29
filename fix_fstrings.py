import re
import os

def fix_fstring_backslashes(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find f-strings with backslashes
    patterns = [
        # f-strings with Windows paths
        (r'f"([^"]*\\[^"]*)"', r'fr"\1"'),
        (r"f'([^']*\\[^']*)'", r"fr'\1'"),
        
        # f-strings with escaped quotes and backslashes
        (r'f"([^"]*\\"[^"]*)"', r'fr"\1"'),
        (r"f'([^']*\\'[^']*)'", r"fr'\1'"),
        
        # Multiline f-strings with backslashes
        (r'f"""([^"]*\\[^"]*)"""', r'fr"""\1"""'),
        (r"f'''([^']*\\[^']*)'''", r"fr'''\1'''"),
    ]
    
    original_content = content
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    # Additional fix for complex cases - replace with format()
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines, 1):
        # Check for f-strings that still might have issues
        if 'f"' in line or "f'" in line:
            # Handle Windows paths specifically
            if re.search(r'f["\'][^"\']*\\[^"\']*[{]', line):
                line = re.sub(r'f"', 'fr"', line)
                line = re.sub(r"f'", "fr'", line)
        
        fixed_lines.append(line)
    
    fixed_content = '\n'.join(fixed_lines)
    
    if fixed_content != original_content:
        # Create backup
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"Backup created at: {backup_path}")
        
        # Write fixed content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"Fixed file saved at: {file_path}")
        
        # Show what was changed
        print("\nChanges made:")
        original_lines = original_content.split('\n')
        fixed_lines = fixed_content.split('\n')
        
        for j, (orig, fixed) in enumerate(zip(original_lines, fixed_lines)):
            if orig != fixed:
                print(f"Line {j+1}:")
                print(f"  WAS: {orig}")
                print(f"  NOW: {fixed}")
                print()
    else:
        print("No changes were needed.")
    
    return fixed_content

if __name__ == "__main__":
    file_path = "amb_w_spc/system_integration/installation/install_spc_system.py"
    if os.path.exists(file_path):
        fix_fstring_backslashes(file_path)
    else:
        print(f"File not found: {file_path}")
