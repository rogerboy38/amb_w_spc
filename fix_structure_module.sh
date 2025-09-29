#!/bin/bash
# Fix AMB_W_SPC Frappe App Structure
# This script fixes the structural issues causing "orphaned DocTypes" errors
set -e  # Exit on any error
# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}
# Check if we're in the frappe-bench directory
if [ ! -d "apps" ] || [ ! -d "sites" ]; then
    print_error "This script must be run from the frappe-bench directory"
    print_error "Please navigate to ~/frappe-bench and run the script again"
    exit 1
fi
# Check if amb_w_spc app exists
APP_PATH="apps/amb_w_spc"
if [ ! -d "$APP_PATH" ]; then
    print_error "amb_w_spc app not found at $APP_PATH"
    exit 1
fi
print_status "Starting amb_w_spc structural fix..."
# Create backup
BACKUP_DIR="amb_w_spc_backup_$(date +%Y%m%d_%H%M%S)"
print_status "Creating backup at $BACKUP_DIR..."
cp -r "$APP_PATH" "$BACKUP_DIR"
print_success "Backup created successfully"
# Navigate to the app directory
cd "$APP_PATH"
print_status "Current directory: $(pwd)"
# Step 1: Fix modules.txt
print_status "Updating modules.txt file..."
cat > modules.txt << 'EOF'
Core SPC
Manufacturing Operations
FDA Compliance
Plant Equipment
SPC Quality Management
System Integration
Batch Management
EOF
print_success "modules.txt updated with all required modules"
# Step 2: Create proper module directory structure
print_status "Creating module directory structure..."
# Create module directories (convert module names to directory names)
declare -A MODULE_DIRS=(
    ["Core SPC"]="core_spc"
    ["Manufacturing Operations"]="manufacturing_operations"
    ["FDA Compliance"]="fda_compliance"
    ["Plant Equipment"]="plant_equipment"
    ["SPC Quality Management"]="spc_quality_management"
    ["System Integration"]="system_integration"
    ["Batch Management"]="batch_management"
)
# Create the main app module directory if it doesn't exist
APP_MODULE_PATH="amb_w_spc"
mkdir -p "$APP_MODULE_PATH"
# Create each module directory with required subdirectories
for module_name in "${!MODULE_DIRS[@]}"; do
    module_dir="${MODULE_DIRS[$module_name]}"
    print_status "Creating module: $module_name -> $module_dir"
    
    mkdir -p "$APP_MODULE_PATH/$module_dir"
    mkdir -p "$APP_MODULE_PATH/$module_dir/doctype"
    
    # Create __init__.py files
    touch "$APP_MODULE_PATH/$module_dir/__init__.py"
    touch "$APP_MODULE_PATH/$module_dir/doctype/__init__.py"
done
print_success "Module directory structure created"
# Step 3: Move existing DocTypes to appropriate modules
print_status "Organizing DocTypes into proper modules..."
# Check if there's a flat doctype directory
FLAT_DOCTYPE_PATH="$APP_MODULE_PATH/doctype"
if [ -d "$FLAT_DOCTYPE_PATH" ]; then
    print_status "Found flat doctype directory, organizing DocTypes..."
    
    # Define DocType to module mapping
    declare -A DOCTYPE_MODULE_MAP=(
        # Core SPC DocTypes
        ["spc_control_chart"]="core_spc"
        ["spc_control_chart_rule"]="core_spc"
        ["spc_point_violation_detail"]="core_spc"
        ["spc_rule_configuration"]="core_spc"
        ["statistical_process_control"]="core_spc"
        ["control_chart_point"]="core_spc"
        ["spc_violation_log"]="core_spc"
        
        # Manufacturing Operations DocTypes
        ["manufacturing_order"]="manufacturing_operations"
        ["production_batch"]="manufacturing_operations"
        ["quality_inspection"]="manufacturing_operations"
        ["equipment_maintenance"]="manufacturing_operations"
        
        # FDA Compliance DocTypes
        ["fda_validation"]="fda_compliance"
        ["compliance_report"]="fda_compliance"
        ["audit_trail"]="fda_compliance"
        
        # Plant Equipment DocTypes
        ["equipment_master"]="plant_equipment"
        ["equipment_calibration"]="plant_equipment"
        ["maintenance_schedule"]="plant_equipment"
        
        # SPC Quality Management DocTypes
        ["quality_control_plan"]="spc_quality_management"
        ["inspection_result"]="spc_quality_management"
        ["quality_metrics"]="spc_quality_management"
        
        # System Integration DocTypes
        ["system_interface"]="system_integration"
        ["data_sync_log"]="system_integration"
        
        # Batch Management DocTypes
        ["batch_record"]="batch_management"
        ["batch_genealogy"]="batch_management"
    )
    
    # Move DocTypes to their proper modules
    for doctype_dir in "$FLAT_DOCTYPE_PATH"/*; do
        if [ -d "$doctype_dir" ]; then
            doctype_name=$(basename "$doctype_dir")
            
            # Find the appropriate module for this DocType
            target_module=""
            for dt_name in "${!DOCTYPE_MODULE_MAP[@]}"; do
                if [[ "$doctype_name" == *"$dt_name"* ]] || [[ "$dt_name" == *"$doctype_name"* ]]; then
                    target_module="${DOCTYPE_MODULE_MAP[$dt_name]}"
                    break
                fi
            done
            
            # If no specific mapping found, try to determine by name patterns
            if [ -z "$target_module" ]; then
                if [[ "$doctype_name" == *"spc"* ]] || [[ "$doctype_name" == *"control"* ]] || [[ "$doctype_name" == *"chart"* ]]; then
                    target_module="core_spc"
                elif [[ "$doctype_name" == *"manufacturing"* ]] || [[ "$doctype_name" == *"production"* ]]; then
                    target_module="manufacturing_operations"
                elif [[ "$doctype_name" == *"fda"* ]] || [[ "$doctype_name" == *"compliance"* ]] || [[ "$doctype_name" == *"audit"* ]]; then
                    target_module="fda_compliance"
                elif [[ "$doctype_name" == *"equipment"* ]] || [[ "$doctype_name" == *"maintenance"* ]]; then
                    target_module="plant_equipment"
                elif [[ "$doctype_name" == *"quality"* ]] || [[ "$doctype_name" == *"inspection"* ]]; then
                    target_module="spc_quality_management"
                elif [[ "$doctype_name" == *"batch"* ]]; then
                    target_module="batch_management"
                else
                    target_module="core_spc"  # Default to core_spc
                fi
            fi
            
            # Move the DocType directory
            target_path="$APP_MODULE_PATH/$target_module/doctype/"
            print_status "Moving $doctype_name to $target_module module"
            mv "$doctype_dir" "$target_path/"
        fi
    done
    
    # Remove the empty flat doctype directory
    rmdir "$FLAT_DOCTYPE_PATH" 2>/dev/null || print_warning "Could not remove flat doctype directory (not empty or doesn't exist)"
    
    print_success "DocTypes reorganized into proper modules"
else
    print_warning "No flat doctype directory found - DocTypes may already be organized"
fi
# Step 4: Ensure proper __init__.py files exist
print_status "Ensuring all __init__.py files exist..."
find "$APP_MODULE_PATH" -type d -exec touch {}/__init__.py \; 2>/dev/null || true
# Step 5: Update any hooks.py file if it exists
HOOKS_FILE="hooks.py"
if [ -f "$HOOKS_FILE" ]; then
    print_status "Updating hooks.py if necessary..."
    
    # Backup hooks.py
    cp "$HOOKS_FILE" "hooks.py.backup"
    
    # Update app_include_js and app_include_css paths if they reference the old structure
    sed -i 's|amb_w_spc/doctype/|amb_w_spc/core_spc/doctype/|g' "$HOOKS_FILE" 2>/dev/null || true
    
    print_success "hooks.py updated"
fi
# Step 6: Create or update app.py file to ensure proper app configuration
print_status "Ensuring app configuration is correct..."
cat > app.py << 'EOF'
from __future__ import unicode_literals
app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB"
app_description = "Statistical Process Control Application"
app_icon = "fa fa-line-chart"
app_color = "blue"
app_email = "admin@amb.com"
app_license = "MIT"
# Includes in <head>
# ------------------
# include js, css files in header of desk.html
# app_include_css = "/assets/amb_w_spc/css/amb_w_spc.css"
# app_include_js = "/assets/amb_w_spc/js/amb_w_spc.js"
# include js, css files in header of web template
# web_include_css = "/assets/amb_w_spc/css/amb_w_spc.css"
# web_include_js = "/assets/amb_w_spc/js/amb_w_spc.js"
# include js in page
# page_js = {"page" : "public/js/file.js"}
# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}
# Home Pages
# ----------
# application home page (will override Website Settings)
# home_page = "login"
# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }
# Website user home page (by function)
# get_website_user_home_page = "amb_w_spc.utils.get_home_page"
# Generators
# ----------
# automatically create page for each record of this doctype
# website_generators = ["Web Page"]
# Installation
# ------------
# before_install = "amb_w_spc.install.before_install"
# after_install = "amb_w_spc.install.after_install"
# Desk Notifications
# -------------------
# See frappe.core.notifications.get_notification_config
# notification_config = "amb_w_spc.notifications.get_notification_config"
# Permissions
# -----------
# Permissions evaluated in scripted ways
# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }
# Document Events
# ---------------
# Hook on document methods and events
# doc_events = {
#	"*": {
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}
# }
# Scheduled Tasks
# ---------------
# scheduler_events = {
#	"all": [
#		"amb_w_spc.tasks.all"
#	],
#	"daily": [
#		"amb_w_spc.tasks.daily"
#	],
#	"hourly": [
#		"amb_w_spc.tasks.hourly"
#	],
#	"weekly": [
#		"amb_w_spc.tasks.weekly"
#	]
#	"monthly": [
#		"amb_w_spc.tasks.monthly"
#	]
# }
# Testing
# -------
# before_tests = "amb_w_spc.install.before_tests"
# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "amb_w_spc.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "amb_w_spc.task.get_dashboard_data"
# }
EOF
print_success "App configuration file created/updated"
# Step 7: Return to frappe-bench directory
cd ../..
print_success "Structural fix completed!"
# Step 8: Display next steps
print_status "Next steps to complete the fix:"
echo ""
print_warning "IMPORTANT: Before running these commands, make sure your Frappe site is stopped to avoid conflicts"
echo ""
echo "1. Clear bench cache:"
echo "   bench clear-cache"
echo ""
echo "2. Reinstall the app (this will read the new structure):"
echo "   bench --site [your-site-name] uninstall-app amb_w_spc"
echo "   bench --site [your-site-name] install-app amb_w_spc"
echo ""
echo "3. Run migrate to sync the database:"
echo "   bench --site [your-site-name] migrate"
echo ""
echo "4. If you still get orphaned DocTypes, run:"
echo "   bench --site [your-site-name] migrate --skip-failing"
echo ""
echo "Replace [your-site-name] with your actual site name (e.g., sysmayal.v.frappe.cloud)"
echo ""
print_success "Script execution completed successfully!"
print_success "Backup created at: $BACKUP_DIR"
# Display summary
echo ""
echo "==============================================="
print_success "SUMMARY OF CHANGES MADE:"
echo "==============================================="
echo "✓ Updated modules.txt with all required modules"
echo "✓ Created proper module directory structure:"
echo "  - core_spc/"
echo "  - manufacturing_operations/"
echo "  - fda_compliance/"
echo "  - plant_equipment/"
echo "  - spc_quality_management/"
echo "  - system_integration/"
echo "  - batch_management/"
echo "✓ Moved DocTypes from flat structure to proper module directories"
echo "✓ Created all necessary __init__.py files"
echo "✓ Updated/created app configuration files"
echo "✓ Created backup of original structure"
echo ""
print_warning "Remember to run the commands above to complete the installation!"
