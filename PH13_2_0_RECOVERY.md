# PH13.2.0 Recovery Script
# Run this on your Frappe server via SSH

## Phase 1: Kill Loops and Clear Locks

```bash
cd ~/frappe-bench

# 1. Kill stuck processes
pkill -f "bench" || true
pkill -f "node" || true
sleep 3

# 2. Verify no active processes
ps aux | grep -E "bench install-app|bench --site" | grep -v grep || true

# 3. Remove stale locks
rm -f sites/v2.sysmayal.cloud/locks/install_app.lock
rm -f sites/v2.sysmayal.cloud/locks/*.lock

# 4. Clear Python cache
cd apps/amb_w_spc
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
cd ~/frappe-bench

# 5. Clear Frappe cache
bench --site v2.sysmayal.cloud clear-cache
```

## Phase 2: Fix Nested Structure

```bash
cd ~/frappe-bench/apps/amb_w_spc

# Check current structure
echo "=== Current structure ==="
pwd
ls -la
ls -la amb_w_spc/ 2>/dev/null || echo "No nested amb_w_spc"
ls -la amb_w_spc/amb_w_spc/ 2>/dev/null || echo "No triple nested"

# Fix triple nesting if present
if [ -d "amb_w_spc/amb_w_spc" ]; then
    echo "Fixing triple nesting..."
    cp -r amb_w_spc/amb_w_spc/* amb_w_spc/
    rm -rf amb_w_spc/amb_w_spc
    echo "Fixed nesting"
fi

# Verify fix
echo "=== After fix ==="
ls -la amb_w_spc/
```

## Phase 3: Pull Latest Code

```bash
cd ~/frappe-bench/apps/amb_w_spc
git pull origin master
```

## Phase 4: Safe DocType Recovery

```bash
cd ~/frappe-bench
bench --site v2.sysmayal.cloud console
```

In the console, run:

```python
import frappe

print("=" * 60)
print("PH13.2.0 - SAFE DOCUMENT TYPE RECOVERY")
print("=" * 60)

# 1. Check current state
apps = frappe.get_installed_apps()
print("Installed apps:", apps)

sensor_skill_exists = frappe.db.exists("DocType", "Sensor Skill")
weight_event_exists = frappe.db.exists("DocType", "Weight Event")
print("Sensor Skill exists:", sensor_skill_exists)
print("Weight Event exists:", weight_event_exists)

# 2. Commit any pending transaction
frappe.db.commit()
print("Committed any pending transactions.")

print("\nFinal state:")
print("Sensor Skill exists:", frappe.db.exists("DocType", "Sensor Skill"))
print("Weight Event exists:", frappe.db.exists("DocType", "Weight Event"))
print("=" * 60)
```

Type `exit()` to leave console.

## Phase 5: Clean Reinstall (Single Attempt)

```bash
cd ~/frappe-bench

# Ensure lock is clear
rm -f sites/v2.sysmayal.cloud/locks/install_app.lock

# Uninstall app
bench --site v2.sysmayal.cloud uninstall-app amb_w_spc --force || true
sleep 2

# Install app
bench --site v2.sysmayal.cloud install-app amb_w_spc --force
```

**If this fails: STOP and report. Do NOT retry.**

## Phase 6: Create Sensor Skill Records

```bash
cd ~/frappe-bench
bench --site v2.sysmayal.cloud execute amb_w_spc.patches.v15.create_sensor_skill_records.execute
```

## Phase 7: Final Verification

```bash
cd ~/frappe-bench
bench --site v2.sysmayal.cloud console
```

In the console:

```python
import frappe

print("=" * 60)
print("PH13.2.0 FINAL VERIFICATION")
print("=" * 60)

checks = [
    ("amb_w_spc installed", "amb_w_spc" in frappe.get_installed_apps()),
    ("Weight Event DocType", frappe.db.exists("DocType", "Weight Event")),
    ("Sensor Skill DocType", frappe.db.exists("DocType", "Sensor Skill")),
    ("scale_plant record", frappe.db.exists("Sensor Skill", "scale_plant")),
    ("scale_lab record", frappe.db.exists("Sensor Skill", "scale_lab")),
]

for name, result in checks:
    print(f"  {'OK' if result else 'FAIL'} {name}: {result}")

print("=" * 60)
```

## Expected Results

All checks should show OK:
- amb_w_spc installed
- Weight Event DocType
- Sensor Skill DocType
- scale_plant record
- scale_lab record

If any FAIL, report the output for diagnosis.
