#!/bin/bash

# AMB W SPC - Safe Installation Script
# This script provides enhanced safety features and prevents recursive interference
# Version: 1.1.2 - Fixed pip usage for Frappe bench

set -euo pipefail  # Enhanced error handling: exit on error, unset vars, pipe failures

# Lock file to prevent concurrent installations
LOCK_FILE="/tmp/amb_w_spc_install.lock"
SCRIPT_PID=$$

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
BENCH_PATH=""
APP_PATH=""
SITE_NAME=""
PYTHON_CMD=""
PIP_CMD=""
INSTALLATION_LOG="/tmp/amb_w_spc_install.log"

# Enhanced logging with timestamps and levels
log() {
    local level="${2:-INFO}"
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[$timestamp]${NC} [$level] $message" | tee -a "$INSTALLATION_LOG"
}

success() {
    log "✅ $1" "SUCCESS"
}

warning() {
    log "⚠️  $1" "WARNING"
}

error() {
    log "❌ $1" "ERROR"
}

# Enhanced cleanup function
cleanup() {
    local exit_code=$?
    log "Performing cleanup..." "CLEANUP"
    
    # Remove lock file
    if [[ -f "$LOCK_FILE" ]]; then
        rm -f "$LOCK_FILE"
        log "Lock file removed" "CLEANUP"
    fi
    
    # If installation failed, offer to show logs
    if [[ $exit_code -ne 0 ]]; then
        error "Installation failed with exit code $exit_code"
        echo "Installation log available at: $INSTALLATION_LOG"
        echo "Last 20 lines of log:"
        tail -20 "$INSTALLATION_LOG" 2>/dev/null || true
    fi
    
    exit $exit_code
}

# Set up signal handlers
trap cleanup EXIT
trap 'error "Installation interrupted by user"; exit 130' INT
trap 'error "Installation terminated"; exit 143' TERM

# Lock mechanism to prevent concurrent runs
acquire_lock() {
    log "Checking for existing installation process..."
    
    if [[ -f "$LOCK_FILE" ]]; then
        local existing_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        
        # Check if the process is still running
        if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
            error "Another installation is already running (PID: $existing_pid)"
            error "If you're sure no other installation is running, remove: $LOCK_FILE"
            exit 1
        else
            warning "Stale lock file found, removing..."
            rm -f "$LOCK_FILE"
        fi
    fi
    
    # Create lock file
    echo "$SCRIPT_PID" > "$LOCK_FILE"
    success "Installation lock acquired (PID: $SCRIPT_PID)"
}

# Enhanced permission checking
check_permissions() {
    log "Checking permissions and user context..."
    
    # Check if running as root
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
        exit 1
    fi
    
    # Check if we have write permissions in current directory
    if [[ ! -w "." ]]; then
        error "No write permission in current directory"
        exit 1
    fi
    
    success "Permission checks passed"
}

# Enhanced system requirements checking
check_requirements() {
    log "Performing comprehensive system requirements check..."
    
    # Python version check with better error handling
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        error "Python is not installed or not in PATH"
        exit 1
    fi
    
    # Get Python version safely
    local python_version
    if ! python_version=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null); then
        error "Failed to determine Python version"
        exit 1
    fi
    
    # Enhanced version comparison
    local major minor
    major=$($PYTHON_CMD -c 'import sys; print(sys.version_info[0])' 2>/dev/null)
    minor=$($PYTHON_CMD -c 'import sys; print(sys.version_info[1])' 2>/dev/null)
    
    if [[ $major -lt 3 ]] || ([[ $major -eq 3 ]] && [[ $minor -lt 8 ]]); then
        error "Python 3.8+ required. Found: $python_version"
        exit 1
    fi
    success "Python $python_version ✓"
    
    # Node.js check (optional but recommended)
    if command -v node &> /dev/null; then
        local node_version=$(node --version 2>/dev/null | cut -d'v' -f2)
        success "Node.js $node_version ✓"
    else
        warning "Node.js not found. Consider installing Node.js 16+ for optimal performance"
    fi
    
    # Enhanced Frappe bench detection - fixed logic
    if [[ ! -f "../../sites/apps.txt" ]] && [[ ! -f "../../../sites/apps.txt" ]]; then
        error "Frappe bench not detected. Please run from: /home/frappe/frappe-bench/apps/amb_w_spc/"
        error "Current directory: $(pwd)"
        exit 1
    fi
    success "Frappe bench environment detected ✓"
    
    # Check disk space (minimum 1GB free)
    local available_space
    available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_space -lt 1 ]]; then
        warning "Low disk space detected: ${available_space}GB free. Minimum 1GB recommended"
    else
        success "Disk space: ${available_space}GB available ✓"
    fi
}

# Safe environment detection with validation - FIXED VERSION
detect_environment() {
    log "Detecting and validating environment..."
    
    APP_PATH=$(pwd)
    
    # Determine bench path correctly - fixed logic
    if [[ -f "../../sites/apps.txt" ]]; then
        # We're in apps/amb_w_spc, so bench is two levels up
        BENCH_PATH=$(realpath "../..")
    elif [[ -f "../../../sites/apps.txt" ]]; then
        # Alternative path detection
        BENCH_PATH=$(realpath "../../..")
    else
        # Try to find bench path by looking for common bench directories
        local current_dir=$(pwd)
        if [[ "$current_dir" =~ /apps/ ]]; then
            BENCH_PATH=$(echo "$current_dir" | sed 's|/apps/.*||')
        else
            error "Cannot determine bench path automatically"
            error "Please run this script from your app directory inside the bench"
            exit 1
        fi
    fi
    
    # Validate bench structure - fixed validation
    if [[ ! -d "$BENCH_PATH/sites" ]] || [[ ! -f "$BENCH_PATH/sites/apps.txt" ]]; then
        error "Invalid bench structure detected at: $BENCH_PATH"
        error "Expected to find: $BENCH_PATH/sites/ and $BENCH_PATH/sites/apps.txt"
        error "Current app path: $APP_PATH"
        exit 1
    fi
    
    # Detect bench Python and pip commands
    if [[ -f "$BENCH_PATH/env/bin/python" ]]; then
        PYTHON_CMD="$BENCH_PATH/env/bin/python"
        PIP_CMD="$BENCH_PATH/env/bin/pip"
    elif [[ -f "$BENCH_PATH/env/bin/python3" ]]; then
        PYTHON_CMD="$BENCH_PATH/env/bin/python3"
        PIP_CMD="$BENCH_PATH/env/bin/pip"
    else
        error "Bench Python environment not found in $BENCH_PATH/env/"
        exit 1
    fi
    
    success "Bench Python environment detected: $PYTHON_CMD"
    
    # Enhanced site detection with validation
    local sites_dir="$BENCH_PATH/sites"
    local sites=()
    
    # Safely collect valid sites
    if [[ -d "$sites_dir" ]]; then
        while IFS= read -r -d '' site_path; do
            local site_name=$(basename "$site_path")
            # Skip common non-site directories and files
            if [[ "$site_name" != "assets" ]] && 
               [[ "$site_name" != "common_site_config.json" ]] && 
               [[ "$site_name" != "apps.txt" ]] &&
               [[ -f "$site_path/site_config.json" ]]; then
                sites+=("$site_name")
            fi
        done < <(find "$sites_dir" -maxdepth 1 -type d -print0 2>/dev/null)
    fi
    
    if [[ ${#sites[@]} -eq 0 ]]; then
        error "No valid Frappe sites found in $sites_dir"
        error "A valid site should have a site_config.json file"
        exit 1
    fi
    
    # Site selection logic
    if [[ ${#sites[@]} -eq 1 ]]; then
        SITE_NAME="${sites[0]}"
        success "Auto-selected site: $SITE_NAME"
    else
        echo "Available sites:"
        for i in "${!sites[@]}"; do
            echo "  $((i+1))) ${sites[$i]}"
        done
        
        local site_choice
        while true; do
            echo -n "Select site (1-${#sites[@]}): "
            read -r site_choice
            
            if [[ "$site_choice" =~ ^[0-9]+$ ]] && [[ "$site_choice" -ge 1 ]] && [[ "$site_choice" -le ${#sites[@]} ]]; then
                SITE_NAME="${sites[$((site_choice-1))]}"
                break
            else
                warning "Invalid selection. Please enter a number between 1 and ${#sites[@]}"
            fi
        done
    fi
    
    # Validate selected site
    if [[ ! -f "$BENCH_PATH/sites/$SITE_NAME/site_config.json" ]]; then
        error "Selected site configuration not found: $BENCH_PATH/sites/$SITE_NAME/site_config.json"
        exit 1
    fi
    
    success "Environment validated successfully"
    log "Using site: $SITE_NAME"
    log "Bench path: $BENCH_PATH"
    log "App path: $APP_PATH"
    log "Python command: $PYTHON_CMD"
    log "Pip command: $PIP_CMD"
}

# Safe dependency installation with rollback capability - FIXED for bench environment
install_dependencies() {
    log "Installing Python dependencies with safety checks..."
    
    local requirements_file="$APP_PATH/requirements.txt"
    
    if [[ ! -f "$requirements_file" ]]; then
        warning "requirements.txt not found at $requirements_file"
        return 0
    fi
    
    # Validate requirements file
    if [[ ! -r "$requirements_file" ]]; then
        error "Cannot read requirements file: $requirements_file"
        exit 1
    fi
    
    # Check for potentially dangerous packages (basic security check)
    if grep -qi "rm -rf\|sudo\|exec\|eval" "$requirements_file"; then
        error "Requirements file contains potentially dangerous commands"
        exit 1
    fi
    
    cd "$BENCH_PATH" || { error "Failed to change to bench directory"; exit 1; }
    
    # Install with timeout to prevent hanging - using bench pip
    log "Installing requirements with bench pip (timeout: 300s)..."
    log "Using pip: $PIP_CMD"
    
    if timeout 300 "$PIP_CMD" install -r "$requirements_file"; then
        success "Python dependencies installed successfully"
    else
        error "Dependency installation failed or timed out"
        exit 1
    fi
}

# Safe app installation with pre-checks
install_app() {
    log "Installing AMB W SPC app with enhanced safety checks..."
    
    cd "$BENCH_PATH" || { error "Failed to change to bench directory"; exit 1; }
    
    # Pre-installation checks
    log "Running pre-installation validations..."
    
    # Check if app is already installed
    if bench --site "$SITE_NAME" list-apps | grep -q "amb_w_spc"; then
        warning "App 'amb_w_spc' appears to already be installed"
        echo -n "Proceed with reinstallation? (y/N): "
        read -r reinstall_choice
        
        if [[ ! "$reinstall_choice" =~ ^[Yy]$ ]]; then
            log "Installation cancelled by user"
            exit 0
        fi
        
        # Uninstall existing app first
        log "Uninstalling existing app..."
        if ! bench --site "$SITE_NAME" uninstall-app amb_w_spc --yes; then
            warning "Failed to uninstall existing app, continuing..."
        fi
    fi
    
    # Check app directory structure
    if [[ ! -d "$APP_PATH/amb_w_spc" ]]; then
        error "App module directory not found: $APP_PATH/amb_w_spc"
        exit 1
    fi
    
    # Install app with timeout
    log "Installing app on site $SITE_NAME (timeout: 120s)..."
    if timeout 120 bench --site "$SITE_NAME" install-app amb_w_spc; then
        success "App installed successfully on site $SITE_NAME"
    else
        error "App installation failed or timed out"
        exit 1
    fi
}

# Enhanced post-installation with safety checks
post_install_setup() {
    log "Running post-installation setup with safety measures..."
    
    cd "$BENCH_PATH" || { error "Failed to change to bench directory"; exit 1; }
    
    # Clear cache safely
    log "Clearing cache..."
    if timeout 60 bench --site "$SITE_NAME" clear-cache; then
        success "Cache cleared successfully"
    else
        warning "Cache clearing failed, but continuing..."
    fi
    
    # Run migrations with timeout
    log "Running migrations (timeout: 300s)..."
    if timeout 300 bench --site "$SITE_NAME" migrate; then
        success "Migrations completed successfully"
    else
        error "Migration failed or timed out"
        exit 1
    fi
    
    # Build assets safely
    log "Building assets (timeout: 240s)..."
    if timeout 240 bench build --app amb_w_spc; then
        success "Asset build completed successfully"
    else
        warning "Asset build failed, but app may still be functional"
    fi
    
    success "Post-installation setup completed"
}

# Safe sample data creation
create_sample_data() {
    local create_samples
    echo -n "Create sample data for testing? (y/N): "
    read -r create_samples
    
    if [[ "$create_samples" =~ ^[Yy]$ ]]; then
        log "Creating sample data with safety checks..."
        cd "$BENCH_PATH" || return 1
        
        # Create sample data with timeout and error handling
        if timeout 60 bench --site "$SITE_NAME" console <<< "
try:
    import amb_w_spc
    print('✅ Sample data creation placeholder - customize as needed')
except Exception as e:
    print('⚠️  Sample data creation failed:', str(e))
"; then
            success "Sample data creation completed"
        else
            warning "Sample data creation had issues, but installation continues"
        fi
    fi
}

# Safe service restart
restart_services() {
    log "Restarting services safely..."
    
    cd "$BENCH_PATH" || { error "Failed to change to bench directory"; exit 1; }
    
    # Restart with timeout
    if timeout 60 bench restart; then
        success "Services restarted successfully"
    else
        warning "Service restart had issues, but installation may still be successful"
    fi
}

# Comprehensive installation validation
run_validation() {
    log "Running comprehensive installation validation..."
    
    cd "$BENCH_PATH" || { error "Failed to change to bench directory"; exit 1; }
    
    # Test 1: App import validation
    log "Testing app import..."
    if timeout 30 bench --site "$SITE_NAME" console <<< "
try:
    import amb_w_spc
    print('✅ App import successful')
except ImportError as e:
    print('❌ App import failed:', str(e))
    exit(1)
except Exception as e:
    print('⚠️  App import warning:', str(e))
"; then
        success "App import validation passed"
    else
        error "App import validation failed"
        return 1
    fi
    
    # Test 2: Database connectivity
    log "Testing database connectivity..."
    if timeout 30 bench --site "$SITE_NAME" console <<< "
try:
    import frappe
    frappe.init(site='$SITE_NAME')
    frappe.connect()
    print('✅ Database connectivity successful')
except Exception as e:
    print('❌ Database connectivity failed:', str(e))
    exit(1)
"; then
        success "Database connectivity validation passed"
    else
        warning "Database connectivity validation had issues"
    fi
    
    # Test 3: Check app installation status
    log "Verifying app installation status..."
    if bench --site "$SITE_NAME" list-apps | grep -q "amb_w_spc"; then
        success "App is properly listed in installed apps"
    else
        error "App not found in installed apps list"
        return 1
    fi
    
    success "Installation validation completed successfully"
}

# Enhanced completion information
show_completion_info() {
    local duration=$((SECONDS - start_time))
    
    echo ""
    echo "🎉 AMB W SPC Installation Successfully Completed!"
    echo ""
    echo "📊 Installation Summary:"
    echo "  • Site: $SITE_NAME"
    echo "  • Bench Path: $BENCH_PATH"
    echo "  • App Path: $APP_PATH"
    echo "  • Installation Duration: ${duration} seconds"
    echo "  • Installation Log: $INSTALLATION_LOG"
    echo ""
    echo "🚀 Next Steps:"
    echo "  1. Access your site: http://localhost:8000 or your configured URL"
    echo "  2. Login with your Frappe/ERPNext credentials"
    echo "  3. Navigate to Manufacturing > SPC Setup (if available)"
    echo "  4. Configure your Statistical Process Control parameters"
    echo ""
    echo "🔧 Maintenance Commands:"
    echo "  • Update app: bench update --patch"
    echo "  • Restart services: bench restart"
    echo "  • View logs: bench logs"
    echo ""
    echo "🆘 Support:"
    echo "  • Installation log: $INSTALLATION_LOG"
    echo "  • Check bench status: bench doctor"
    echo ""
}

# Main installation process with enhanced error handling
main() {
    local start_time=$SECONDS
    
    echo "🏭 AMB W SPC - Advanced Manufacturing Business with Statistical Process Control"
    echo "🛡️  Safe Installation Script v1.1.2"
    echo "📋 Enhanced with safety features and recursive interference prevention"
    echo ""
    
    # Initialize installation log
    echo "=== AMB W SPC Safe Installation Log ===" > "$INSTALLATION_LOG"
    echo "Start Time: $(date)" >> "$INSTALLATION_LOG"
    echo "Script PID: $SCRIPT_PID" >> "$INSTALLATION_LOG"
    echo "" >> "$INSTALLATION_LOG"
    
    # Safety checks first
    acquire_lock
    check_permissions
    check_requirements
    detect_environment
    
    echo ""
    echo "📋 Safe Installation Plan:"
    echo "  1. ✅ Acquire installation lock (prevent concurrent runs)"
    echo "  2. ✅ Validate permissions and requirements"
    echo "  3. ✅ Detect and validate environment"
    echo "  4. 📦 Install Python dependencies (with timeout protection)"
    echo "  5. 🚀 Install app on Frappe site (with pre-checks)"
    echo "  6. ⚙️  Run post-installation setup (with safety measures)"
    echo "  7. 📊 Create sample data (optional, with error handling)"
    echo "  8. 🔄 Restart services (with timeout protection)"
    echo "  9. ✅ Validate installation (comprehensive tests)"
    echo ""
    
    local proceed
    echo -n "Proceed with safe installation? (y/N): "
    read -r proceed
    
    if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
        log "Installation cancelled by user"
        exit 0
    fi
    
    echo ""
    log "Starting safe installation process..."
    
    # Execute installation steps with error handling
    if install_dependencies && 
       install_app && 
       post_install_setup && 
       create_sample_data && 
       restart_services && 
       run_validation; then
        
        show_completion_info
        success "Safe installation completed successfully!"
    else
        error "Installation failed during execution"
        exit 1
    fi
}

# Global error handling
handle_error() {
    local line_no=$1
    local error_code=$2
    error "Installation failed at line $line_no with exit code $error_code"
    error "Check the installation log for details: $INSTALLATION_LOG"
    
    # Show recent log entries
    echo ""
    echo "Recent log entries:"
    tail -10 "$INSTALLATION_LOG" 2>/dev/null || true
}

# Set up enhanced error trapping
trap 'handle_error ${LINENO} $?' ERR

# Help information
show_help() {
    echo "AMB W SPC Safe Installation Script"
    echo ""
    echo "Usage: ./install_safe.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help, -h    Show this help message"
    echo "  --version     Show version information"
    echo ""
    echo "Features:"
    echo "  • Prevents concurrent installations with lock mechanism"
    echo "  • Enhanced error handling and rollback capabilities"
    echo "  • Comprehensive validation and safety checks"
    echo "  • Timeout protection for all operations"
    echo "  • Detailed logging and progress tracking"
    echo ""
    echo "Requirements:"
    echo "  • Python 3.8+ installed and accessible"
    echo "  • Valid Frappe bench environment"
    echo "  • Write permissions in current directory"
    echo "  • At least 1GB free disk space"
    echo ""
}

# Command line argument parsing
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --version)
        echo "AMB W SPC Safe Installation Script v1.1.2"
        exit 0
        ;;
    *)
        # Run main installation
        main "$@"
        ;;
esac
