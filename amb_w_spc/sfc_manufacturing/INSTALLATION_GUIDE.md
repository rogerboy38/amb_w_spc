# AMB-SPC Installation Guide

## How to Generate DocTypes in Your Frappe Bench

### Problem Resolved
The issue you encountered was that the DocType JSON definition files were missing. I've now created all the necessary files for the DocTypes to be properly recognized by Frappe.

### Step-by-Step Installation Process

#### 1. Copy App to Your Bench
```bash
# Navigate to your Frappe bench directory
cd /path/to/your/frappe-bench

# Copy the amb_w_spc app folder to your apps directory
cp -r /path/to/amb_w_spc ./apps/

# Or clone from your repository if you've pushed it
# bench get-app https://github.com/your-username/amb_w_spc.git
```

#### 2. Install the App
```bash
# Install the app on your site
bench --site [your-site-name] install-app amb_w_spc

# Example:
# bench --site mysite.local install-app amb_w_spc
```

#### 3. Run Database Migration
```bash
# This creates the DocTypes in your database
bench --site [your-site-name] migrate

# Example:
# bench --site mysite.local migrate
```

#### 4. Build Assets (if needed)
```bash
# Build the frontend assets
bench build

# Or for development
bench build --dev
```

#### 5. Restart Bench
```bash
# Restart the bench to load the new app
bench restart
```

### Verification Steps

#### 1. Check DocTypes in Desk
After installation, you should see the following DocTypes in your ERPNext:

**Manufacturing Module:**
- SFC Transaction
- SFC Operator  
- SFC Operator Attendance
- Work Order Routing

**Statistical Process Control Module:**
- SPC Data Point
- SPC Control Chart

#### 2. Access DocTypes
You can access them through:
- **Desk → Manufacturing → SFC Operations**
- **Desk → Manufacturing → Quality Control**

#### 3. API Access
Test the APIs at:
- `/api/method/amb_w_spc.amb_w_spc.api.sfc_operations.start_operation`
- `/api/method/amb_w_spc.amb_w_spc.api.quality_integration.record_quality_measurement`

#### 4. Dashboard Access
Navigate to: `http://your-site/sfc-dashboard`

### File Structure Created
```
amb_w_spc/
├── setup.py
├── requirements.txt
├── hooks.py
├── modules.txt
├── README.md
└── amb_w_spc/
    ├── __init__.py
    ├── hooks.py
    ├── utils.py
    ├── doctype/
    │   ├── __init__.py
    │   ├── sfc_transaction/
    │   │   ├── __init__.py
    │   │   ├── sfc_transaction.json        # ← DocType Definition
    │   │   ├── sfc_transaction.py          # ← Controller
    │   │   ├── sfc_transaction.js          # ← Client Script
    │   │   └── test_sfc_transaction.py     # ← Tests
    │   ├── sfc_operator/
    │   │   ├── __init__.py
    │   │   ├── sfc_operator.json           # ← DocType Definition
    │   │   ├── sfc_operator.py             # ← Controller
    │   │   ├── sfc_operator.js             # ← Client Script
    │   │   └── test_sfc_operator.py        # ← Tests
    │   ├── work_order_routing/
    │   │   ├── __init__.py
    │   │   ├── work_order_routing.json     # ← DocType Definition
    │   │   ├── work_order_routing.py       # ← Controller
    │   │   ├── work_order_routing.js       # ← Client Script
    │   │   └── test_work_order_routing.py  # ← Tests
    │   ├── spc_data_point/
    │   │   ├── __init__.py
    │   │   ├── spc_data_point.json         # ← DocType Definition
    │   │   └── spc_data_point.py           # ← Controller
    │   └── spc_control_chart/
    │       ├── __init__.py
    │       ├── spc_control_chart.json      # ← DocType Definition
    │       └── spc_control_chart.py        # ← Controller
    ├── api/
    │   ├── __init__.py
    │   ├── sfc_operations.py               # ← REST APIs
    │   └── quality_integration.py          # ← Quality APIs
    └── www/
        ├── __init__.py
        ├── sfc_dashboard.py                # ← Dashboard Backend
        └── sfc_dashboard.html              # ← Dashboard Frontend
```

### Key Files That Were Missing (Now Created)

1. **DocType JSON Definition Files**: 
   - These `.json` files define the DocType structure (fields, permissions, etc.)
   - **Critical**: Without these, Frappe cannot create the DocTypes

2. **`__init__.py` Files**: 
   - Required for Python to recognize directories as packages

3. **App Structure Files**:
   - `setup.py` - App installation configuration
   - `requirements.txt` - Python dependencies

### Common Troubleshooting

#### Issue: "DocType not found"
**Solution**: Run `bench --site [site] migrate` to create DocTypes in database

#### Issue: "Permission Denied"
**Solution**: Assign proper roles to users:
```bash
# Add Manufacturing User role
bench --site [site] set-user-role [user] "Manufacturing User"
```

#### Issue: "Module not found"
**Solution**: Restart bench after installation:
```bash
bench restart
```

#### Issue: API not accessible
**Solution**: Check if app is properly installed:
```bash
bench --site [site] list-apps
```

### Testing the Installation

#### 1. Create Test Data
```python
# In Frappe console (bench --site [site] console)
from amb_w_spc.amb_w_spc.utils import create_sample_data
create_sample_data()
```

#### 2. Run Tests
```bash
# Run all tests
bench --site [site] run-tests amb_w_spc

# Run specific test
bench --site [site] run-tests amb_w_spc.amb_w_spc.doctype.sfc_transaction.test_sfc_transaction
```

#### 3. Test APIs
```bash
# Test SFC operation start
curl -X POST http://your-site/api/method/amb_w_spc.amb_w_spc.api.sfc_operations.start_operation \
  -H "Content-Type: application/json" \
  -d '{"work_order": "WO-001", "operation_sequence": 1, "workstation": "WS-001", "operator": "OP-001"}'
```

### Next Steps After Installation

1. **Configure Workstations**: Create workstation records in Manufacturing module
2. **Setup Operators**: Create SFC Operator records with skills
3. **Define Routings**: Create Work Order Routing for your products
4. **Start Production**: Use SFC Dashboard to monitor real-time operations

The app is now fully ready for installation and use!
