# check_batch_amb_structure.py
import json

batch_amb_path = "amb_w_spc/sfc_manufacturing/doctype/batch_amb/batch_amb.json"

with open(batch_amb_path, 'r') as f:
    data = json.load(f)

print("Batch AMB doctype structure:")
print(f"Title field: {data.get('title_field')}")
print("Fields:")
for field in data.get('fields', []):
    if field.get('fieldname') == 'title':
        print(f"  ✓ Found title field: {field}")
        break
else:
    print("  ❌ No title field found - this will cause issues!")
