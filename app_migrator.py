import os
import json
import shutil
import subprocess

class AppMigrator:
    """Comprehensive app migration fixer based on lessons learned"""
    
    def __init__(self, app_path, site_name):
        self.app_path = app_path
        self.site_name = site_name
        self.bench_path = "/home/frappe/frappe-bench-spc"
    
    def detect_orphaned_doctypes(self):
        """Detect orphaned doctypes that aren't properly connected to modules"""
        print("=== DETECTING ORPHANED DOCTYPES ===")
        
        orphaned_doctypes = []
        
        # Check all doctype directories
        for root, dirs, files in os.walk(self.app_path):
            if root.endswith('/doctype'):
                for doctype_dir in dirs:
                    doctype_path = os.path.join(root, doctype_dir)
                    json_file = os.path.join(doctype_path, f"{doctype_dir}.json")
                    python_file = os.path.join(doctype_path, f"{doctype_dir}.py")
                    
                    if os.path.exists(json_file):
                        try:
                            with open(json_file, 'r') as f:
                                doctype_data = json.load(f)
                            
                            module = doctype_data.get('module', '')
                            name = doctype_data.get('name', '')
                            
                            # Check if Python file exists and has proper class
                            python_ok = self._check_python_file(python_file, doctype_dir)
                            
                            if not module or not python_ok:
                                orphaned_doctypes.append({
                                    'doctype': doctype_dir,
                                    'module': module,
                                    'json_file': json_file,
                                    'python_file': python_file,
                                    'module_path': root.replace(self.app_path + '/', '').split('/doctype')[0]
                                })
                                print(f"❌ Orphaned: {doctype_dir} (module: '{module}')")
                            else:
                                print(f"✅ OK: {doctype_dir} (module: '{module}')")
                                
                        except Exception as e:
                            print(f"❌ Error reading {json_file}: {e}")
        
        return orphaned_doctypes
    
    def _check_python_file(self, python_file, doctype_name):
        """Check if Python file exists and has proper class structure"""
        if not os.path.exists(python_file):
            return False
        
        try:
            with open(python_file, 'r') as f:
                content = f.read()
            
            # Check for basic required elements
            required_imports = ['from frappe.model.document import Document', 'import frappe']
            class_name = doctype_name.replace('_', ' ').title().replace(' ', '')
            
            has_imports = any(imp in content for imp in required_imports)
            has_class = f"class {class_name}" in content
            
            return has_imports and has_class
            
        except:
            return False
    
    def fix_orphaned_doctypes(self, orphaned_doctypes):
        """Fix orphaned doctypes using lessons learned"""
        print("\n=== FIXING ORPHANED DOCTYPES ===")
        
        fixes_applied = []
        
        for doctype_info in orphaned_doctypes:
            doctype_name = doctype_info['doctype']
            module_path = doctype_info['module_path']
            json_file = doctype_info['json_file']
            python_file = doctype_info['python_file']
            
            print(f"\n🔧 Fixing {doctype_name}...")
            
            # 1. Fix JSON module reference
            module_name = self._get_module_name(module_path)
            self._fix_json_module(json_file, module_name)
            
            # 2. Fix Python file
            self._fix_python_file(python_file, doctype_name)
            
            # 3. Ensure proper __init__.py structure
            self._ensure_module_structure(module_path)
            
            fixes_applied.append({
                'doctype': doctype_name,
                'module': module_name,
                'status': 'fixed'
            })
            
            print(f"✅ Fixed {doctype_name} → module: {module_name}")
        
        return fixes_applied
    
    def _get_module_name(self, module_path):
        """Convert module path to proper module name"""
        module_mapping = {
            'core_spc': 'Core SPC',
            'system_integration': 'System Integration',
            'sfc_manufacturing': 'SFC Manufacturing',
            'spc_quality_management': 'SPC Quality Management',
            'operator_management': 'Operator Management',
            'sensor_management': 'Sensor Management',
            'shop_floor_control': 'Shop Floor Control',
            'fda_compliance': 'FDA Compliance',
            'real_time_monitoring': 'Real Time Monitoring',
            'plant_equipment': 'Plant Equipment'
        }
        
        return module_mapping.get(module_path, module_path.replace('_', ' ').title())
    
    def _fix_json_module(self, json_file, module_name):
        """Fix the module reference in doctype JSON file"""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            old_module = data.get('module', '')
            data['module'] = module_name
            
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            if old_module != module_name:
                print(f"   📝 JSON: module '{old_module}' → '{module_name}'")
                
        except Exception as e:
            print(f"   ❌ Error fixing JSON: {e}")
    
    def _fix_python_file(self, python_file, doctype_name):
        """Fix the Python file with proper class structure"""
        class_name = doctype_name.replace('_', ' ').title().replace(' ', '')
        
        python_content = f'''import frappe
from frappe.model.document import Document

class {class_name}(Document):
    """Auto-generated by AppMigrator"""
    pass
'''
        
        os.makedirs(os.path.dirname(python_file), exist_ok=True)
        with open(python_file, 'w') as f:
            f.write(python_content)
        
        print(f"   📝 Python: Created {class_name} class")
    
    def _ensure_module_structure(self, module_path):
        """Ensure proper Python module structure"""
        module_dir = os.path.join(self.app_path, module_path)
        
        # Create module __init__.py
        init_file = os.path.join(module_dir, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write(f"# {module_path} module\n")
        
        # Create doctype __init__.py
        doctype_dir = os.path.join(module_dir, 'doctype')
        if os.path.exists(doctype_dir):
            init_file = os.path.join(doctype_dir, '__init__.py')
            if not os.path.exists(init_file):
                with open(init_file, 'w') as f:
                    f.write("# Doctype package\n")
    
    def update_hooks_for_all_modules(self):
        """Update hooks.py to include all detected modules"""
        print("\n=== UPDATING HOOKS.PY ===")
        
        hooks_file = os.path.join(self.app_path, 'hooks.py')
        
        # Detect all modules
        modules = []
        for item in os.listdir(self.app_path):
            item_path = os.path.join(self.app_path, item)
            if os.path.isdir(item_path) and not item.startswith('.') and item != 'www':
                modules.append(item)
        
        # Create hooks content
        hooks_content = f'''from . import __version__ as app_version

app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "Your Company"
app_description = "Advanced Manufacturing with SPC"
app_email = "your-email@example.com"
app_license = "MIT"

# Includes in <base>/apps/amb_w_spc/amb_w_spc
app_include_js = "/assets/amb_w_spc/js/amb_w_spc.js"

# Apps to include in the site
app_include = {json.dumps(modules, indent=4)}

# Fixtures
fixtures = [
    {{"dt": "DocType", "filters": [["module", "in", {json.dumps([self._get_module_name(m) for m in modules], indent=8)}]}}
]

# After install hook
after_install = "amb_w_spc.install.after_install"
'''
        
        with open(hooks_file, 'w') as f:
            f.write(hooks_content)
        
        print(f"✅ Updated hooks.py with {len(modules)} modules:")
        for module in modules:
            print(f"   📦 {module}")
    
    def clean_caches(self):
        """Clean all caches"""
        print("\n=== CLEANING CACHES ===")
        
        commands = [
            ['bench', '--site', self.site_name, 'clear-cache'],
            ['bench', 'clear-cache'],
            ['bench', '--site', self.site_name, 'clear-website-cache'],
        ]
        
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.bench_path)
                if result.returncode == 0:
                    print(f"✅ {cmd[1]}")
                else:
                    print(f"⚠️  {cmd[1]}: {result.stderr}")
            except Exception as e:
                print(f"❌ {cmd[1]}: {e}")
        
        # Remove __pycache__ directories
        import glob
        pycache_dirs = glob.glob(f"{self.app_path}/**/__pycache__", recursive=True)
        for pycache_dir in pycache_dirs:
            try:
                shutil.rmtree(pycache_dir)
                print(f"✅ Removed {pycache_dir.replace(self.app_path + '/', '')}")
            except:
                pass
    
    def run_complete_migration_fix(self):
        """Run complete migration fix process"""
        print("🚀 STARTING COMPLETE MIGRATION FIX")
        print("=" * 50)
        
        # 1. Detect issues
        orphaned_doctypes = self.detect_orphaned_doctypes()
        
        if not orphaned_doctypes:
            print("✅ No orphaned doctypes detected!")
        else:
            # 2. Fix issues
            fixes = self.fix_orphaned_doctypes(orphaned_doctypes)
        
        # 3. Update hooks
        self.update_hooks_for_all_modules()
        
        # 4. Clean caches
        self.clean_caches()
        
        print("\n" + "=" * 50)
        print("🎉 MIGRATION FIX COMPLETED!")
        print("\n📋 NEXT STEPS:")
        print("1. Run migration: bench --site test-spc3 migrate")
        print("2. Export fixtures: bench --site test-spc3 export-fixtures --app amb_w_spc")
        print("3. Verify: bench --site test-spc3 list-apps")

# Run the migrator
if __name__ == "__main__":
    app_path = "/home/frappe/frappe-bench-spc/apps/amb_w_spc/amb_w_spc"
    site_name = "test-spc3"
    
    migrator = AppMigrator(app_path, site_name)
    migrator.run_complete_migration_fix()
