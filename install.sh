#!/bin/bash

# AMB W SPC - Advanced Installation Script
# This script automates the complete installation process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Safe exit function that doesn't terminate the shell session
safe_exit() {
    local exit_code=${1:-1}
    error "Installation failed. Please check the errors above."
    echo "Returning to Frappe bench directory..."
    cd ~/frappe-bench 2>/dev/null || true
    # Use return instead of exit to avoid terminating the shell session
    return $exit_code
}

# Check if running as root
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root"
        safe_exit 1
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        safe_exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    
    # Use Python itself for version comparison (most reliable)
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
        safe_exit 1
    fi
    success "Python $PYTHON_VERSION ✓"
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        warning "Node.js not found. Please install Node.js 16+ for full functionality"
    else
        NODE_VERSION=$(node --version | cut -d'v' -f2)
        success "Node.js $NODE_VERSION ✓"
    fi
    
    # Check if we're in a Frappe bench - IMPROVED VALIDATION
    local bench_detected=false
    
    # Check multiple possible bench locations
    if [[ -f "../../apps.txt" ]]; then
        bench_detected=true
    elif [[ -f "../../../apps.txt" ]]; then
        bench_detected=true
    elif [[ -d "../../sites" ]]; then
        bench_detected=true
    elif [[ -d "../../../sites" ]]; then
        bench_detected=true
    elif [[ -f "apps.txt" ]]; then
        bench_detected=true
    fi
    
    if $bench_detected; then
        success "Frappe bench environment detected ✓"
    else
        error "This script must be run from within a Frappe bench apps directory"
        echo "Current directory: $(pwd)"
        echo "Looking for bench files (apps.txt or sites directory) in parent directories..."
        
        # Debug information
        echo ""
        echo "Debug information:"
        echo "Parent directories:"
        ls -la ../ 2>/dev/null | head -10 || echo "Cannot list parent directory"
        echo ""
        echo "Checking for common bench files:"
        [[ -f "../../apps.txt" ]] && echo "✅ Found ../../apps.txt" || echo "❌ ../../apps.txt not found"
        [[ -f "../../../apps.txt" ]] && echo "✅ Found ../../../apps.txt" || echo "❌ ../../../apps.txt not found"
        [[ -d "../../sites" ]] && echo "✅ Found ../../sites" || echo "❌ ../../sites not found"
        [[ -d "../../../sites" ]] && echo "✅ Found ../../../sites" || echo "❌ ../../../sites not found"
        
        safe_exit 1
    fi
}

# Detect Frappe bench path and site - IMPROVED DETECTION
detect_environment() {
    log "Detecting environment..."
    
    # Try to find bench path by looking for common bench files
    if [[ -f "../../apps.txt" ]]; then
        BENCH_PATH=$(cd ../.. && pwd)
    elif [[ -f "../../../apps.txt" ]]; then
        BENCH_PATH=$(cd ../../.. && pwd)
    elif [[ -d "../../sites" ]]; then
        BENCH_PATH=$(cd ../.. && pwd)
    elif [[ -d "../../../sites" ]]; then
        BENCH_PATH=$(cd ../../.. && pwd)
    elif [[ -f "apps.txt" ]]; then
        BENCH_PATH=$(pwd)
    else
        error "Could not detect Frappe bench path"
        echo "Please make sure you're in a valid Frappe bench directory structure"
        safe_exit 1
    fi
    
    APP_PATH=$(pwd)
    
    # Get available sites
    SITES=($(ls -d ${BENCH_PATH}/sites/*/ 2>/dev/null | xargs -n 1 basename | grep -v assets | grep -v common_site_config.json || true))
    
    if [[ ${#SITES[@]} -eq 0 ]]; then
        error "No Frappe sites found in $BENCH_PATH/sites/"
        echo "Available directories in sites:"
        ls -la ${BENCH_PATH}/sites/ || true
        safe_exit 1
    fi
    
    echo "Available sites:"
    for i in "${!SITES[@]}"; do
        echo "  $((i+1))) ${SITES[$i]}"
    done
    
    # Auto-select if only one site, otherwise prompt
    if [[ ${#SITES[@]} -eq 1 ]]; then
        SITE_NAME="${SITES[0]}"
        success "Auto-selected site: $SITE_NAME"
    else
        echo -n "Select site (1-${#SITES[@]}): "
        read site_choice
        if [[ "$site_choice" =~ ^[0-9]+$ ]] && [[ "$site_choice" -ge 1 ]] && [[ "$site_choice" -le ${#SITES[@]} ]]; then
            SITE_NAME="${SITES[$((site_choice-1))]}"
        else
            error "Invalid selection"
            safe_exit 1
        fi
    fi
    
    success "Using site: $SITE_NAME"
    success "Bench path: $BENCH_PATH"
    success "App path: $APP_PATH"
}

# Install Python dependencies
install_dependencies() {
    log "Installing Python dependencies..."
    
    cd "$BENCH_PATH"
    
    # Install requirements
    if [[ -f "apps/amb_w_spc/requirements.txt" ]]; then
        ./env/bin/pip install -r apps/amb_w_spc/requirements.txt
        success "Python dependencies installed"
    elif [[ -f "$APP_PATH/requirements.txt" ]]; then
        ./env/bin/pip install -r "$APP_PATH/requirements.txt"
        success "Python dependencies installed"
    else
        warning "requirements.txt not found, skipping dependency installation"
    fi
}

# Install the app
install_app() {
    log "Installing AMB W SPC app..."
    
    cd "$BENCH_PATH"
    
    # Install app on site
    if bench --site "$SITE_NAME" install-app amb_w_spc; then
        success "App installed on site $SITE_NAME"
    else
        error "Failed to install app on site $SITE_NAME"
        safe_exit 1
    fi
}

# Run post-installation setup
post_install_setup() {
    log "Running post-installation setup..."
    
    cd "$BENCH_PATH"
    
    # Clear cache
    if ! bench --site "$SITE_NAME" clear-cache; then
        warning "Cache clear had issues, but continuing..."
    fi
    
    # Run migrations
    if ! bench --site "$SITE_NAME" migrate; then
        error "Migrations failed"
        safe_exit 1
    fi
    
    # Build assets
    if ! bench build --app amb_w_spc; then
        warning "Asset build had issues, but continuing..."
    fi
    
    success "Post-installation setup completed"
}

# Create sample data (optional)
create_sample_data() {
    echo -n "Would you like to create sample data for testing? (y/N): "
    read create_samples
    
    if [[ "$create_samples" =~ ^[Yy]$ ]]; then
        log "Creating sample data..."
        cd "$BENCH_PATH"
        
        # Run sample data creation script
        if bench --site "$SITE_NAME" execute amb_w_spc.fixtures.create_sample_data; then
            success "Sample data created"
        else
            warning "Sample data creation failed, but installation is complete"
        fi
    fi
}

# Restart services
restart_services() {
    log "Restarting services..."
    
    cd "$BENCH_PATH"
    
    # Restart bench
    if bench restart; then
        success "Services restarted"
    else
        warning "Service restart had issues, but continuing..."
    fi
}

# Run validation tests
run_validation() {
    log "Running installation validation..."
    
    cd "$BENCH_PATH"
    
    # Test app import
    if bench --site "$SITE_NAME" console <<< "import amb_w_spc; print('✅ App import successful')"; then
        success "App import test passed"
    else
        error "App import failed"
        safe_exit 1
    fi
    
    # Test database
    if bench --site "$SITE_NAME" execute "frappe.get_doc('DocType', 'SPC Data Point')" &>/dev/null; then
        success "Database validation passed"
    else
        error "Database validation failed"
        safe_exit 1
    fi
    
    success "Installation validation passed"
}

# Display final information
show_completion_info() {
    echo ""
    echo "🎉 AMB W SPC Installation Complete!"
    echo ""
    echo "📊 Installation Summary:"
    echo "  • Site: $SITE_NAME"
    echo "  • Bench Path: $BENCH_PATH"
    echo "  • App Path: $APP_PATH"
    echo ""
    echo "🚀 Next Steps:"
    echo "  1. Access your site: http://localhost:8000"
    echo "  2. Login with your Frappe credentials"
    echo "  3. Navigate to Manufacturing > SPC Setup"
    echo "  4. Configure your first SPC parameters"
    echo ""
    echo "📚 Documentation:"
    echo "  • User Guide: https://github.com/your-username/amb_w_spc/wiki"
    echo "  • API Docs: https://github.com/your-username/amb_w_spc/wiki/API"
    echo ""
    echo "💬 Support:"
    echo "  • Issues: https://github.com/your-username/amb_w_spc/issues"
    echo "  • Discussions: https://github.com/your-username/amb_w_spc/discussions"
    echo ""
}

# Main installation process
main() {
    echo "🏭 AMB W SPC - Advanced Manufacturing Business with Statistical Process Control"
    echo "🚀 Installation Script v1.0.0"
    echo ""
    
    # Store original directory
    ORIGINAL_DIR=$(pwd)
    
    # Use trap to ensure we return to original directory on any exit
    trap 'cd "$ORIGINAL_DIR"' EXIT
    
    if ! check_permissions; then
        return 1
    fi
    
    if ! check_requirements; then
        return 1
    fi
    
    if ! detect_environment; then
        return 1
    fi
    
    echo ""
    echo "📋 Installation Plan:"
    echo "  1. Install Python dependencies"
    echo "  2. Install app on Frappe site"
    echo "  3. Run post-installation setup"
    echo "  4. Create sample data (optional)"
    echo "  5. Restart services"
    echo "  6. Validate installation"
    echo ""
    
    echo -n "Proceed with installation? (y/N): "
    read proceed
    
    if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        cd "$ORIGINAL_DIR"
        return 0
    fi
    
    echo ""
    log "Starting installation..."
    
    # Run each step with error handling
    if ! install_dependencies; then
        safe_exit 1
    fi
    
    if ! install_app; then
        safe_exit 1
    fi
    
    if ! post_install_setup; then
        safe_exit 1
    fi
    
    if ! create_sample_data; then
        # Sample data is optional, don't exit on failure
        warning "Sample data step completed with warnings"
    fi
    
    if ! restart_services; then
        # Service restart is important but not critical
        warning "Service restart completed with warnings"
    fi
    
    if ! run_validation; then
        safe_exit 1
    fi
    
    show_completion_info
    cd "$ORIGINAL_DIR"
}

# Error handling - use trap to catch errors but not exit the shell
trap 'error "Installation failed at line $LINENO. Check the error message above."; cd ~/frappe-bench 2>/dev/null || true; return 1' ERR

# Run main function
main "$@"
