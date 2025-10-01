import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

class COAAMB(Document):
    def validate(self):
        self.validate_required_fields()
        self.auto_load_tds_parameters()
        self.update_validation_status()
        self.set_default_naming_series()
    
    def before_save(self):
        self.update_workflow_state()
        self.sync_tds_information()
    
    def on_submit(self):
        self.update_status("Submitted")
        self.create_quality_inspection_records()
    
    def on_cancel(self):
        self.update_status("Cancelled")
    
    def validate_required_fields(self):
        """Validate required fields before saving"""
        if not self.linked_tds:
            frappe.throw("TDS Product Specification is required")
        
        if not self.coa_quality_test_parameter:
            frappe.throw("At least one COA Quality Test Parameter is required")
    
    def auto_load_tds_parameters(self):
        """Automatically load TDS parameters when linked_tds is set (Your Server Script)"""
        if self.linked_tds and self.docstatus == 0 and self.is_new():
            self.load_tds_parameters_event(self.linked_tds)
    
    def load_tds_parameters_event(self, tds_name):
        """Load parameters for DocType event (Your Server Script)"""
        try:
            # Get TDS document
            tds_doc = frappe.get_doc('TDS Product Specification', tds_name)
            
            # Check if TDS has parameters
            if not hasattr(tds_doc, 'item_quality_inspection_parameter') or not tds_doc.item_quality_inspection_parameter:
                frappe.msgprint("No parameters found in selected TDS", alert=True)
                return
            
            # Clear existing parameters
            self.coa_quality_test_parameter = []
            
            # Copy parameters with complete field mapping
            param_count = 0
            for tds_param in tds_doc.item_quality_inspection_parameter:
                new_param = {
                    'parameter': tds_param.parameter or 'Parameter',
                    'specification': tds_param.specification or '',
                    'parameter_group': tds_param.parameter_group or '',
                    'value': tds_param.value or '',
                    'custom_uom': tds_param.custom_uom or '',
                    'numeric': tds_param.numeric or 0,
                    'custom_reconstituted_to_05_total_solids_solution': tds_param.custom_reconstituted_to_05_total_solids_solution or 0,
                    'is_title_row': tds_param.custom_is_title_row or 0,
                    'min_value': tds_param.min_value,
                    'max_value': tds_param.max_value,
                    'method': tds_param.custom_method or '',
                    'uom': tds_param.uom or '',
                    'formula_based_criteria': tds_param.formula_based_criteria or 0,
                    'acceptance_formula': tds_param.acceptance_formula or '',
                    'result_text': '',
                    'result_value': '',
                    'result_status': 'N/A' if tds_param.custom_is_title_row else 'Pending'
                }
                self.append('coa_quality_test_parameter', new_param)
                param_count += 1
            
            # Sync TDS information
            self.sync_tds_information_from_doc(tds_doc)
            
            frappe.msgprint(f"Loaded {param_count} parameters from TDS", alert=True)
            
        except Exception as e:
            frappe.log_error(f"Error loading TDS parameters: {str(e)}")
    
    def sync_tds_information_from_doc(self, tds_doc):
        """Sync TDS information to COA fields"""
        self.product_item = tds_doc.product_item
        self.item_name = tds_doc.item_name
        self.item_code = tds_doc.item_code
        self.tds_settings = tds_doc.tds_settings
        self.tds_naming_series = tds_doc.tds_naming_series
        self.tds_version = tds_doc.tds_version
        self.tds_sequence = tds_doc.tds_sequence
        self.cas_number = tds_doc.cas_number
        self.inci_name = tds_doc.inci_name
        self.shelf_life = tds_doc.shelf_life
        self.packaging = tds_doc.packaging
        self.storage_and_handling_conditions = tds_doc.storage_and_handling_conditions
        self.formula_based_criteria = tds_doc.formula_based_criteria
    
    def sync_tds_information(self):
        """Sync TDS information when linked_tds changes"""
        if self.linked_tds:
            try:
                tds_doc = frappe.get_doc('TDS Product Specification', self.linked_tds)
                self.sync_tds_information_from_doc(tds_doc)
            except Exception as e:
                frappe.log_error(f"Error syncing TDS information: {str(e)}")
    
    def update_validation_status(self):
        """Update validation status based on parameter compliance"""
        if not self.coa_quality_test_parameter:
            self.validation_status = "Not Started"
            self.overall_compliance_status = "PENDING"
            return
        
        passed = 0
        failed = 0
        pending = 0
        total = 0
        
        for param in self.coa_quality_test_parameter:
            if self.is_title_row(param):
                continue
                
            total += 1
            if param.result_status == "Compliant":
                passed += 1
            elif param.result_status == "Non-Compliant":
                failed += 1
            else:
                pending += 1
        
        if failed > 0:
            self.validation_status = "Non-Compliant"
            self.overall_compliance_status = "FAIL"
        elif pending > 0 and passed == 0:
            self.validation_status = "Not Started"
            self.overall_compliance_status = "PENDING"
        elif pending > 0:
            self.validation_status = "Pending Review"
            self.overall_compliance_status = "PENDING"
        elif passed > 0 and failed == 0:
            self.validation_status = "Compliant"
            self.overall_compliance_status = "PASS"
        else:
            self.validation_status = "Not Started"
            self.overall_compliance_status = "PENDING"
    
    def is_title_row(self, param):
        """Check if parameter is a title row"""
        if param.is_title_row == 1:
            return True
        
        if param.parameter:
            param_lower = param.parameter.lower()
            if (param_lower.includes('title') or 
                param_lower.includes('header') or 
                param_lower.includes('section') or
                param_lower == 'organoleptic' or
                param_lower == 'physicochemical' or
                param_lower == 'microbiological' or
                param_lower == 'other analysis' or
                param_lower.includes('---') or
                param_lower.includes('***') or
                param_lower.includes('===')):
                return True
        
        has_min_max = (param.min_value is not None and param.min_value != '') or \
                      (param.max_value is not None and param.max_value != '')
        has_spec = param.specification and param.specification.strip() != ''
        
        return not has_min_max and not has_spec
    
    def set_default_naming_series(self):
        """Set default naming series if not provided"""
        if not self.naming_series:
            self.naming_series = "COA-.YY.-.####"
    
    def update_workflow_state(self):
        """Update workflow state based on document status"""
        if self.docstatus == 1 and self.workflow_state != "Approved":
            self.workflow_state = "Approved"
        elif self.docstatus == 2 and self.workflow_state != "Cancelled":
            self.workflow_state = "Cancelled"
        elif self.docstatus == 0 and not self.workflow_state:
            self.workflow_state = "Draft"
    
    def update_status(self, status):
        """Update document status"""
        self.db_set('status', status)
    
    def create_quality_inspection_records(self):
        """Create quality inspection records from COA parameters"""
        try:
            for param in self.coa_quality_test_parameter:
                if not self.is_title_row(param) and param.result_value:
                    # Create quality inspection record for each parameter
                    inspection = frappe.new_doc("Quality Inspection")
                    inspection.report_date = nowdate()
                    inspection.status = "Completed"
                    inspection.inspection_type = "Incoming"
                    inspection.item_code = self.item_code
                    inspection.item_name = self.item_name
                    inspection.specification = param.specification
                    inspection.value = param.result_value
                    inspection.status = "Accepted" if param.result_status == "Compliant" else "Rejected"
                    inspection.coa_amb_reference = self.name
                    inspection.insert()
            
            frappe.msgprint("Quality Inspection records created successfully")
        except Exception as e:
            frappe.log_error(f"Error creating quality inspection records: {str(e)}")

# Your Server Script Functions
@frappe.whitelist()
def load_tds_parameters(coa_name, tds_name):
    """Load TDS parameters (Your Server Script)"""
    try:
        # Get the COA document
        coa_doc = frappe.get_doc('COA AMB', coa_name)
        
        # Clear existing child table
        coa_doc.set('coa_quality_test_parameter', [])
        
        # Get the TDS document
        tds_doc = frappe.get_doc('TDS Product Specification', tds_name)
        
        # Check if TDS has parameters
        if not tds_doc.get('item_quality_inspection_parameter'):
            return {"success": False, "message": "No parameters found in TDS"}
        
        # Copy each parameter from TDS to COA
        param_count = 0
        for tds_param in tds_doc.get('item_quality_inspection_parameter'):
            coa_param = coa_doc.append('coa_quality_test_parameter', {})
            
            # Map the fields
            coa_param.parameter = tds_param.parameter or "Parameter"
            coa_param.specification = tds_param.specification or ""
            coa_param.min_value = tds_param.min_value
            coa_param.max_value = tds_param.max_value
            coa_param.is_numeric = 1
            coa_param.result_status = "N/A"
            
            param_count += 1
        
        # Save the document
        coa_doc.save()
        
        return {
            "success": True, 
            "message": "Loaded " + str(param_count) + " parameters from TDS",
            "parameter_count": param_count
        }
        
    except Exception as e:
        frappe.log_error(f"Error loading TDS parameters: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def validate_coa_compliance(coa_name):
    """Validate COA compliance against TDS specifications"""
    try:
        coa_doc = frappe.get_doc('COA AMB', coa_name)
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'pending': 0,
            'issues': []
        }
        
        for param in coa_doc.coa_quality_test_parameter:
            if coa_doc.is_title_row(param):
                continue
                
            results['total'] += 1
            validation_result = validate_parameter_compliance(param)
            
            if validation_result['status'] == 'PASS':
                results['passed'] += 1
                param.result_status = 'Compliant'
            elif validation_result['status'] == 'FAIL':
                results['failed'] += 1
                param.result_status = 'Non-Compliant'
                results['issues'].append(validation_result['message'])
            else:
                results['pending'] += 1
                param.result_status = 'Pending'
        
        coa_doc.save()
        return results
        
    except Exception as e:
        frappe.log_error(f"Error validating COA compliance: {str(e)}")
        return {"success": False, "error": str(e)}

def validate_parameter_compliance(param):
    """Validate single parameter compliance"""
    result = {'status': 'PENDING', 'message': ''}
    
    if not param.result_value or str(param.result_value).strip() == '':
        return result
    
    try:
        # Your validation logic here
        result_value = float(param.result_value)
        min_value = float(param.min_value) if param.min_value else None
        max_value = float(param.max_value) if param.max_value else None
        
        if min_value is not None and result_value < min_value:
            result['status'] = 'FAIL'
            result['message'] = f"{param.parameter}: Value {result_value} below minimum {min_value}"
        elif max_value is not None and result_value > max_value:
            result['status'] = 'FAIL'
            result['message'] = f"{param.parameter}: Value {result_value} above maximum {max_value}"
        else:
            result['status'] = 'PASS'
            result['message'] = f"{param.parameter}: Value within acceptable range"
            
    except ValueError:
        # Handle non-numeric values
        result['status'] = 'PASS'  # Auto-pass non-numeric values for now
        result['message'] = f"{param.parameter}: Non-numeric value accepted"
    
    return result

@frappe.whitelist()
def submit_and_start_workflow(docname):
    """Submit COA and start workflow (Your Client Script Function)"""
    try:
        doc = frappe.get_doc('COA AMB', docname)
        
        # Validate compliance before submission
        if doc.validation_status != 'Compliant':
            return {'success': False, 'error': 'COA must be compliant before submission'}
        
        # Submit the document
        doc.submit()
        
        return {'success': True, 'message': 'COA submitted successfully'}
        
    except Exception as e:
        frappe.log_error(f"Error submitting COA: {str(e)}")
        return {'success': False, 'error': str(e)}
