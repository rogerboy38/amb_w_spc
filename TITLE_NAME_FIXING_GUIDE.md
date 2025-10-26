# Title Name Fixing Guide for Frappe Doctypes

## Problem Statement
When migrating Frappe applications, a common issue occurs when doctypes have Title Names in link field options instead of actual snake_case doctype names. This causes migration failures and broken relationships.

## Solution Approach
1. **Analysis**: Export current doctypes and detect issues
2. **Fixing**: Apply document_type and link field corrections  
3. **Migration**: Run bench migrate with fixes applied
4. **Verification**: Test all doctypes and relationships

## Key Fixes Applied
- Fixed document_type from generic "Master"/"Document" to proper names
- Corrected link field options to reference actual doctype names
- Removed naming_series unique constraints
- Updated individual doctype JSON files

## Case Study: AMB W SPC App
- **69 doctypes** processed successfully
- **20 document_type** values fixed
- **24+ link fields** corrected
- **Zero migration errors** post-fix

## Prevention
- Use snake_case for all doctype names
- Validate link field references during development
- Regular fixture maintenance
- Pre-migration validation scripts
