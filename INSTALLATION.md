# AMB_W_SPC System Installation Guide

## Table of Contents
1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Prerequisites](#prerequisites)
4. [Pre-Installation Checklist](#pre-installation-checklist)
5. [Installation Procedures](#installation-procedures)
6. [Post-Installation Configuration](#post-installation-configuration)
7. [Module Activation Sequence](#module-activation-sequence)
8. [Database Setup and Configuration](#database-setup-and-configuration)
9. [User Creation and Role Assignment](#user-creation-and-role-assignment)
10. [Initial System Configuration](#initial-system-configuration)
11. [Verification Procedures](#verification-procedures)
12. [Troubleshooting Common Issues](#troubleshooting-common-issues)
13. [Maintenance and Updates](#maintenance-and-updates)

## Overview

The AMB_W_SPC (Statistical Process Control) system is a comprehensive, FDA-compliant quality management solution designed for seamless integration with ERPNext. This installation guide provides system administrators with detailed procedures for deploying the system in production environments.

### Key Features
- 25+ custom DocTypes for comprehensive quality management
- 6-tier role-based permission system with plant-based multi-tenancy
- 4 automated workflows for quality processes
- FDA 21 CFR Part 11 compliance with electronic signatures
- PLC integration capabilities for automated data collection
- Real-time SPC monitoring and alerting

## System Requirements

### Minimum Hardware Requirements
- **RAM**: 4GB minimum, 8GB recommended for production
- **Storage**: 10GB free space minimum
- **CPU**: Multi-core processor (2+ cores recommended)
- **Network**: Stable internet connection for updates and external integrations

### Production Hardware Recommendations
- **RAM**: 16GB or higher for multi-plant environments
- **Storage**: 50GB+ with SSD for optimal performance
- **CPU**: 4+ cores for high-volume data processing
- **Network**: Dedicated network interface for PLC integration

### Software Requirements

#### Core Dependencies
- **ERPNext**: Version 14.0.0 or higher
- **Frappe Framework**: Version 14.0.0 or higher
- **Python**: Version 3.8 or higher
- **Node.js**: Version 14.x or higher
- **npm**: Version 6.x or higher

#### Database Requirements
Choose one of the following database systems:
- **MariaDB**: Version 10.3 or higher (recommended)
- **PostgreSQL**: Version 12 or higher

#### Operating System Support
- **Ubuntu**: 20.04 LTS or higher (recommended)
- **CentOS**: 8 or higher
- **Debian**: 10 or higher
- **Red Hat Enterprise Linux**: 8 or higher

#### Additional Software
- **Redis**: Version 5.0 or higher (for caching and job queuing)
- **Nginx**: Version 1.18 or higher (for web server)
- **Supervisor**: For process management
- **wkhtmltopdf**: Version 0.12.6 with patched qt (for PDF generation)

## Prerequisites

### 1. ERPNext Installation

Ensure you have a working ERPNext installation before proceeding. If you need to install ERPNext:

```bash
# Install Frappe Bench
pip3 install frappe-bench

# Create a new bench
bench init my-frappe-bench --frappe-branch version-14

# Change to bench directory
cd my-frappe-bench

# Create a new site
bench new-site your-site-name.local

# Install ERPNext
bench get-app --branch version-14 erpnext
bench --site your-site-name.local install-app erpnext
```

### 2. Database Preparation

#### For MariaDB:
```sql
-- Create database with proper charset
CREATE DATABASE erpnext_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user and grant permissions
CREATE USER 'erpnext_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON erpnext_db.* TO 'erpnext_user'@'localhost';
FLUSH PRIVILEGES;
```

#### For PostgreSQL:
```sql
-- Create database
CREATE DATABASE erpnext_db WITH ENCODING 'UTF8' LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8';

-- Create user and grant permissions
CREATE USER erpnext_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE erpnext_db TO erpnext_user;
```

### 3. System User Setup

Create a dedicated system user for running the application:

```bash
# Create erpnext user
sudo adduser erpnext --home /home/erpnext

# Add to required groups
sudo usermod -aG sudo erpnext

# Switch to erpnext user
sudo su - erpnext
```

### 4. Required Python Packages

Install additional Python packages required by the SPC system:

```bash
# Install statistical computing packages
pip3 install numpy scipy pandas matplotlib seaborn

# Install database connectors
pip3 install pymysql psycopg2-binary

# Install API and automation packages
pip3 install requests celery redis

# Install PDF and reporting packages
pip3 install reportlab weasyprint
```

## Pre-Installation Checklist

Before starting the installation, verify all requirements are met:

### ✅ System Verification Checklist

```bash
# Check Python version
python3 --version  # Should be >= 3.8

# Check Node.js version
node --version  # Should be >= 14.x

# Check database connectivity
mysql -u erpnext_user -p -e "SELECT VERSION();"  # For MariaDB
# OR
psql -U erpnext_user -d erpnext_db -c "SELECT version();"  # For PostgreSQL

# Check Redis connectivity
redis-cli ping  # Should return PONG

# Check disk space
df -h  # Ensure at least 10GB free

# Check memory
free -h  # Ensure at least 4GB available

# Check ERPNext installation
bench --version
```

### ✅ Network and Security Checklist

- [ ] Firewall configured to allow required ports (80, 443, 3306/5432)
- [ ] SSL certificates obtained for production domains
- [ ] Backup procedures established
- [ ] Monitoring tools configured
- [ ] Log rotation configured

## Installation Procedures

### Step 1: Download the AMB_W_SPC Application

Navigate to your bench directory and get the application:

```bash
# Change to bench directory
cd /path/to/your/bench

# Get the AMB_W_SPC application from GitHub
bench get-app https://github.com/rogerboy38/amb_w_spc.git

# Verify the app was downloaded
ls apps/  # Should show 'amb_w_spc' directory
```

### Step 2: Install the Application

Install the application on your site:

```bash
# Install the app on your site
bench --site your-site-name.local install-app amb_w_spc

# The installation will automatically:
# - Install all DocTypes
# - Set up roles and permissions
# - Configure workflows
# - Install fixtures and initial data
# - Set up validation rules
# - Configure automation scripts
```

### Step 3: Verify Installation Success

Check that the installation completed successfully:

```bash
# Check installation log
tail -f logs/bench.log

# Verify app is installed
bench --site your-site-name.local list-apps

# Check for any installation errors
bench --site your-site-name.local console
```

In the console, run:
```python
# Check if SPC DocTypes are available
frappe.get_doc("DocType", "SPC Data Point")
frappe.get_doc("DocType", "SPC Alert")
frappe.get_doc("DocType", "Process Capability")

# Exit console
exit()
```

## Post-Installation Configuration

### Step 1: Initial System Configuration

Access your ERPNext site and complete the initial setup:

```bash
# Start the development server (for testing)
bench start

# OR for production, restart services
sudo supervisorctl restart all
```

### Step 2: Site Configuration

Navigate to your site and complete the setup wizard:

1. Access your site: `http://your-site-name.local:8000`
2. Log in with Administrator credentials
3. Complete the ERPNext setup wizard if not already done

### Step 3: Enable SPC System Features

Enable the required features in System Settings:

1. Go to **Setup** → **System Settings**
2. Enable the following:
   - Enable Multi-Plant Operations
   - Enable Electronic Signatures
   - Enable Audit Trail
   - Enable API Access

## Module Activation Sequence

The SPC system modules must be activated in the correct sequence to ensure proper dependency resolution:

### Phase 1: Core DocTypes (Automatically installed)
1. **Plant Configuration** - Root level configuration
2. **Workstation** - Equipment and location setup
3. **SPC Parameter Master** - Parameter definitions
4. **SPC Specification** - Limits and specifications

### Phase 2: Data Collection (Automatically installed)
1. **SPC Data Point** - Individual measurements
2. **SPC Alert** - Exception handling
3. **SPC Control Chart** - Statistical visualization

### Phase 3: Quality Management (Automatically installed)
1. **Process Capability** - Statistical analysis
2. **SPC Report** - Reporting framework
3. **Corrective Action** - CAPA management

### Phase 4: Compliance (Automatically installed)
1. **Deviation** - Non-conformance management
2. **Electronic Signature** - Approval processes
3. **SPC Audit Trail** - Compliance tracking

### Phase 5: Integration (Automatically installed)
1. **Bot User Configuration** - Automation setup
2. **PLC Integration** - Hardware connectivity

## Database Setup and Configuration

### Database Optimization

Configure your database for optimal SPC system performance:

#### MariaDB Configuration

Edit `/etc/mysql/mariadb.conf.d/50-server.cnf`:

```ini
[mysqld]
# SPC System optimizations
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT

# Query optimization
query_cache_size = 128M
query_cache_limit = 2M
query_cache_type = 1

# Connection settings
max_connections = 200
wait_timeout = 3600
interactive_timeout = 3600

# Character set
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

#### PostgreSQL Configuration

Edit `postgresql.conf`:

```ini
# Memory settings
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 4MB
maintenance_work_mem = 64MB

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Connection settings
max_connections = 200
```

### Database Schema Verification

After installation, verify the database schema:

```sql
-- Check SPC tables exist
SHOW TABLES LIKE 'tabSPC%';

-- Verify key tables
DESCRIBE `tabSPC Data Point`;
DESCRIBE `tabSPC Alert`;
DESCRIBE `tabProcess Capability`;

-- Check indexes
SHOW INDEX FROM `tabSPC Data Point`;
```

### Database Maintenance

Set up automated database maintenance:

```bash
# Create maintenance script
cat > /home/erpnext/db_maintenance.sh << 'EOF'
#!/bin/bash
# SPC System Database Maintenance

# Optimize tables
mysqlcheck -u erpnext_user -p --optimize erpnext_db

# Update table statistics
mysqlcheck -u erpnext_user -p --analyze erpnext_db

# Check for corruption
mysqlcheck -u erpnext_user -p --check erpnext_db
EOF

chmod +x /home/erpnext/db_maintenance.sh

# Add to cron for weekly execution
echo "0 2 * * 0 /home/erpnext/db_maintenance.sh" | crontab -
```

## User Creation and Role Assignment

### 1. Understanding SPC System Roles

The SPC system implements a six-tier role structure:

#### Quality User Role
- **Purpose**: Quality engineers and managers
- **Permissions**: Full system access with read/write/create privileges
- **Special Capabilities**: Electronic signature authority, workflow approval, comprehensive reporting

#### Inspector User Role
- **Purpose**: Quality inspectors and technicians
- **Permissions**: SPC Data Point creation/editing, alert acknowledgment
- **Limitations**: Owner-based access restrictions

#### Manufacturing User Role
- **Purpose**: Production operators and supervisors
- **Permissions**: Workstation data entry, alert notifications, limited SPC access
- **Scope**: Production-focused reporting with restricted access

#### Bot User Roles (3 Types)

**Warehouse Bot User:**
- Rate limit: 60 requests/minute
- Access: Warehouse parameter data only
- Use case: Automated warehouse systems

**Workstation Bot User:**
- Rate limit: 120 requests/minute
- Access: PLC integration for manufacturing equipment
- Use case: High-volume production data

**Weight Bot User:**
- Rate limit: 30 requests/minute
- Access: Weight parameter filtering
- Use case: Automated weighing systems

### 2. Creating Users

#### Creating Human Users

1. Go to **Setup** → **Users and Permissions** → **User**
2. Click **New** to create a user
3. Fill in the required information:
   - Email (used as username)
   - First Name and Last Name
   - Phone Number
   - Language preference

#### Example Quality Manager User Creation:

```python
# Via console or script
frappe.get_doc({
    "doctype": "User",
    "email": "quality.manager@company.com",
    "first_name": "Quality",
    "last_name": "Manager",
    "enabled": 1,
    "user_type": "System User",
    "roles": [
        {"role": "Quality User"},
        {"role": "Employee"}
    ]
}).insert()
```

#### Creating Bot Users

Bot users require special configuration for API access:

```python
# Create Workstation Bot User
bot_user = frappe.get_doc({
    "doctype": "User",
    "email": "workstation.bot@company.com",
    "first_name": "Workstation",
    "last_name": "Bot",
    "enabled": 1,
    "user_type": "System User",
    "roles": [
        {"role": "Workstation Bot User"}
    ]
})
bot_user.insert()

# Generate API key
api_key = frappe.generate_hash(length=15)
api_secret = frappe.generate_hash(length=15)

# Save API credentials
frappe.get_doc({
    "doctype": "API Key",
    "user": "workstation.bot@company.com",
    "api_key": api_key,
    "api_secret": api_secret
}).insert()
```

### 3. Plant-Based User Permissions

Configure plant-based access restrictions:

```python
# Create User Permission for plant restriction
frappe.get_doc({
    "doctype": "User Permission",
    "user": "inspector@plant1.com",
    "allow": "Plant Configuration",
    "for_value": "Plant 1",
    "apply_to_all_doctypes": 1
}).insert()
```

### 4. Workstation Access Control

Restrict operators to specific workstations:

```python
# Workstation-specific permissions
frappe.get_doc({
    "doctype": "User Permission",
    "user": "operator@plant1.com",
    "allow": "Workstation",
    "for_value": "Packaging Line 1",
    "apply_to_all_doctypes": 1
}).insert()
```

## Initial System Configuration

### 1. Plant Configuration Setup

Create your first plant configuration:

1. Go to **SPC** → **Setup** → **Plant Configuration**
2. Click **New** and fill in:
   - Plant Name (e.g., "Main Manufacturing Plant")
   - Plant Code (e.g., "MFG01")
   - Location details
   - Time zone settings
   - Operating schedule

### 2. Workstation Setup

Configure workstations for each plant:

1. Go to **Manufacturing** → **Workstation**
2. Create workstations or verify existing ones
3. Ensure each workstation is linked to appropriate plant
4. Configure capacity and operating hours

### 3. SPC Parameter Master Setup

Define the parameters you'll be monitoring:

1. Go to **SPC** → **Setup** → **SPC Parameter Master**
2. Create parameters such as:
   - Weight
   - Temperature
   - Pressure
   - Dimension measurements
   - pH levels
   - Moisture content

Example parameter configuration:
- **Parameter Name**: Product Weight
- **Parameter Type**: Continuous
- **Unit of Measure**: kg
- **Decimal Places**: 3
- **Data Collection Method**: Manual/Automated

### 4. SPC Specification Setup

Define specification limits for each parameter:

1. Go to **SPC** → **Setup** → **SPC Specification**
2. Link to Parameter Master and Workstation
3. Set specification limits:
   - Lower Specification Limit (LSL)
   - Upper Specification Limit (USL)
   - Lower Control Limit (LCL)
   - Upper Control Limit (UCL)
   - Target value

### 5. Email Configuration

Configure email settings for alerts and notifications:

1. Go to **Setup** → **Email** → **Email Account**
2. Set up SMTP settings for outgoing mail
3. Configure notification templates in **SPC** → **Notifications**

### 6. Workflow Configuration

The system comes with pre-configured workflows, but you may need to customize:

1. **SPC Alert Workflow**
   - Review escalation timing (default: 24 hours)
   - Customize notification recipients
   - Adjust severity classifications

2. **Process Capability Workflow**
   - Review approval requirements
   - Set minimum sample sizes
   - Configure capability thresholds

3. **Corrective Action Workflow**
   - Set default due date calculations
   - Configure assignment rules
   - Review effectiveness verification requirements

4. **Deviation Workflow**
   - Review investigation timelines
   - Set team assignment rules
   - Configure CAPA requirements

### 7. Dashboard Configuration

Set up role-based dashboards:

1. **Quality Manager Dashboard**
   - Plant-wide quality metrics
   - Alert status summaries
   - Capability trending
   - Compliance reports

2. **Inspector Dashboard**
   - Daily task assignments
   - Recent alerts
   - Data entry shortcuts
   - Performance metrics

3. **Manufacturing Dashboard**
   - Production quality status
   - Real-time alerts
   - Workstation performance
   - Trend analysis

## Verification Procedures

### 1. System Health Check

Run comprehensive system verification:

```bash
# Navigate to bench directory
cd /path/to/your/bench

# Run health check
bench --site your-site-name.local execute amb_w_spc.system_integration.installation.health_check.run_health_check
```

### 2. DocType Verification

Verify all SPC DocTypes are properly installed:

```python
# In bench console
bench --site your-site-name.local console

# Check core DocTypes
spc_doctypes = [
    "Plant Configuration",
    "Workstation", 
    "SPC Parameter Master",
    "SPC Specification",
    "SPC Data Point",
    "SPC Alert",
    "SPC Control Chart",
    "Process Capability",
    "SPC Report",
    "Corrective Action",
    "Deviation",
    "Electronic Signature",
    "SPC Audit Trail",
    "Bot User Configuration"
]

for doctype in spc_doctypes:
    try:
        frappe.get_doc("DocType", doctype)
        print(f"✓ {doctype} - OK")
    except:
        print(f"✗ {doctype} - MISSING")
```

### 3. Permission Verification

Check role permissions are correctly configured:

```python
# Check role permissions
roles_to_check = [
    "Quality User",
    "Inspector User", 
    "Manufacturing User",
    "Warehouse Bot User",
    "Workstation Bot User",
    "Weight Bot User"
]

for role in roles_to_check:
    try:
        role_doc = frappe.get_doc("Role", role)
        print(f"✓ Role {role} - OK")
    except:
        print(f"✗ Role {role} - MISSING")
```

### 4. Workflow Verification

Verify workflows are active:

```python
# Check workflows
workflows = [
    "SPC Alert Workflow",
    "Process Capability Workflow", 
    "Corrective Action Workflow",
    "Deviation Workflow"
]

for workflow in workflows:
    try:
        wf = frappe.get_doc("Workflow", workflow)
        if wf.is_active:
            print(f"✓ {workflow} - ACTIVE")
        else:
            print(f"⚠ {workflow} - INACTIVE")
    except:
        print(f"✗ {workflow} - MISSING")
```

### 5. Database Schema Verification

Check database tables and indexes:

```sql
-- Verify key tables exist
SELECT COUNT(*) as spc_tables 
FROM information_schema.tables 
WHERE table_schema = 'erpnext_db' 
AND table_name LIKE 'tabSPC%';

-- Check critical indexes
SHOW INDEX FROM `tabSPC Data Point` WHERE Key_name = 'idx_timestamp';
SHOW INDEX FROM `tabSPC Alert` WHERE Key_name = 'idx_severity';
```

### 6. API Functionality Test

Test API endpoints for bot user functionality:

```bash
# Test bot user authentication
curl -X POST http://your-site.local/api/method/login \
  -H "Content-Type: application/json" \
  -d '{
    "usr": "workstation.bot@company.com",
    "pwd": "bot_password"
  }'

# Test SPC data point creation
curl -X POST http://your-site.local/api/resource/SPC%20Data%20Point \
  -H "Authorization: token api_key:api_secret" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "parameter": "Weight",
      "workstation": "Packaging Line 1", 
      "measurement_value": 100.5,
      "timestamp": "2025-01-15 10:30:00"
    }
  }'
```

### 7. End-to-End Workflow Test

Perform a complete workflow test:

1. **Create SPC Data Point**
   - Navigate to SPC → Data Collection → SPC Data Point
   - Create a new data point that violates specifications
   - Verify alert is automatically generated

2. **Test Alert Workflow**
   - Check that alert appears in SPC → Alerts
   - Acknowledge the alert
   - Verify workflow state changes

3. **Test Electronic Signatures**
   - Create a document requiring signature
   - Apply electronic signature
   - Verify audit trail is created

4. **Test Reporting**
   - Generate SPC reports
   - Verify data accuracy
   - Test export functionality

## Troubleshooting Common Issues

### Installation Issues

#### Issue: "App not found" during installation

**Symptoms:**
```
Error: App amb_w_spc not found
```

**Solution:**
```bash
# Verify app download
cd /path/to/bench
ls apps/

# If missing, re-download
bench get-app https://github.com/rogerboy38/amb_w_spc.git

# Clear cache and retry
bench clear-cache
bench --site your-site.local install-app amb_w_spc
```

#### Issue: Database connection errors

**Symptoms:**
```
Error: (2003, "Can't connect to MySQL server")
```

**Solution:**
```bash
# Check database service
sudo systemctl status mysql  # or mariadb

# Test connection
mysql -u erpnext_user -p -e "SELECT 1"

# Check site config
cat sites/your-site.local/site_config.json

# Verify database credentials
```

#### Issue: Permission denied during installation

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Fix file permissions
cd /path/to/bench
sudo chown -R erpnext:erpnext .
chmod -R 755 .

# Ensure correct user
whoami  # Should return 'erpnext'
```

### Runtime Issues

#### Issue: SPC Data Points not creating alerts

**Diagnosis:**
```python
# Check in console
bench --site your-site.local console

# Verify specifications exist
frappe.get_all("SPC Specification", fields=["name", "parameter", "upper_limit"])

# Check alert generation function
from amb_w_spc.system_integration.scripts.automation_scripts import generate_spc_alert
```

**Solution:**
- Verify SPC Specifications are properly configured
- Check specification limits are set correctly
- Ensure automation scripts are enabled

#### Issue: Electronic signatures not working

**Diagnosis:**
```python
# Check electronic signature setup
frappe.get_doc("DocType", "Electronic Signature")

# Verify user has signature permissions
user = frappe.get_doc("User", "user@company.com")
print(user.roles)
```

**Solution:**
- Verify user has appropriate role permissions
- Check document workflow state allows signatures
- Ensure signature meaning is correctly configured

#### Issue: Bot user API authentication fails

**Diagnosis:**
```bash
# Check API key configuration
curl -X GET http://your-site.local/api/resource/User/workstation.bot@company.com \
  -H "Authorization: token api_key:api_secret"
```

**Solution:**
- Regenerate API keys
- Verify bot user has correct roles
- Check rate limiting configuration

### Performance Issues

#### Issue: Slow SPC report generation

**Diagnosis:**
```sql
-- Check data volume
SELECT COUNT(*) FROM `tabSPC Data Point`;

-- Check slow queries
SHOW PROCESSLIST;
```

**Solution:**
```sql
-- Add indexes for performance
ALTER TABLE `tabSPC Data Point` ADD INDEX idx_parameter_timestamp (parameter, timestamp);
ALTER TABLE `tabSPC Alert` ADD INDEX idx_plant_created (plant, creation);

-- Optimize tables
OPTIMIZE TABLE `tabSPC Data Point`;
```

#### Issue: High memory usage

**Diagnosis:**
```bash
# Check memory usage
free -h
ps aux | grep python

# Check Redis memory
redis-cli info memory
```

**Solution:**
```bash
# Tune Redis configuration
echo "maxmemory 1gb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf

# Restart services
sudo systemctl restart redis
sudo supervisorctl restart all
```

### Data Issues

#### Issue: Missing historical data after migration

**Diagnosis:**
```sql
-- Check data ranges
SELECT MIN(creation), MAX(creation), COUNT(*) 
FROM `tabSPC Data Point`;

-- Verify plant assignments
SELECT plant, COUNT(*) 
FROM `tabSPC Data Point` 
GROUP BY plant;
```

**Solution:**
- Review migration scripts
- Check data import logs
- Verify User Permissions for plant access

### Integration Issues

#### Issue: PLC integration not working

**Diagnosis:**
```python
# Test PLC connection
from amb_w_spc.system_integration.integrations.plc_integration import test_plc_connection
test_plc_connection("192.168.1.100")
```

**Solution:**
- Verify network connectivity to PLC
- Check firewall rules
- Validate PLC configuration parameters
- Test with manual data points first

## Maintenance and Updates

### Regular Maintenance Tasks

#### Daily Tasks
```bash
#!/bin/bash
# Daily maintenance script

# Clear temporary files
bench --site your-site.local clear-cache

# Process scheduled jobs
bench --site your-site.local trigger-scheduler-event all

# Check system health
bench --site your-site.local execute amb_w_spc.system_integration.installation.health_check.daily_check

# Archive old logs
find logs/ -name "*.log" -mtime +30 -delete
```

#### Weekly Tasks
```bash
#!/bin/bash
# Weekly maintenance script

# Database optimization
bench --site your-site.local execute frappe.utils.bench_manager.optimize_tables

# Update statistics
bench --site your-site.local execute amb_w_spc.system_integration.scripts.maintenance.update_statistics

# Generate maintenance report
bench --site your-site.local execute amb_w_spc.system_integration.reports.system_health_report
```

#### Monthly Tasks
```bash
#!/bin/bash
# Monthly maintenance script

# Full backup
bench --site your-site.local backup --with-files

# Archive old data
bench --site your-site.local execute amb_w_spc.system_integration.scripts.data_archival.archive_old_data

# Security audit
bench --site your-site.local execute amb_w_spc.system_integration.security.audit_users_and_permissions
```

### Update Procedures

#### Updating the AMB_W_SPC Application

```bash
# Navigate to bench directory
cd /path/to/bench

# Pull latest changes
bench get-app amb_w_spc --branch main

# Update the application
bench --site your-site.local migrate

# Clear cache
bench --site your-site.local clear-cache

# Restart services
bench restart
```

#### Version Compatibility Check

Before updating, verify compatibility:

```python
# Check current versions
bench --site your-site.local console

import frappe
print(f"ERPNext Version: {frappe.get_attr('erpnext.__version__')}")
print(f"Frappe Version: {frappe.get_attr('frappe.__version__')}")

# Check AMB_W_SPC version
from amb_w_spc import __version__
print(f"AMB_W_SPC Version: {__version__}")
```

### Backup and Recovery

#### Automated Backup Setup

```bash
# Create backup script
cat > /home/erpnext/backup_spc.sh << 'EOF'
#!/bin/bash
SITE_NAME="your-site.local"
BACKUP_DIR="/backup/erpnext"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
bench --site $SITE_NAME backup --with-files

# Copy to backup directory
cp sites/$SITE_NAME/private/backups/*.sql.gz $BACKUP_DIR/
cp sites/$SITE_NAME/private/backups/*-files.tar $BACKUP_DIR/

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*-files.tar" -mtime +30 -delete

# Log backup completion
echo "$(date): Backup completed successfully" >> /var/log/erpnext_backup.log
EOF

chmod +x /home/erpnext/backup_spc.sh

# Schedule daily backups
echo "0 2 * * * /home/erpnext/backup_spc.sh" | crontab -
```

#### Recovery Procedures

```bash
# To restore from backup
bench --site your-site.local --force restore /path/to/backup.sql.gz

# Restore files if needed
cd sites/your-site.local/
tar -xf /path/to/backup-files.tar

# Clear cache after restore
bench --site your-site.local clear-cache
bench restart
```

### Monitoring and Alerting

Set up monitoring for production systems:

#### System Health Monitoring

```bash
# Create monitoring script
cat > /home/erpnext/monitor_spc.sh << 'EOF'
#!/bin/bash
SITE_NAME="your-site.local"
LOG_FILE="/var/log/spc_monitoring.log"

# Check site status
if ! bench --site $SITE_NAME execute frappe.ping; then
    echo "$(date): Site $SITE_NAME is down" >> $LOG_FILE
    # Send alert email
    echo "SPC System Down" | mail -s "URGENT: SPC System Alert" admin@company.com
fi

# Check database connectivity
if ! bench --site $SITE_NAME execute "frappe.db.sql('SELECT 1')"; then
    echo "$(date): Database connectivity issue" >> $LOG_FILE
fi

# Check critical services
for service in redis nginx mysql; do
    if ! systemctl is-active --quiet $service; then
        echo "$(date): Service $service is not running" >> $LOG_FILE
    fi
done
EOF

chmod +x /home/erpnext/monitor_spc.sh

# Run every 5 minutes
echo "*/5 * * * * /home/erpnext/monitor_spc.sh" | crontab -
```

### Security Maintenance

#### User Audit

```python
# Monthly user audit script
def audit_users():
    users = frappe.get_all("User", 
        filters={"enabled": 1}, 
        fields=["name", "last_login", "creation"]
    )
    
    # Check for inactive users (no login in 90 days)
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=90)
    
    inactive_users = []
    for user in users:
        if user.last_login and user.last_login < cutoff_date:
            inactive_users.append(user.name)
    
    # Report inactive users
    if inactive_users:
        print(f"Inactive users: {inactive_users}")
    
    return inactive_users

# Run audit
bench --site your-site.local execute path.to.audit_users
```

#### Permission Review

```python
# Review bot user permissions
def review_bot_permissions():
    bot_users = frappe.get_all("User", 
        filters={"email": ["like", "%bot%"]}, 
        fields=["name", "enabled", "last_login"]
    )
    
    for bot in bot_users:
        # Check API usage
        api_usage = frappe.db.count("API Access Log", 
            filters={"user": bot.name, "creation": [">", "2025-01-01"]}
        )
        print(f"Bot {bot.name}: {api_usage} API calls this month")

bench --site your-site.local execute path.to.review_bot_permissions
```

---

This installation guide provides comprehensive procedures for deploying the AMB_W_SPC system. For additional support or customization requirements, consult the system integration documentation or contact your system administrator.

**Document Version:** 1.0  
**Last Updated:** January 2025  
**Compatibility:** ERPNext 14.0+, Frappe Framework 14.0+
