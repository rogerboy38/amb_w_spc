# AMB W SPC - Advanced Manufacturing & Statistical Process Control

**Version:** 1.0.1  
**Compatibility:** ERPNext v15+ (includes Frappe v15.84.0+ compatibility fix)  
**License:** MIT

## Overview

AMB W SPC is a comprehensive ERPNext application designed for advanced manufacturing environments. It integrates Statistical Process Control (SPC), Shop Floor Control (SFC), and real-time manufacturing operations management.

## Key Features

- **Real-time Control Charts:** Monitor process parameters with live statistical analysis
- **Production Monitoring:** Track work orders, equipment status, and operator performance
- **IoT Device Integration:** Connect sensors and PLCs for automated data collection
- **Quality Management:** FDA-compliant tools including audit trails and electronic signatures
- **Shop Floor Control:** Comprehensive SFC functionality for production management
- **Plant Equipment Management:** Track and monitor manufacturing equipment

## Installation

### Frappe Cloud Installation

This version includes automatic fixes for Frappe v15.84.0 installation issues.

1. **Upload to your Frappe Cloud:**
   ```bash
   # Option 1: Upload via web interface
   # - Go to your Frappe Cloud dashboard
   # - Upload the amb_w_spc folder
   
   # Option 2: Git deployment
   git clone [your-repo-url]
   cd frappe-bench
   bench get-app [your-repo-url]
   ```

2. **Install the app:**
   ```bash
   bench --site [your-site] install-app amb_w_spc
   ```

3. **Verification:**
   ```bash
   bench --site [your-site] console
   ```
   ```python
   # In the console:
   from amb_w_spc.install import check_installation
   check_installation()
   ```

### Local Development Installation

```bash
# Get the app
bench get-app [repo-url]

# Install on your site
bench --site [site-name] install-app amb_w_spc

# Start development
bench start
```

## Compatibility Notes

### Frappe v15.84.0 Fix

This version automatically handles the known module installation bug in Frappe v15.84.0 where the installer tries to use v16 database field names on a v15 schema.

**Automatic Fix Included:**
- ✅ Patch-based module creation
- ✅ Multiple fallback methods
- ✅ Comprehensive error handling
- ✅ Detailed logging for troubleshooting

## Modules

The application includes 10 specialized modules:

1. **core_spc** - Core SPC functionality
2. **spc_quality_management** - Quality management tools
3. **sfc_manufacturing** - Shop floor control
4. **operator_management** - Operator tracking and management
5. **shop_floor_control** - Production line control
6. **plant_equipment** - Equipment management
7. **real_time_monitoring** - Live data monitoring
8. **sensor_management** - IoT sensor integration
9. **system_integration** - System integration tools
10. **fda_compliance** - FDA compliance features

## Support

For issues related to:
- **Installation:** Check the automatic compatibility patches
- **Frappe Cloud:** All fixes are designed to work without shell access
- **Development:** Standard ERPNext development practices apply

## License

MIT License - see LICENSE file for details.

## Version History

### v1.0.1
- ✅ Fixed Frappe v15.84.0 installation compatibility
- ✅ Added automatic patch system
- ✅ Enhanced error handling and logging
- ✅ Multiple installation fallback methods
- ✅ Frappe Cloud deployment ready