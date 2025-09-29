# AMB W SPC - Troubleshooting Guide

## 🔍 Quick Diagnostics

### Health Check Command
```bash
# Run this first for overall system health
cd /path/to/frappe-bench
bench doctor
```

### App-Specific Health Check
```bash
# Check AMB W SPC installation
cd apps/amb_w_spc
python test_installation.py
```

## 🚨 Common Installation Issues

### 1. Permission Denied Errors

**Symptoms:**
- "Permission denied" during installation
- Cannot write to directories
- Bench commands fail

**Solutions:**
```bash
# Fix ownership
sudo chown -R $(whoami):$(whoami) /path/to/frappe-bench

# Fix permissions  
chmod -R 755 /path/to/frappe-bench
chmod +x /path/to/frappe-bench/env/bin/*

# Specific to AMB W SPC
chmod +x apps/amb_w_spc/install.sh
```

### 2. Python Import Errors

**Symptoms:**
- `ModuleNotFoundError: No module named 'amb_w_spc'`
- Import errors during installation

**Solutions:**
```bash
# Reinstall app
bench --site YOUR_SITE uninstall-app amb_w_spc --force
bench --site YOUR_SITE install-app amb_w_spc

# Check Python path
bench --site YOUR_SITE console
>>> import sys
>>> print('\n'.join(sys.path))

# Rebuild app
bench build --app amb_w_spc
```

### 3. Database Schema Errors

**Symptoms:**
- DocType not found errors
- Database table missing
- Migration failures

**Solutions:**
```bash
# Run migrations
bench --site YOUR_SITE migrate

# Force sync schema
bench --site YOUR_SITE console
>>> frappe.db.commit()
>>> frappe.reload_doctype("SPC Data Point")

# Clear cache and retry
bench --site YOUR_SITE clear-cache
bench restart
```

### 4. Node.js Build Failures

**Symptoms:**
- Asset build failures
- JavaScript/CSS not loading
- "npm" or "node" not found

**Solutions:**
```bash
# Check Node.js version
node --version  # Should be 16+
npm --version

# Install Node.js if missing
curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt-get install -y nodejs

# Rebuild assets
bench build --app amb_w_spc --force
bench restart
```

## 🔧 Runtime Issues

### 1. Scheduler Problems

**Symptoms:**
- Background jobs not running
- SPC alerts not triggering
- Data collection stopped

**Diagnostics:**
```bash
# Check scheduler status
bench --site YOUR_SITE execute frappe.utils.scheduler.is_scheduler_disabled

# List scheduled jobs
bench --site YOUR_SITE execute "print(frappe.get_all('Scheduled Job Type', fields=['name', 'frequency']))"

# Check last job execution
bench --site YOUR_SITE execute "print(frappe.get_all('Scheduled Job Log', fields=['*'], limit=10))"
```

**Solutions:**
```bash
# Enable scheduler
bench --site YOUR_SITE enable-scheduler

# Restart with scheduler
bench restart
supervisor restart all  # If using supervisor

# Manual job execution (testing)
bench --site YOUR_SITE execute amb_w_spc.shop_floor_control.scheduler.collect_sensor_data
```

### 2. Real-time Features Not Working

**Symptoms:**
- Dashboards not updating
- Sensor data not appearing
- WebSocket connection issues

**Diagnostics:**
```bash
# Check Redis connection
redis-cli ping  # Should return "PONG"

# Check WebSocket server
netstat -tlnp | grep 9000  # Check if socketio is running

# Test real-time events
bench --site YOUR_SITE console
>>> frappe.publish_realtime("test_event", {"message": "hello"})
```

**Solutions:**
```bash
# Start Redis if not running
sudo service redis-server start

# Restart socketio
bench restart

# Configure Redis in site_config.json
{
    "redis_cache": "redis://localhost:6379/1",
    "redis_queue": "redis://localhost:6379/2",
    "socketio_port": 9000
}
```

### 3. SPC Calculations Not Working

**Symptoms:**
- Control charts showing no data
- Alert calculations failing
- Process capability values incorrect

**Diagnostics:**
```bash
# Check SPC data points
bench --site YOUR_SITE execute "print(frappe.db.count('SPC Data Point'))"

# Test calculation functions
bench --site YOUR_SITE console
>>> from amb_w_spc.core_spc.spc_calculations import calculate_control_limits
>>> calculate_control_limits([1,2,3,4,5])  # Should return dict with UCL, LCL
```

**Solutions:**
```bash
# Install required Python packages
pip install numpy scipy matplotlib pandas

# Re-run SPC setup
bench --site YOUR_SITE execute amb_w_spc.system_integration.installation.install_spc_system.setup_spc_parameters

# Check and fix data
bench --site YOUR_SITE execute "
doc = frappe.get_doc('SPC Parameter Master', 'YOUR_PARAMETER')
doc.calculate_control_limits()
doc.save()
"
```

## 📊 Performance Issues

### 1. Slow Dashboard Loading

**Symptoms:**
- Dashboards take >10 seconds to load
- Browser becomes unresponsive
- High CPU usage

**Diagnostics:**
```bash
# Check database performance
bench --site YOUR_SITE execute "
import time
start = time.time()
frappe.db.sql('SELECT COUNT(*) FROM `tabSPC Data Point`')
print(f'Query time: {time.time() - start:.2f}s')
"

# Monitor system resources
top -p $(pgrep -f "frappe")
```

**Solutions:**
```bash
# Add database indexes
bench --site YOUR_SITE execute "
frappe.db.sql('CREATE INDEX IF NOT EXISTS idx_spc_timestamp ON `tabSPC Data Point`(timestamp)')
frappe.db.sql('CREATE INDEX IF NOT EXISTS idx_spc_parameter ON `tabSPC Data Point`(parameter)')
"

# Enable caching
# Add to site_config.json:
{
    "enable_frappe_cache": true,
    "cache_redis_server": "redis://localhost:6379/3"
}

# Archive old data
bench --site YOUR_SITE execute amb_w_spc.sensor_management.scheduler.archive_old_sensor_data
```

### 2. Memory Issues

**Symptoms:**
- Out of memory errors
- Process getting killed
- System becoming unresponsive

**Solutions:**
```bash
# Increase worker memory limits
# In common_site_config.json:
{
    "gunicorn_workers": 2,
    "background_workers": 1,
    "max_requests": 5000,
    "max_requests_jitter": 500
}

# Monitor memory usage
bench --site YOUR_SITE execute "
import psutil
print(f'Memory usage: {psutil.virtual_memory().percent}%')
"

# Clear old logs and cache
bench --site YOUR_SITE clear-cache
find /path/to/frappe-bench/logs -name "*.log" -mtime +7 -delete
```

## 🔒 Security Issues

### 1. Authentication Problems

**Symptoms:**
- Cannot login to system
- API authentication fails
- Role permissions not working

**Solutions:**
```bash
# Reset admin password
bench --site YOUR_SITE set-admin-password NEW_PASSWORD

# Check user roles
bench --site YOUR_SITE execute "
user = frappe.get_doc('User', 'your-user@email.com')
print(user.get_roles())
"

# Grant required roles
bench --site YOUR_SITE execute "
frappe.get_doc('User', 'your-user@email.com').add_roles('Manufacturing Manager', 'SPC Operator')
"
```

### 2. API Access Issues

**Symptoms:**
- API calls returning 403/401
- Cannot access REST endpoints
- Token authentication failing

**Solutions:**
```bash
# Generate API token
bench --site YOUR_SITE console
>>> user = frappe.get_doc("User", "your-user@email.com")
>>> api_key = frappe.generate_hash(length=15)
>>> api_secret = frappe.generate_hash(length=15)
>>> user.api_key = api_key
>>> user.api_secret = api_secret
>>> user.save()
>>> print(f"API Key: {api_key}")
>>> print(f"API Secret: {api_secret}")

# Test API access
curl -H "Authorization: token API_KEY:API_SECRET" \
     http://localhost:8000/api/resource/SPC%20Data%20Point
```

## 🌐 Network & Connectivity

### 1. External API Integration Issues

**Symptoms:**
- Sensor data not being received
- Third-party API calls failing
- Network timeouts

**Solutions:**
```bash
# Test network connectivity
ping sensor-gateway.local
telnet sensor-gateway.local 8080

# Check firewall rules
sudo ufw status
sudo iptables -L

# Test API endpoints
curl -v http://your-sensor-api/health

# Configure proxy if needed (site_config.json):
{
    "http_proxy": "http://proxy.company.com:8080",
    "https_proxy": "http://proxy.company.com:8080"
}
```

## 🗃️ Data Issues

### 1. Missing or Corrupted Data

**Symptoms:**
- Charts showing no data
- Historical data missing
- Inconsistent calculations

**Diagnostics:**
```bash
# Check data integrity
bench --site YOUR_SITE execute "
import frappe
from datetime import datetime, timedelta

# Check recent data
recent = frappe.db.sql('''
    SELECT parameter, COUNT(*) as count, 
           MIN(timestamp) as first, MAX(timestamp) as last
    FROM `tabSPC Data Point` 
    WHERE timestamp > %s 
    GROUP BY parameter
''', (datetime.now() - timedelta(days=1),), as_dict=True)

for row in recent:
    print(f'{row.parameter}: {row.count} points from {row.first} to {row.last}')
"
```

**Solutions:**
```bash
# Data cleanup and repair
bench --site YOUR_SITE execute "
# Remove duplicates
frappe.db.sql('''
    DELETE t1 FROM `tabSPC Data Point` t1
    INNER JOIN `tabSPC Data Point` t2 
    WHERE t1.name > t2.name 
    AND t1.parameter = t2.parameter 
    AND t1.timestamp = t2.timestamp
''')

# Recalculate control limits
for param in frappe.get_all('SPC Parameter Master'):
    doc = frappe.get_doc('SPC Parameter Master', param.name)
    doc.calculate_control_limits()
    doc.save()
"

# Restore from backup if needed
bench --site YOUR_SITE restore /path/to/backup.sql.gz
```

## 🔨 Advanced Troubleshooting

### Debug Mode Commands

```bash
# Enable developer mode
bench --site YOUR_SITE set-config developer_mode 1
bench restart

# Enable SQL query logging
bench --site YOUR_SITE set-config log_queries 1

# Detailed error tracking
bench --site YOUR_SITE set-config debug_console 1
```

### Log Analysis

```bash
# View real-time logs
tail -f /path/to/frappe-bench/logs/bench.log

# Search for specific errors
grep -r "amb_w_spc" /path/to/frappe-bench/logs/

# Analyze error patterns
grep -E "(ERROR|CRITICAL)" /path/to/frappe-bench/logs/bench.log | tail -20
```

### Database Query Optimization

```bash
# Identify slow queries
bench --site YOUR_SITE execute "
import frappe
frappe.db.sql('SET profiling = 1')
# Run your problematic operation here
frappe.db.sql('SHOW PROFILES')
"

# Analyze table sizes
bench --site YOUR_SITE execute "
tables = frappe.db.sql('''
    SELECT table_name, 
           ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
    FROM information_schema.tables 
    WHERE table_schema = %s 
    AND table_name LIKE 'tab%'
    ORDER BY size_mb DESC 
    LIMIT 10
''', frappe.db.get_default('db_name'), as_dict=True)

for table in tables:
    print(f'{table.table_name}: {table.size_mb} MB')
"
```

## 📞 Getting Additional Help

### Before Seeking Support

1. **Collect System Information:**
```bash
# Generate system report
bench --site YOUR_SITE execute "
import platform, sys, frappe
print(f'OS: {platform.system()} {platform.release()}')
print(f'Python: {sys.version}')
print(f'Frappe: {frappe.__version__}')
print(f'AMB W SPC: {frappe.get_attr(\"amb_w_spc.__version__\")}')
"
```

2. **Gather Log Files:**
```bash
# Create support bundle
mkdir support_bundle_$(date +%Y%m%d)
cp /path/to/frappe-bench/logs/bench.log support_bundle_*/
cp /path/to/frappe-bench/sites/YOUR_SITE/site_config.json support_bundle_*/
tar -czf support_bundle_$(date +%Y%m%d).tar.gz support_bundle_*/
```

3. **Document Issue:**
   - Exact error messages
   - Steps to reproduce
   - Expected vs actual behavior
   - System environment details

### Support Channels

- **GitHub Issues**: [Create Issue](https://github.com/your-username/amb_w_spc/issues/new)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/amb_w_spc/discussions)
- **Email Support**: support@ambsystems.com
- **Community Forum**: [Frappe Community](https://discuss.frappe.io/)

---

## 🎯 Prevention Tips

1. **Regular Monitoring:**
   - Set up log rotation
   - Monitor disk space
   - Check backup integrity

2. **Maintenance Schedule:**
   - Weekly: Clear old logs and cache
   - Monthly: Archive old data  
   - Quarterly: Performance optimization

3. **Keep Updated:**
   - Monitor GitHub releases
   - Update dependencies regularly
   - Test updates in staging first

**Remember: Most issues can be resolved by following these systematic troubleshooting steps!** 🚀