"""
Title Name Fixer for Frappe Applications
Standalone module based on AMB W SPC implementation experience
"""

import frappe
import json
from datetime import datetime

class TitleNameFixer:
    """
    Handle detection and resolution of Title Name to doctype name mismatches
    Based on successful resolution of 69 doctypes in AMB W SPC app
    """
    
    def __init__(self, site=None):
        self.site = site or frappe.local.site
    
    def detect_issues(self):
        """
        Detect Title Name issues in custom doctypes
        Returns: dict with detected issues
        """
        print("🔍 Scanning for Title Name issues...")
        
        issues = {
            'document_type_issues': [],
            'link_field_issues': [],
            'naming_series_issues': []
        }
        
        try:
            custom_doctypes = frappe.get_all('DocType', 
                filters={'custom': 1},
                fields=['name', 'document_type', 'fields', 'module']
            )
            
            for dt in custom_doctypes:
                # Check document_type
                if dt.document_type in ['Master', 'Document']:
                    issues['document_type_issues'].append({
                        'doctype': dt.name,
                        'current': dt.document_type,
                        'module': dt.module
                    })
                
                # Check fields
                if dt.fields:
                    fields_data = json.loads(dt.fields)
                    for field in fields_data:
                        # Check link fields with Title Names
                        if (field.get('fieldtype') == 'Link' and 
                            field.get('options') and 
                            ' ' in field.get('options')):
                            issues['link_field_issues'].append({
                                'doctype': dt.name,
                                'field': field.get('fieldname'),
                                'options': field.get('options'),
                                'label': field.get('label')
                            })
                        
                        # Check naming_series unique constraint
                        if (field.get('fieldname') == 'naming_series' and 
                            field.get('unique') == 1):
                            issues['naming_series_issues'].append(dt.name)
            
            print(f"✅ Scan complete: {len(issues['document_type_issues'])} document_type issues, "
                  f"{len(issues['link_field_issues'])} link field issues, "
                  f"{len(issues['naming_series_issues'])} naming_series issues")
            
            return issues
            
        except Exception as e:
            print(f"❌ Error during issue detection: {e}")
            return issues
    
    def apply_fixes(self, issues):
        """
        Apply fixes for detected Title Name issues
        Returns: dict with fix results
        """
        print("🔧 Applying Title Name fixes...")
        
        results = {
            'document_type_fixes': 0,
            'link_field_fixes': 0,
            'naming_series_fixes': 0,
            'errors': []
        }
        
        try:
            # Fix document_type issues
            for issue in issues.get('document_type_issues', []):
                try:
                    doc = frappe.get_doc("DocType", issue['doctype'])
                    proper_name = ' '.join(word.capitalize() for word in issue['doctype'].split('_'))
                    if doc.document_type != proper_name:
                        doc.document_type = proper_name
                        doc.save()
                        results['document_type_fixes'] += 1
                        print(f"✅ Fixed document_type for {issue['doctype']}")
                except Exception as e:
                    results['errors'].append(f"document_type fix for {issue['doctype']}: {e}")
            
            # Fix link field issues
            for issue in issues.get('link_field_issues', []):
                try:
                    doc = frappe.get_doc("DocType", issue['doctype'])
                    for field in doc.fields:
                        if (field.fieldname == issue['field'] and 
                            field.options == issue['options']):
                            new_options = issue['options'].lower().replace(' ', '_')
                            field.options = new_options
                            doc.save()
                            results['link_field_fixes'] += 1
                            print(f"✅ Fixed {issue['doctype']}.{issue['field']}")
                            break
                except Exception as e:
                    results['errors'].append(f"link field fix for {issue['doctype']}.{issue['field']}: {e}")
            
            # Fix naming_series issues
            for doctype_name in issues.get('naming_series_issues', []):
                try:
                    doc = frappe.get_doc("DocType", doctype_name)
                    for field in doc.fields:
                        if field.fieldname == 'naming_series' and field.unique == 1:
                            field.unique = 0
                            doc.save()
                            results['naming_series_fixes'] += 1
                            print(f"✅ Fixed naming_series in {doctype_name}")
                            break
                except Exception as e:
                    results['errors'].append(f"naming_series fix for {doctype_name}: {e}")
            
            print(f"🎉 Fixes applied: {results['document_type_fixes']} document_type, "
                  f"{results['link_field_fixes']} link fields, "
                  f"{results['naming_series_fixes']} naming_series")
            
            return results
            
        except Exception as e:
            print(f"❌ Error during fix application: {e}")
            results['errors'].append(str(e))
            return results

# Usage example:
def usage_example():
    """
    Example of how to use the TitleNameFixer
    """
    fixer = TitleNameFixer()
    
    # Detect issues
    issues = fixer.detect_issues()
    
    # Apply fixes
    results = fixer.apply_fixes(issues)
    
    return issues, results

if __name__ == "__main__":
    print("TitleNameFixer - Frappe Title Name Resolution System")
    print("Based on AMB W SPC implementation experience")
