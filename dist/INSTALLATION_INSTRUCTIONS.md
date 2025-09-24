# AMB W SPC Installation Instructions

## Quick Installation (Recommended)

### Method 1: Using Production Package

```bash
# 1. Download the production package
wget https://github.com/your-username/amb_w_spc/releases/latest/download/amb_w_spc_v1.0.0_production.tar.gz

# 2. Extract to your Frappe bench apps directory
cd /path/to/frappe-bench/apps
tar -xzf amb_w_spc_v1.0.0_production.tar.gz
mv amb_w_spc-1.0.0 amb_w_spc

# 3. Run the installation script
cd amb_w_spc
./install.sh
```

### Method 2: Using Frappe Bench

```bash
# 1. Navigate to your Frappe bench
cd /path/to/frappe-bench

# 2. Get the app
bench get-app https://github.com/your-username/amb_w_spc.git

# 3. Install on your site
bench --site your-site-name install-app amb_w_spc

# 4. Restart
bench restart
```

## Verification

After installation, verify everything is working:

```bash
# Check app installation
bench --site your-site-name list-apps

# Test the app
bench --site your-site-name console
>>> import amb_w_spc
>>> print("✅ AMB W SPC installed successfully!")
```

## Troubleshooting

If you encounter issues:

1. **Check system requirements**: Python 3.8+, Frappe 15.0+
2. **Review installation logs**: Check for error messages
3. **Validate dependencies**: Ensure all required packages are installed
4. **Clear cache**: `bench --site your-site clear-cache`
5. **Rebuild**: `bench build --app amb_w_spc`

For additional help, visit our [GitHub Issues](https://github.com/your-username/amb_w_spc/issues) page.
