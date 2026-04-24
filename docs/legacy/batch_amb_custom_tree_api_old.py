"""
Archived Server Script: batch_amb_custom_tree_api_old

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: API
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
# Batch AMB Server Script - Nested Set Compatible (Fixed Version)

#import frappe
#from frappe import _

def before_insert(self, method):
    """Set up parent relationship before insert"""
    if self.custom_batch_level and int(self.custom_batch_level) > 1:
        if not self.parent_batch_amb:
            frappe.throw(_("Parent Batch AMB is required for level {0}").format(self.custom_batch_level))
        
        # Ensure parent field is set for nested set to work properly
        if not hasattr(self, 'parent'):
            self.parent = self.parent_batch_amb

    # Initialize lft and rgt as integers
    self.lft = 0
    self.rgt = 0

def before_save(self, method):
    """Validate data before saving"""
    # Validate batch level and parent relationship
    if self.custom_batch_level and int(self.custom_batch_level) > 1:
        if not self.parent_batch_amb:
            frappe.throw(_("Parent Batch AMB is required for level {0}").format(self.custom_batch_level))
    
    # Force lft and rgt to be integers (CRITICAL)
    self.lft = int(self.lft) if self.lft is not None else 0
    self.rgt = int(self.rgt) if self.rgt is not None else 0

def validate(self, method):
    """Validate the document"""
    # Ensure title is set
    if not self.title and self.custom_generated_batch_name:
        self.title = self.custom_generated_batch_name
    
    # Set is_group based on level
    if self.custom_batch_level:
        if int(self.custom_batch_level) == 1:
            self.is_group = 1
        else:
            self.is_group = 0
    
    # Force lft and rgt to be integers
    self.lft = int(self.lft) if self.lft is not None else 0
    self.rgt = int(self.rgt) if self.rgt is not None else 0

def on_update(self, method):
    """Custom nested set update - let the overridden function handle this"""
    # The overridden update_nsm function will handle this
    pass
"""
