#!/usr/bin/env python3
"""
Workflow Restoration Script for amb_w_spc Application

This script restores workflow configurations after successful DocType installation.
It moves the corrected workflow files back to their proper locations.
"""

import os
import shutil
import sys
from pathlib import Path

def restore_workflows():
    """Restore workflow files to their proper locations"""
    
    print("=== AMB_W_SPC Workflow Restoration ===")
    print("Restoring workflow configurations after DocType installation...")
    
    # Base paths
    base_path = Path(os.getcwd())
    backup_path = base_path / "workflow_backup" / "corrected_workflows"
    target_path = base_path / "amb_w_spc" / "amb_w_spc"
    
    if not backup_path.exists():
        print(f"ERROR: Workflow backup directory not found at {backup_path}")
        return False
    
    if not target_path.exists():
        print(f"ERROR: Target application directory not found at {target_path}")
        return False
    
    # Workflow restoration mappings
    restorations = [
        {
            "source": backup_path / "spc_alert_workflow",
            "target": target_path / "spc_quality_management" / "doctype" / "spc_alert_workflow",
            "name": "SPC Alert Workflow"
        },
        {
            "source": backup_path / "spc_corrective_action_workflow",
            "target": target_path / "spc_quality_management" / "doctype" / "spc_corrective_action_workflow",
            "name": "SPC Corrective Action Workflow"
        },
        {
            "source": backup_path / "spc_process_capability_workflow",
            "target": target_path / "spc_quality_management" / "doctype" / "spc_process_capability_workflow",
            "name": "SPC Process Capability Workflow"
        },
        {
            "source": backup_path / "system_integration" / "workflows",
            "target": target_path / "system_integration" / "workflows",
            "name": "System Integration Workflows"
        }
    ]
    
    # Restore each workflow
    restored_count = 0
    
    for restoration in restorations:
        try:
            if restoration["source"].exists():
                # Create target directory if it doesn't exist
                restoration["target"].parent.mkdir(parents=True, exist_ok=True)
                
                # Remove existing target if it exists
                if restoration["target"].exists():
                    if restoration["target"].is_dir():
                        shutil.rmtree(restoration["target"])
                    else:
                        restoration["target"].unlink()
                
                # Copy the workflow
                if restoration["source"].is_dir():
                    shutil.copytree(restoration["source"], restoration["target"])
                else:
                    shutil.copy2(restoration["source"], restoration["target"])
                
                print(f"✓ Restored: {restoration['name']}")
                restored_count += 1
            else:
                print(f"⚠ Warning: Source not found for {restoration['name']}")
        
        except Exception as e:
            print(f"✗ Error restoring {restoration['name']}: {str(e)}")
            return False
    
    print(f"\n=== Restoration Complete ===")
    print(f"Successfully restored {restored_count} workflow configurations.")
    print("\nNext steps:")
    print("1. Run 'bench migrate' to install the workflow DocTypes")
    print("2. Restart your Frappe/ERPNext instance")
    print("3. Verify workflows are active in the system")
    
    return True

if __name__ == "__main__":
    success = restore_workflows()
    sys.exit(0 if success else 1)
