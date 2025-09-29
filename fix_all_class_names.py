#!/usr/bin/env python3
import os
import re

def get_proper_class_name(doctype_name):
    """Convert doctype name to proper class name with acronym handling"""
    # Handle acronyms - SPC, SFC, PLC, FDA should be all caps
    words = doctype_name.split('_')
    
    # Process each word
    processed_words = []
    for word in words:
        if word.upper() in ['SPC', 'SFC', 'PLC', 'FDA', 'ERP', 'API']:
            processed_words.append(word.upper())
        else:
            processed_words.append(word.capitalize())
    
    return ''.join(processed_words)

def fix_python_file(file_path):
    """Fix the class name in a Python file"""
    doctype_name = os.path.basename(file_path).replace('.py', '')
    proper_class_name = get_proper_class_name(doctype_name)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find current class name
    class_match = re.search(r'class\s+(\w+)', content)
    if class_match:
        current_class = class_match.group(1)
        if current_class != proper_class_name:
            print(f"Fixing {doctype_name}: {current_class} -> {proper_class_name}")
            content = content.replace(f'class {current_class}', f'class {proper_class_name}')
            
            with open(file_path, 'w') as f:
                f.write(content)
            return True
    
    return False

def main():
    # Find all Python controller files
    for root, dirs, files in os.walk('amb_w_spc'):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                file_path = os.path.join(root, file)
                # Check if this is a doctype controller (file name matches directory name)
                dir_name = os.path.basename(root)
                if file.replace('.py', '') == dir_name:
                    fix_python_file(file_path)

if __name__ == '__main__':
    main()
    print("Class name fix complete!")
