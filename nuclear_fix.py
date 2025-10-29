import re

def nuclear_fix(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Convert all f-strings with backslashes to use .format()
    def replace_fstring(match):
        fstring = match.group(1)
        # Extract variables from f-string
        variables = re.findall(r'\{([^}]+)\}', fstring)
        # Create format string
        format_string = fstring.replace('{', '{{').replace('}', '}}')
        for i, var in enumerate(variables):
            format_string = format_string.replace('{{' + var + '}}', '{' + str(i) + '}', 1)
        
        # Build format call
        if variables:
            return f'"{format_string}".format({", ".join(variables)})'
        else:
            return f'"{format_string}"'
    
    # Replace f-strings
    content = re.sub(r'f"([^"]*)"', replace_fstring, content)
    content = re.sub(r"f'([^']*)'", lambda m: replace_fstring(m), content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Nuclear fix applied - all f-strings converted to .format()")

nuclear_fix("amb_w_spc/system_integration/installation/install_spc_system.py")
