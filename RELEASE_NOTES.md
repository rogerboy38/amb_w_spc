# AMB W SPC v1.0.1 - Release Notes
## Frappe v15.84.0 Compatibility Fix

### 🎯 Purpose
This release specifically addresses the critical installation error in Frappe v15.84.0 where the module installer fails with:
```
pymysql.err.OperationalError: (1054, "Unknown column 'parent' in 'INSERT INTO'")
```

### ✅ What's Fixed
- **Automatic Compatibility Detection**: App detects Frappe version and applies appropriate installation method
- **Patch-Based Installation**: Uses Frappe's patch system for automatic module creation
- **Multiple Fallback Methods**: 3 different installation approaches for maximum reliability
- **Enhanced Logging**: Comprehensive logging for troubleshooting
- **Cloud-Ready**: Designed specifically for Frappe Cloud deployment without shell access

### 🚀 Key Features
1. **Zero Manual Intervention**: Patches run automatically during installation
2. **Backward Compatible**: Works with Frappe v15.0+ including the problematic v15.84.0
3. **Production Ready**: Includes all necessary files for immediate deployment
4. **Comprehensive Documentation**: Multiple guides and troubleshooting resources

### 📁 Package Contents
```
amb_w_spc/
├── hooks.py                       # App configuration (modules commented out)
├── install.py                     # Enhanced installation with multiple methods
├── patches.txt                    # Patch registration for automatic execution
├── patches/v15/fix_module_installation.py  # The automatic fix
├── README.md                      # Complete documentation
├── INSTALLATION_GUIDE.md          # Step-by-step installation
├── DEPLOYMENT_GUIDE.md            # Production deployment guide
├── LICENSE                        # MIT License
├── requirements.txt               # Dependencies
└── setup.py                       # Python package configuration
```

### 🔧 Technical Solution
**Problem Root Cause**: Frappe v15.84.0 installer code was updated for v16 compatibility but tries to insert data into columns (`parent`, `parentfield`, `parenttype`) that don't exist in v15 database schema.

**Solution Approach**: 
1. Remove problematic module creation from `hooks.py`
2. Use Frappe's patch system to create modules after installation
3. Implement v15-compatible SQL queries that only use existing database fields
4. Provide multiple fallback methods for maximum reliability

### 🎯 Installation Process
1. **Standard Installation**: `bench install-app amb_w_spc`
2. **Automatic Patch Execution**: Patch runs during installation
3. **Module Creation**: Uses v15-compatible methods
4. **Verification**: Built-in verification functions

### 🔍 Verification
After installation, verify with:
```python
from amb_w_spc.install import check_installation
check_installation()
```

### 🌐 Cloud Compatibility
- ✅ Frappe Cloud ready
- ✅ No shell access required
- ✅ Automatic patch execution
- ✅ Comprehensive error handling

### 📞 Support
- Installation issues are automatically logged
- Built-in verification commands
- Multiple fallback methods reduce failure risk
- Compatible with all Frappe v15+ versions

### 🔄 Migration from Previous Versions
If updating from a previous version:
1. Replace old files with this package
2. Commit and push to your repository
3. Redeploy via Frappe Cloud
4. Patches will handle any necessary updates

**This version is the definitive solution for Frappe v15.84.0 compatibility issues.**