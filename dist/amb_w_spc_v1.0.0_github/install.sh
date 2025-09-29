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

# Check if running as root
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) ]]; then
        error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    success "Python $PYTHON_VERSION ✓"
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        warning "Node.js not found. Please install Node.js 16+ for full functionality"
    else
        NODE_VERSION=$(node --version | cut -d'v' -f2)
        success "Node.js $NODE_VERSION ✓"
    fi
    
    # Check if we're in a Frappe bench
    if [[ ! -f "../apps.txt" ]]; then
        error "This script must be run from within a Frappe bench apps directory"
        echo "Expected structure: /path/to/frappe-bench/apps/amb_w_spc"
        exit 1
    fi
    success "Frappe bench environment detected ✓"
}

# Detect Frappe bench path and site
detect_environment() {
    log "Detecting environment..."
    
    BENCH_PATH=$(cd ../../ && pwd)
    APP_PATH=$(pwd)
    
    # Get available sites
    SITES=($(ls -d ${BENCH_PATH}/sites/*/ 2>/dev/null | xargs -n 1 basename | grep -v assets | grep -v common_site_config.json || true))
    
    if [[ ${#SITES[@]} -eq 0 ]]; then
        error "No Frappe sites found in $BENCH_PATH/sites/"
        exit 1
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
            exit 1
        fi
    fi
    
    success "Using site: $SITE_NAME"
    success "Bench path: $BENCH_PATH"
}

# Install Python dependencies
install_dependencies() {
    log "Installing Python dependencies..."
    
    cd "$BENCH_PATH"
    
    # Install requirements
    if [[ -f "apps/amb_w_spc/requirements.txt" ]]; then
        ./env/bin/pip install -r apps/amb_w_spc/requirements.txt
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
    bench --site "$SITE_NAME" install-app amb_w_spc
    success "App installed on site $SITE_NAME"
}

# Run post-installation setup
post_install_setup() {
    log "Running post-installation setup..."
    
    cd "$BENCH_PATH"
    
    # Clear cache
    bench --site "$SITE_NAME" clear-cache
    
    # Run migrations
    bench --site "$SITE_NAME" migrate
    
    # Build assets
    bench build --app amb_w_spc
    
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
        bench --site "$SITE_NAME" execute amb_w_spc.fixtures.create_sample_data || {
            warning "Sample data creation failed, but installation is complete"
        }
        success "Sample data created"
    fi
}

# Restart services
restart_services() {
    log "Restarting services..."
    
    cd "$BENCH_PATH"
    
    # Restart bench
    bench restart
    
    success "Services restarted"
}

# Run validation tests
run_validation() {
    log "Running installation validation..."
    
    cd "$BENCH_PATH"
    
    # Test app import
    bench --site "$SITE_NAME" console <<< "import amb_w_spc; print('✅ App import successful')" || {
        error "App import failed"
        exit 1
    }
    
    # Test database
    bench --site "$SITE_NAME" execute "frappe.get_doc('DocType', 'SPC Data Point')" &>/dev/null || {
        error "Database validation failed"
        exit 1
    }
    
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
    
    check_permissions
    check_requirements
    detect_environment
    
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
        exit 0
    fi
    
    echo ""
    log "Starting installation..."
    
    install_dependencies
    install_app
    post_install_setup
    create_sample_data
    restart_services
    run_validation
    
    show_completion_info
}

# Error handling
trap 'error "Installation failed at line $LINENO. Check the error message above."' ERR

# Run main function
main "$@"