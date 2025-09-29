# AMB W SPC - Copy-Paste Deployment Guide

## 🚀 Quick Deploy Commands (Copy & Paste Ready)

### Option 1: One-Line Production Install

```bash
curl -sSL https://raw.githubusercontent.com/your-username/amb_w_spc/main/install.sh | bash
```

### Option 2: Manual Production Install

```bash
# Step 1: Navigate to your Frappe bench
cd /path/to/frappe-bench

# Step 2: Download and extract latest release  
wget https://github.com/your-username/amb_w_spc/releases/latest/download/amb_w_spc_v1.0.0_production.tar.gz
tar -xzf amb_w_spc_v1.0.0_production.tar.gz -C apps/
mv apps/amb_w_spc-* apps/amb_w_spc

# Step 3: Install the app
bench --site YOUR_SITE_NAME install-app amb_w_spc

# Step 4: Restart and build
bench restart && bench build --app amb_w_spc
```

### Option 3: GitHub Clone Install

```bash
# Step 1: Navigate to Frappe bench
cd /path/to/frappe-bench

# Step 2: Clone repository
bench get-app https://github.com/your-username/amb_w_spc.git

# Step 3: Install on site
bench --site YOUR_SITE_NAME install-app amb_w_spc

# Step 4: Restart
bench restart
```

### Option 4: Quick Test Install

```bash
# For quick testing - downloads minimal package
cd /tmp
wget https://github.com/your-username/amb_w_spc/releases/latest/download/amb_w_spc_v1.0.0_quick.tar.gz
tar -xzf amb_w_spc_v1.0.0_quick.tar.gz
cd amb_w_spc
./quick_install.sh
```

## 🎯 GitHub Repository Setup Commands

### For Repository Owners

```bash
# Step 1: Create new repository on GitHub (amb_w_spc)

# Step 2: Clone and setup
git clone https://github.com/your-username/amb_w_spc.git
cd amb_w_spc

# Step 3: Copy production-ready code
cp -r /path/to/workspace/amb_w_spc_PRODUCTION_READY/* .

# Step 4: Initial commit
git add .
git commit -m "feat: initial release v1.0.0 - production ready AMB W SPC"
git push origin main

# Step 5: Create release
git tag v1.0.0
git push origin v1.0.0
```

### For GitHub Release Creation

```bash
# After pushing code, create GitHub release:
# 1. Go to: https://github.com/your-username/amb_w_spc/releases/new
# 2. Tag version: v1.0.0  
# 3. Release title: AMB W SPC v1.0.0 - Production Ready
# 4. Description: Copy from dist/RELEASE_NOTES.md
# 5. Upload files:
#    - amb_w_spc_v1.0.0_production.tar.gz
#    - amb_w_spc_v1.0.0_github.tar.gz  
#    - amb_w_spc_v1.0.0_quick.tar.gz
#    - checksums.sha256
#    - INSTALLATION_INSTRUCTIONS.md
```

## ✅ Post-Installation Validation

### Quick Validation Commands

```bash
# Check app installation
bench --site YOUR_SITE_NAME list-apps | grep amb_w_spc

# Test app import
bench --site YOUR_SITE_NAME console <<< "import amb_w_spc; print('✅ Success!')"

# Check database setup
bench --site YOUR_SITE_NAME execute "frappe.get_doc('DocType', 'SPC Data Point')"

# Verify modules
bench --site YOUR_SITE_NAME execute "print([d.name for d in frappe.get_all('Module Def')])"
```

### Full System Test

```bash
# Run comprehensive test
cd /path/to/frappe-bench/apps/amb_w_spc
python test_installation.py

# Expected output:
# ✅ All 56 JSON files are valid
# ✅ All 132 Python files have valid syntax  
# ✅ hooks.py is valid and has required attributes
# ✅ modules.txt lists 10 modules
# ✅ All compatibility tests passed!
# 🚀 App is ready for Frappe installation
```

## 🎛️ First Setup Commands

### Initial Configuration (Copy & Paste)

```bash
# Access your site
bench --site YOUR_SITE_NAME browse

# Or manually navigate to:
# http://localhost:8000 (development)
# https://yourdomain.com (production)

# Login and run these commands in console:
bench --site YOUR_SITE_NAME console
```

```python
# In Frappe console - Initial setup
import amb_w_spc.system_integration.installation.install_spc_system as setup

# Setup basic system data
setup.setup_system()

# Create sample data (optional)
import amb_w_spc.fixtures.create_sample_data as sample
sample.create_all_samples()

print("✅ AMB W SPC Setup Complete!")
```

## 📊 Verification Dashboard Access

After installation, access these key areas:

### 1. SPC Dashboard
```
URL: /app/spc-dashboard
Quick Access: Ctrl+G → type "spc"
```

### 2. Manufacturing Operations
```
URL: /app/manufacturing-operations
Menu: Manufacturing > Operations
```

### 3. Shop Floor Control
```
URL: /app/shop-floor-dashboard  
Menu: Manufacturing > Shop Floor Control
```

### 4. Real-time Monitoring
```
URL: /app/real-time-monitoring
Menu: Manufacturing > Real-time Monitoring
```

## 🔧 Environment Variables (Optional)

```bash
# Add to your site_config.json for enhanced features:

# Redis configuration for real-time features
redis_cache: "redis://localhost:6379/1"
redis_queue: "redis://localhost:6379/2"

# Email configuration for alerts
mail_server: "smtp.gmail.com"
mail_port: 587
use_tls: 1
mail_login: "your-email@gmail.com"
mail_password: "your-app-password"

# Real-time configuration
socketio_port: 9000
auto_commit_on_many_writes: 1
```

## 🚨 Common Issues & Quick Fixes

### Issue 1: Permission Denied
```bash
# Fix: Set proper permissions
sudo chown -R $(whoami):$(whoami) /path/to/frappe-bench
```

### Issue 2: Node.js Assets Build Failed
```bash
# Fix: Rebuild assets
bench build --app amb_w_spc --force
```

### Issue 3: Database Connection Error
```bash
# Fix: Restart services
sudo service mysql restart
bench restart
```

### Issue 4: Import Errors
```bash
# Fix: Clear cache and rebuild
bench --site YOUR_SITE_NAME clear-cache
bench --site YOUR_SITE_NAME migrate
```

### Issue 5: Scheduler Not Working
```bash
# Fix: Enable and restart scheduler
bench --site YOUR_SITE_NAME enable-scheduler
bench restart
```

## 📱 Mobile Access Setup

```bash
# Enable mobile app (optional)
bench --site YOUR_SITE_NAME set-config mobile_app 1

# Create mobile user
bench --site YOUR_SITE_NAME add-user mobile@yourcompany.com --first-name Mobile --last-name User
```

## 🔄 Backup & Recovery Commands

### Create Backup
```bash
# Full backup
bench --site YOUR_SITE_NAME backup --with-files

# Database only
bench --site YOUR_SITE_NAME backup
```

### Restore Backup
```bash
# Restore from backup
bench --site YOUR_SITE_NAME restore /path/to/backup/file.sql.gz
```

## 🎉 Success Indicators

After successful installation, you should see:

- ✅ **Menu Items**: Manufacturing > SPC Setup, Operations, etc.
- ✅ **DocTypes**: 49 new doctypes available
- ✅ **Modules**: 15 modules in Module Def
- ✅ **Dashboards**: SPC and Manufacturing dashboards accessible  
- ✅ **Scheduler**: Background jobs running (check Scheduled Job Type)
- ✅ **No Errors**: Clean error logs

## 📞 Getting Help

If you encounter issues:

1. **Check logs**: `tail -f /path/to/frappe-bench/logs/bench.log`
2. **Review documentation**: [GitHub Wiki](https://github.com/your-username/amb_w_spc/wiki)
3. **Search issues**: [GitHub Issues](https://github.com/your-username/amb_w_spc/issues)
4. **Ask community**: [GitHub Discussions](https://github.com/your-username/amb_w_spc/discussions)
5. **Contact support**: support@ambsystems.com

---

**🚀 Ready to revolutionize your manufacturing operations with AMB W SPC!**