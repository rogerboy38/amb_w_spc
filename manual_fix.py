import re

def manual_fix_specific_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Fix specific line patterns - adjust these based on the actual error
    for i in range(len(lines)):
        line = lines[i]
        
        # Common problematic patterns and their fixes:
        
        # Pattern 1: Windows paths in f-strings
        if re.search(r'f["\'][^"\']*\\[^"\']*[{][^"\']*["\']', line):
            lines[i] = line.replace('f"', 'fr"').replace("f'", "fr'")
        
        # Pattern 2: Escaped characters in f-strings
        elif re.search(r'f["\'][^"\']*\\[ntr][^"\']*[{]', line):
            # For newlines, tabs, etc. - consider alternative approaches
            match = re.search(r'f(".*?")', line)
            if match:
                fstring = match.group(1)
                # Replace with concatenation or format()
                parts = fstring.split('{')
                if len(parts) > 1:
                    new_line = line.replace(f'f{fstring}', f'"{parts[0]}" + ' + '{' + parts[1])
                    lines[i] = new_line
        
        # Pattern 3: Backslashes before quotes in f-strings
        elif re.search(r'f["\'][^"\']*\\["\'][^"\']*["\']', line):
            lines[i] = line.replace('f"', 'fr"').replace("f'", "fr'")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Manual fixes applied.")

manual_fix_specific_lines("amb_w_spc/system_integration/installation/install_spc_system.py")
