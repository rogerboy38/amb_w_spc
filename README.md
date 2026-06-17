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

## Sensor Skill Registry

The `Sensor Skill` DocType (module: System Integration) is the canonical hardware registry for IoT sensors and scales. RPi clients read each skill's configuration via the whitelisted endpoint:

```python
amb_w_spc.api.sensor_skill.get_sensor_skill_config(skill_id="<id>")
```

The DocType lives in this app, but **records are seeded by external apps that manage specific deployments**. Current seed sources:

| Source app | Patch | Records seeded | Status |
|---|---|---|---|
| `amb_w_spc` (this app) | `patches/v15/04_create_sensor_skills_idempotent.py` | `scale_plant`, `scale_lab` | Legacy v1.0.0 templates — not yet run on erp.sysmayal2.cloud |
| `raven_ai_agent` | `patches/v0_3/create_sensor_skills_bot_iot_l01_and_fleet.py` | 5 production scale placeholders + 3 bot-iot-l01 testbed sensors | Active — seeded via bench migrate after PR merge |

### Production Scale Fleet (placeholder skill IDs)

| skill_id | Plant | Precision | Status |
|---|---|---|---|
| `scale_juice` | Juice Plant endpoint | 0.010 kg | Placeholder (enabled=0) |
| `scale_dry` | Dry Plant endpoint | 0.010 kg | Placeholder (enabled=0) |
| `scale_mix` | Mix Plant endpoint | 0.010 kg | Placeholder (enabled=0) |
| `scale_formulated` | Formulated Plant endpoint | 0.010 kg | Placeholder (enabled=0) |
| `scale_lab` | Laboratory Plant precision scale | 0.001 kg | Placeholder (enabled=0) |

Flip `enabled=1` per skill when the corresponding scale hardware is physically connected and `python_config` tuned to the actual driver (ModbusRTU vs SerialCommand) and protocol parameters.

### Naming Conventions

- `scale_<plant>` — production scales (Juice, Dry, Mix, Formulated plant-floor; Lab precision)
- `dev_l<NN>_<id>` — development testbed sensors on bot-iot-l<NN> (clearly non-production)
- Skill IDs are stable identifiers; never rename a seeded skill — RPi clients cache config by skill_id with 300s TTL.

See the [raven_ai_agent patch source](https://github.com/rogerboy38/raven_ai_agent/blob/main/raven_ai_agent/patches/v0_3/create_sensor_skills_bot_iot_l01_and_fleet.py) for the full skill catalog and `python_config` schema.