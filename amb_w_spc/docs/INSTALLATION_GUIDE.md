# AMB W SPC Installation Guide
## Frappe v15.84.0+ Compatible Version

### Quick Installation (Frappe Cloud)

This version is specifically designed to work on Frappe Cloud with automatic fixes for the v15.84.0 module installation bug.

#### Step 1: Get the App
```bash
# Method 1: Direct upload to Frappe Cloud
# Upload the amb_w_spc folder to your Frappe Cloud instance

# Method 2: Git deployment (recommended)
# Push this code to your Git repository and use Frappe Cloud's Git integration
```

#### Step 2: Install
```bash
# On Frappe Cloud or local bench
bench --site [your-site-name] install-app amb_w_spc
```

#### Step 3: Verify Installation
```bash
# Check via console
bench --site [your-site-name] console
```

In the Frappe console:
```python
from amb_w_spc.install import check_installation
check_installation()
```

Expected output:
```
=== AMB W SPC Installation Verification ===
Checking modules:
✅ core_spc
✅ spc_quality_management
✅ sfc_manufacturing
✅ operator_management
✅ shop_floor_control
✅ plant_equipment
✅ real_time_monitoring
✅ sensor_management
✅ system_integration
✅ fda_compliance

✅ AMB W SPC app import successful

🎉 All 10 modules are properly installed!
```

### What's Different in This Version

#### Automatic Frappe v15.84.0 Fix
- **Problem:** Frappe v15.84.0 has a bug where module installation fails with "Unknown column 'parent' in 'INSERT INTO'"
- **Solution:** This version includes automatic patches that fix the installation

#### Key Improvements
1. **Patch System:** Automatic module creation via `patches/v15/fix_module_installation.py`
2. **Multiple Fallbacks:** 3 different installation methods for maximum reliability
3. **Enhanced Logging:** Detailed logs for troubleshooting
4. **Cloud Ready:** Designed specifically for Frappe Cloud deployment

### Installation Methods Included

This app tries multiple installation approaches automatically:

1. **Standard Method:** Normal ERPNext module creation
2. **Compatibility Method:** Direct SQL with v15-compatible fields only
3. **Emergency Method:** Most basic SQL insertion as final fallback

### Troubleshooting

#### If Installation Fails

**Check the logs:**
```bash
# View installation logs
tail -f ~/frappe-bench/logs/worker.log
```

**Manual verification:**
```bash
bench --site [site-name] console
```

```python
# Check which modules exist
import frappe
modules = ['core_spc', 'spc_quality_management', 'sfc_manufacturing', 'operator_management', 'shop_floor_control', 'plant_equipment', 'real_time_monitoring', 'sensor_management', 'system_integration', 'fda_compliance']

for module in modules:
    exists = frappe.db.exists('Module Def', module)
    print(f"{module}: {'✅' if exists else '❌'}")
```

**Manual fix (if needed):**
```python
# Run this only if automatic installation failed
from amb_w_spc.install import create_modules_v15_safe
create_modules_v15_safe()
```

#### Common Issues

1. **"Unknown column 'parent'"** - Fixed automatically by patches
2. **Import errors** - Check that ERPNext v15+ is installed
3. **Permission errors** - Ensure proper Frappe Cloud permissions

### Local Development Setup

```bash
# Clone and setup
git clone [your-repo-url]
cd frappe-bench
bench get-app [repo-path]
bench --site [site-name] install-app amb_w_spc

# Start development
bench start
```

### Production Deployment

This version is ready for production deployment on:
- ✅ Frappe Cloud
- ✅ Self-hosted Frappe/ERPNext
- ✅ Docker deployments
- ✅ Traditional VPS setups

### Support

For installation issues:
1. Check the automatic logs in `worker.log`
2. Use the verification console commands above
3. The patch system handles most compatibility issues automatically

### Version Information

- **Version:** 1.0.1
- **Frappe Compatibility:** v15.0+ (including v15.84.0+ fix)
- **ERPNext Compatibility:** v15.0+
- **Python:** 3.8+