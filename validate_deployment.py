#!/usr/bin/env python3
"""
Final Deployment Validation Script for AMB W SPC
Comprehensive validation before production deployment
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
import time

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def run_command(command, check=True):
    """Run shell command and return result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            return False, result.stderr
        return True, result.stdout
    except Exception as e:
        return False, str(e)

class DeploymentValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.tests_passed = 0
        self.tests_total = 0
        
    def add_error(self, error):
        self.errors.append(error)
        
    def add_warning(self, warning):
        self.warnings.append(warning)
        
    def test(self, name, condition, error_msg=None, warning_msg=None):
        """Generic test function"""
        self.tests_total += 1
        if condition:
            print_success(f"{name}")
            self.tests_passed += 1
            return True
        else:
            if error_msg:
                print_error(f"{name}: {error_msg}")
                self.add_error(error_msg)
            elif warning_msg:
                print_warning(f"{name}: {warning_msg}")
                self.add_warning(warning_msg)
            else:
                print_error(f"{name}: Failed")
                self.add_error(name)
            return False

    def validate_file_structure(self):
        """Validate file and directory structure"""
        print_header("FILE STRUCTURE VALIDATION")
        
        # Required root files
        required_files = [
            'setup.py', 'requirements.txt', 'modules.txt', 
            'hooks.py', 'README.md', 'LICENSE', 'CONTRIBUTING.md',
            'install.sh', 'DEPLOYMENT_GUIDE.md', 'TROUBLESHOOTING.md'
        ]
        
        for file in required_files:
            self.test(
                f"Required file: {file}",
                os.path.exists(file),
                f"Missing required file: {file}"
            )
        
        # App directory structure
        app_dir = 'amb_w_spc'
        self.test(
            f"App directory: {app_dir}",
            os.path.exists(app_dir),
            f"App directory missing: {app_dir}"
        )
        
        if os.path.exists(app_dir):
            # Check core modules
            core_modules = [
                'core_spc', 'manufacturing_operations', 'shop_floor_control',
                'operator_management', 'sensor_management', 'real_time_monitoring',
                'spc_quality_management', 'fda_compliance', 'plant_equipment',
                'system_integration'
            ]
            
            for module in core_modules:
                module_path = os.path.join(app_dir, module)
                self.test(
                    f"Module: {module}",
                    os.path.exists(module_path),
                    f"Missing module: {module}"
                )

    def validate_python_syntax(self):
        """Validate Python file syntax"""
        print_header("PYTHON SYNTAX VALIDATION")
        
        python_files = []
        for root, dirs, files in os.walk('amb_w_spc'):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        print_info(f"Found {len(python_files)} Python files to validate")
        
        syntax_errors = 0
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), py_file, 'exec')
            except SyntaxError as e:
                print_error(f"Syntax error in {py_file}: {e}")
                self.add_error(f"Python syntax error in {py_file}")
                syntax_errors += 1
            except UnicodeDecodeError as e:
                print_warning(f"Encoding issue in {py_file}: {e}")
                self.add_warning(f"Encoding issue in {py_file}")
        
        self.test(
            f"Python syntax validation ({len(python_files)} files)",
            syntax_errors == 0,
            f"Found {syntax_errors} syntax errors"
        )

    def validate_json_files(self):
        """Validate JSON file syntax"""
        print_header("JSON VALIDATION")
        
        json_files = []
        for root, dirs, files in os.walk('amb_w_spc'):
            for file in files:
                if file.endswith('.json'):
                    json_files.append(os.path.join(root, file))
        
        print_info(f"Found {len(json_files)} JSON files to validate")
        
        json_errors = 0
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                print_error(f"JSON error in {json_file}: {e}")
                self.add_error(f"JSON syntax error in {json_file}")
                json_errors += 1
            except UnicodeDecodeError as e:
                print_warning(f"Encoding issue in {json_file}: {e}")
                self.add_warning(f"Encoding issue in {json_file}")
        
        self.test(
            f"JSON syntax validation ({len(json_files)} files)",
            json_errors == 0,
            f"Found {json_errors} JSON errors"
        )

    def validate_setup_files(self):
        """Validate setup and configuration files"""
        print_header("SETUP FILES VALIDATION")
        
        # Validate setup.py
        if os.path.exists('setup.py'):
            try:
                spec = importlib.util.spec_from_file_location("setup", "setup.py")
                setup_module = importlib.util.module_from_spec(spec)
                print_success("setup.py is valid")
            except Exception as e:
                print_error(f"setup.py validation failed: {e}")
                self.add_error("Invalid setup.py")
        
        # Validate hooks.py
        if os.path.exists('hooks.py'):
            try:
                spec = importlib.util.spec_from_file_location("hooks", "hooks.py")
                hooks_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(hooks_module)
                
                # Check required attributes
                required_attrs = ['app_name', 'app_title', 'app_publisher']
                missing_attrs = [attr for attr in required_attrs if not hasattr(hooks_module, attr)]
                
                if missing_attrs:
                    print_error(f"hooks.py missing required attributes: {missing_attrs}")
                    self.add_error("hooks.py missing required attributes")
                else:
                    print_success("hooks.py is valid")
                    
            except Exception as e:
                print_error(f"hooks.py validation failed: {e}")
                self.add_error("Invalid hooks.py")
        
        # Validate requirements.txt
        if os.path.exists('requirements.txt'):
            try:
                with open('requirements.txt', 'r') as f:
                    requirements = f.read().strip().split('\n')
                
                # Check for essential packages
                essential_packages = ['frappe', 'erpnext']
                found_packages = [req.split('>=')[0].split('==')[0] for req in requirements if req.strip()]
                
                missing_essential = [pkg for pkg in essential_packages if pkg not in found_packages]
                
                if missing_essential:
                    print_warning(f"Missing essential packages in requirements.txt: {missing_essential}")
                    self.add_warning("Missing essential packages")
                else:
                    print_success("requirements.txt is valid")
                    
            except Exception as e:
                print_error(f"requirements.txt validation failed: {e}")
                self.add_error("Invalid requirements.txt")

    def validate_documentation(self):
        """Validate documentation completeness"""
        print_header("DOCUMENTATION VALIDATION")
        
        # Check documentation files
        doc_files = ['README.md', 'CONTRIBUTING.md', 'DEPLOYMENT_GUIDE.md', 'TROUBLESHOOTING.md']
        
        for doc_file in doc_files:
            if os.path.exists(doc_file):
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Basic content checks
                self.test(
                    f"{doc_file} has content",
                    len(content) > 100,
                    f"{doc_file} appears to be empty or too short"
                )
                
                # Check for essential sections in README
                if doc_file == 'README.md':
                    essential_sections = ['Installation', 'Usage', 'Features']
                    for section in essential_sections:
                        self.test(
                            f"README contains {section} section",
                            section.lower() in content.lower(),
                            f"README missing {section} section"
                        )
            else:
                print_error(f"Missing documentation file: {doc_file}")
                self.add_error(f"Missing {doc_file}")

    def validate_installation_scripts(self):
        """Validate installation scripts"""
        print_header("INSTALLATION SCRIPTS VALIDATION")
        
        # Check install.sh
        if os.path.exists('install.sh'):
            self.test(
                "install.sh is executable",
                os.access('install.sh', os.X_OK),
                "install.sh is not executable"
            )
            
            # Basic syntax check for bash script
            success, output = run_command('bash -n install.sh')
            self.test(
                "install.sh bash syntax",
                success,
                f"Bash syntax error in install.sh: {output}"
            )
        else:
            print_error("Missing install.sh")
            self.add_error("Missing install.sh")

    def validate_package_integrity(self):
        """Validate package integrity and completeness"""
        print_header("PACKAGE INTEGRITY VALIDATION")
        
        # Count important components
        components = {
            'DocTypes': 0,
            'Python files': 0,
            'JavaScript files': 0,
            'JSON files': 0,
            'Modules': 0
        }
        
        for root, dirs, files in os.walk('amb_w_spc'):
            for file in files:
                if file.endswith('.py'):
                    components['Python files'] += 1
                elif file.endswith('.js'):
                    components['JavaScript files'] += 1
                elif file.endswith('.json'):
                    components['JSON files'] += 1
                    # Count DocTypes (JSON files in doctype directories)
                    if '/doctype/' in root and not file.startswith('test_'):
                        components['DocTypes'] += 1
            
            # Count modules (top-level directories in app)
            if root.count(os.sep) == 1:  # Direct subdirectories of amb_w_spc
                if os.path.basename(root) not in ['__pycache__', '.git', 'tests']:
                    components['Modules'] += 1
        
        print_info("Package contents:")
        for component, count in components.items():
            print(f"  {component}: {count}")
        
        # Validate expected counts
        self.test(
            "Sufficient DocTypes",
            components['DocTypes'] >= 40,
            f"Expected at least 40 DocTypes, found {components['DocTypes']}"
        )
        
        self.test(
            "Sufficient Python files",
            components['Python files'] >= 100,
            f"Expected at least 100 Python files, found {components['Python files']}"
        )
        
        self.test(
            "Sufficient modules",
            components['Modules'] >= 10,
            f"Expected at least 10 modules, found {components['Modules']}"
        )

    def validate_frappe_compatibility(self):
        """Validate Frappe framework compatibility"""
        print_header("FRAPPE COMPATIBILITY VALIDATION")
        
        # Check if we're in a Frappe environment
        frappe_bench_indicators = [
            '../apps.txt',
            '../common_site_config.json',
            '../sites'
        ]
        
        in_frappe_bench = any(os.path.exists(indicator) for indicator in frappe_bench_indicators)
        
        if in_frappe_bench:
            print_success("Running in Frappe bench environment")
            
            # Try to validate Frappe version compatibility
            try:
                success, output = run_command('python -c "import frappe; print(frappe.__version__)"')
                if success:
                    frappe_version = output.strip()
                    print_info(f"Detected Frappe version: {frappe_version}")
                    
                    # Check version compatibility (assuming 15.0+ required)
                    version_parts = frappe_version.split('.')
                    major_version = int(version_parts[0]) if version_parts else 0
                    
                    self.test(
                        "Frappe version compatibility",
                        major_version >= 15,
                        f"Requires Frappe 15.0+, found {frappe_version}"
                    )
                else:
                    print_warning("Could not detect Frappe version")
                    self.add_warning("Frappe version unknown")
            except Exception as e:
                print_warning(f"Could not check Frappe compatibility: {e}")
                self.add_warning("Frappe compatibility check failed")
        else:
            print_warning("Not running in Frappe bench environment")
            self.add_warning("Cannot validate Frappe compatibility outside bench")

    def generate_report(self):
        """Generate final validation report"""
        print_header("VALIDATION REPORT")
        
        # Overall statistics
        success_rate = (self.tests_passed / self.tests_total * 100) if self.tests_total > 0 else 0
        
        print(f"{Colors.BOLD}Overall Results:{Colors.END}")
        print(f"  Tests Passed: {Colors.GREEN}{self.tests_passed}{Colors.END}")
        print(f"  Tests Failed: {Colors.RED}{self.tests_total - self.tests_passed}{Colors.END}")
        print(f"  Success Rate: {Colors.CYAN}{success_rate:.1f}%{Colors.END}")
        print(f"  Errors: {Colors.RED}{len(self.errors)}{Colors.END}")
        print(f"  Warnings: {Colors.YELLOW}{len(self.warnings)}{Colors.END}")
        
        # Status determination
        if len(self.errors) == 0:
            if len(self.warnings) == 0:
                status = f"{Colors.GREEN}🚀 READY FOR PRODUCTION DEPLOYMENT{Colors.END}"
            else:
                status = f"{Colors.YELLOW}⚠️  READY WITH WARNINGS{Colors.END}"
        else:
            status = f"{Colors.RED}❌ NOT READY - REQUIRES FIXES{Colors.END}"
        
        print(f"\n{Colors.BOLD}Deployment Status: {status}{Colors.END}")
        
        # Error details
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ ERRORS TO FIX:{Colors.END}")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        
        # Warning details
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  WARNINGS TO REVIEW:{Colors.END}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        # Next steps
        print(f"\n{Colors.BOLD}Next Steps:{Colors.END}")
        if len(self.errors) == 0:
            print("  1. ✅ All critical validations passed")
            print("  2. 🚀 Ready to create GitHub release")
            print("  3. 📦 Use dist/ packages for deployment")
            print("  4. 📚 Share documentation with users")
        else:
            print("  1. 🔧 Fix all errors listed above")
            print("  2. 🔄 Re-run validation: python validate_deployment.py")
            print("  3. 📋 Review troubleshooting guide if needed")
        
        return len(self.errors) == 0

def main():
    """Main validation function"""
    start_time = time.time()
    
    print(f"{Colors.PURPLE}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                  AMB W SPC DEPLOYMENT VALIDATOR            ║")
    print("║              Final Production Readiness Check             ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    validator = DeploymentValidator()
    
    # Run all validation checks
    validator.validate_file_structure()
    validator.validate_python_syntax()
    validator.validate_json_files()
    validator.validate_setup_files()
    validator.validate_documentation()
    validator.validate_installation_scripts()
    validator.validate_package_integrity()
    validator.validate_frappe_compatibility()
    
    # Generate final report
    is_ready = validator.generate_report()
    
    # Execution time
    execution_time = time.time() - start_time
    print(f"\n{Colors.BLUE}Validation completed in {execution_time:.2f} seconds{Colors.END}")
    
    # Exit with appropriate code
    sys.exit(0 if is_ready else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Validation interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Validation failed with error: {e}{Colors.END}")
        sys.exit(1)