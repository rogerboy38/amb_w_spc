import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
import json

def create_coa_from_purchase_receipt_inspection(quality_inspection_name):
    """
    Create COA from Quality Inspection results for Purchase Receipt items
    """
    try:
        # Get Quality Inspection details
        qi = frappe.get_doc("Quality Inspection", quality_inspection_name)
        
        # Check if this is from Purchase Receipt Integration
        pr_integration_name = qi.custom_purchase_receipt_integration
        
        if not pr_integration_name:
            return {"success": False, "error": "No Purchase Receipt Integration found"}
            
        # Get TDS specification for the item
        tds_spec = frappe.db.get_value(
            "TDS Product Specification",
            {"item_code": qi.item_code},
            "name"
        )
        
        if not tds_spec:
            return {"success": False, "error": f"No TDS specification found for item {qi.item_code}"}
            
        # Create COA
        coa_doc = {
            "doctype": "COA AMB",
            "linked_tds": tds_spec,
            "item_code": qi.item_code,
            "item_name": qi.item_name,
            "batch_no": qi.batch_no,
            "supplier": qi.supplier,
            "quality_inspection_reference": quality_inspection_name,
            "purchase_receipt_integration": pr_integration_name,
            "coa_date": nowdate(),
            "manufacturing_date": qi.report_date,
            "expiry_date": frappe.utils.add_months(qi.report_date, 24),
            "status": "Draft",
            "workflow_state": "Draft",
            "custom_auto_generated": 1,
            "custom_generation_source": "Purchase Receipt Quality Inspection"
        }
        
        coa = frappe.get_doc(coa_doc)
        
        # Load TDS parameters
        coa.load_tds_parameters_event(tds_spec)
        
        # Map quality inspection results to COA parameters
        map_qi_results_to_coa(coa, qi)
        
        # Insert and return
        coa.insert(ignore_permissions=True)
        
        return {
            "success": True,
            "coa_name": coa.name,
            "message": f"COA {coa.name} created from Quality Inspection {quality_inspection_name}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating COA from Purchase Receipt inspection: {str(e)}")
        return {"success": False, "error": str(e)}

def map_qi_results_to_coa(coa_doc, qi_doc):
    """Map Quality Inspection results to COA parameters"""
    try:
        # Get quality inspection readings if available
        if hasattr(qi_doc, 'readings') and qi_doc.readings:
            for reading in qi_doc.readings:
                # Find matching COA parameter
                for coa_param in coa_doc.coa_quality_test_parameter:
                    if (coa_param.parameter and reading.specification and 
                        coa_param.parameter.lower() == reading.specification.lower()):
                        
                        coa_param.result_value = reading.reading_1 or reading.reading_value
                        
                        # Determine compliance status
                        if reading.status == "Accepted":
                            coa_param.result_status = "Compliant"
                        elif reading.status == "Rejected":
                            coa_param.result_status = "Non-Compliant"
                        else:
                            coa_param.result_status = "Pending"
                            
                        break
        
        # Set overall status based on QI status
        if qi_doc.status == "Accepted":
            coa_doc.validation_status = "Compliant"
            coa_doc.overall_compliance_status = "PASS"
        elif qi_doc.status == "Rejected":
            coa_doc.validation_status = "Non-Compliant"
            coa_doc.overall_compliance_status = "FAIL"
        else:
            coa_doc.validation_status = "Pending Review"
            coa_doc.overall_compliance_status = "PENDING"
            
    except Exception as e:
        frappe.log_error(f"Error mapping QI results to COA: {str(e)}")

@frappe.whitelist()
def create_coa_for_approved_receipt_items(purchase_receipt_integration_name):
    """Create COAs for all approved items in Purchase Receipt Integration"""
    try:
        # Get Purchase Receipt Integration
        pr_integration = frappe.get_doc("Purchase Receipt Integration", purchase_receipt_integration_name)
        
        created_coas = []
        
        for item in pr_integration.items:
            if (item.quality_inspection_required and 
                item.quality_inspection and 
                item.quality_approval_status == "Approved"):
                
                # Create COA for this item
                result = create_coa_from_purchase_receipt_inspection(item.quality_inspection)
                
                if result.get("success"):
                    created_coas.append({
                        "item_code": item.item_code,
                        "coa_name": result["coa_name"],
                        "quality_inspection": item.quality_inspection
                    })
                    
                    # Link COA back to item
                    item.coa_reference = result["coa_name"]
                    
        # Save the integration document
        pr_integration.save(ignore_permissions=True)
        
        return {
            "success": True,
            "created_coas": created_coas,
            "message": f"Created {len(created_coas)} COAs for approved items"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating COAs for approved receipt items: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_coa_generation_candidates(purchase_receipt_integration_name):
    """Get items that are candidates for COA generation"""
    try:
        pr_integration = frappe.get_doc("Purchase Receipt Integration", purchase_receipt_integration_name)
        
        candidates = []
        
        for item in pr_integration.items:
            if item.quality_inspection_required and item.quality_inspection:
                # Get QI status
                qi_status = frappe.db.get_value("Quality Inspection", item.quality_inspection, "status")
                
                # Check if TDS exists for item
                tds_exists = frappe.db.exists("TDS Product Specification", {"item_code": item.item_code})
                
                # Check if COA already exists
                coa_exists = bool(item.coa_reference)
                
                candidates.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "quality_inspection": item.quality_inspection,
                    "qi_status": qi_status,
                    "tds_exists": bool(tds_exists),
                    "coa_exists": coa_exists,
                    "eligible_for_coa": (qi_status == "Accepted" and tds_exists and not coa_exists),
                    "batch_no": item.batch_no
                })
                
        return {
            "success": True,
            "candidates": candidates,
            "total_candidates": len(candidates),
            "eligible_count": len([c for c in candidates if c["eligible_for_coa"]])
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting COA generation candidates: {str(e)}")
        return {"success": False, "error": str(e)}

def auto_generate_coa_on_qi_approval(quality_inspection_doc, method):
    """
    Hook: Auto-generate COA when Quality Inspection is approved
    Called from Quality Inspection on_update
    """
    try:
        # Check if QI status changed to Accepted
        if (quality_inspection_doc.status == "Accepted" and 
            quality_inspection_doc.inspection_type == "Incoming" and
            quality_inspection_doc.custom_purchase_receipt_integration):
            
            # Check if COA already exists
            existing_coa = frappe.db.exists(
                "COA AMB", 
                {"quality_inspection_reference": quality_inspection_doc.name}
            )
            
            if not existing_coa:
                # Auto-generate COA
                result = create_coa_from_purchase_receipt_inspection(quality_inspection_doc.name)
                
                if result.get("success"):
                    frappe.msgprint(
                        _("COA {0} auto-generated for approved Quality Inspection").format(result["coa_name"]),
                        alert=True
                    )
                    
                    # Update the Purchase Receipt Integration item
                    update_purchase_receipt_item_coa_link(
                        quality_inspection_doc.custom_purchase_receipt_integration,
                        quality_inspection_doc.name,
                        result["coa_name"]
                    )
                    
    except Exception as e:
        frappe.log_error(f"Error in auto COA generation: {str(e)}")

def update_purchase_receipt_item_coa_link(pr_integration_name, qi_name, coa_name):
    """Update Purchase Receipt Integration item with COA link"""
    try:
        pr_integration = frappe.get_doc("Purchase Receipt Integration", pr_integration_name)
        
        for item in pr_integration.items:
            if item.quality_inspection == qi_name:
                item.coa_reference = coa_name
                item.quality_approval_status = "Approved"
                break
                
        pr_integration.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Error updating Purchase Receipt item COA link: {str(e)}")

@frappe.whitelist()
def validate_coa_against_purchase_receipt(coa_name):
    """Validate COA parameters against original Purchase Receipt specifications"""
    try:
        coa = frappe.get_doc("COA AMB", coa_name)
        
        if not coa.purchase_receipt_integration:
            return {"success": False, "error": "COA not linked to Purchase Receipt Integration"}
            
        # Get Purchase Receipt Integration
        pr_integration = frappe.get_doc("Purchase Receipt Integration", coa.purchase_receipt_integration)
        
        # Find the related item
        related_item = None
        for item in pr_integration.items:
            if item.item_code == coa.item_code:
                related_item = item
                break
                
        if not related_item:
            return {"success": False, "error": "Related item not found in Purchase Receipt"}
            
        # Validation results
        validation_results = {
            "basic_validation": {
                "item_code_match": coa.item_code == related_item.item_code,
                "batch_match": coa.batch_no == (related_item.batch_no if hasattr(related_item, 'batch_no') else None),
                "supplier_match": coa.supplier == pr_integration.supplier
            },
            "quality_validation": {
                "tds_linked": bool(coa.linked_tds),
                "parameters_populated": len(coa.coa_quality_test_parameter) > 0,
                "results_complete": all(p.result_value for p in coa.coa_quality_test_parameter if not coa.is_title_row(p))
            },
            "compliance_status": {
                "overall_status": coa.overall_compliance_status,
                "validation_status": coa.validation_status,
                "passed_parameters": len([p for p in coa.coa_quality_test_parameter if p.result_status == "Compliant"]),
                "failed_parameters": len([p for p in coa.coa_quality_test_parameter if p.result_status == "Non-Compliant"])
            }
        }
        
        # Calculate overall validation score
        validation_score = 0
        total_checks = 0
        
        for category in validation_results.values():
            if isinstance(category, dict):
                for check, result in category.items():
                    if isinstance(result, bool):
                        total_checks += 1
                        if result:
                            validation_score += 1
                            
        validation_percentage = (validation_score / total_checks) * 100 if total_checks > 0 else 0
        
        return {
            "success": True,
            "validation_results": validation_results,
            "validation_score": validation_score,
            "total_checks": total_checks,
            "validation_percentage": validation_percentage,
            "is_valid": validation_percentage >= 80  # 80% threshold
        }
        
    except Exception as e:
        frappe.log_error(f"Error validating COA: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def generate_certificate_from_coa(coa_name):
    """Generate quality certificate/TDS from approved COA"""
    try:
        coa = frappe.get_doc("COA AMB", coa_name)
        
        if coa.overall_compliance_status != "PASS":
            return {"success": False, "error": "COA must be compliant to generate certificate"}
            
        # Create Quality Certificate
        certificate = {
            "doctype": "Quality Certificate",
            "certificate_type": "Certificate of Analysis",
            "item_code": coa.item_code,
            "item_name": coa.item_name,
            "batch_no": coa.batch_no,
            "supplier": coa.supplier,
            "coa_reference": coa.name,
            "issue_date": nowdate(),
            "manufacturing_date": coa.manufacturing_date,
            "expiry_date": coa.expiry_date,
            "certificate_status": "Valid",
            "signed_by": frappe.session.user,
            "compliance_status": "PASS",
            "test_parameters": []
        }
        
        # Copy test parameters
        for param in coa.coa_quality_test_parameter:
            if not coa.is_title_row(param) and param.result_value:
                certificate["test_parameters"].append({
                    "parameter": param.parameter,
                    "specification": param.specification,
                    "result": param.result_value,
                    "status": param.result_status,
                    "method": param.method,
                    "uom": param.uom
                })
                
        try:
            cert_doc = frappe.get_doc(certificate)
            cert_doc.insert(ignore_permissions=True)
            
            # Link certificate back to COA
            coa.db_set("quality_certificate", cert_doc.name)
            
            return {
                "success": True,
                "certificate_name": cert_doc.name,
                "message": f"Quality Certificate {cert_doc.name} generated from COA {coa_name}"
            }
            
        except Exception:
            # If Quality Certificate DocType doesn't exist, create a document
            frappe.log_error(f"Quality Certificate DocType not found. Certificate data: {json.dumps(certificate)}")
            
            return {
                "success": True,
                "message": "Certificate data generated (DocType not available)",
                "certificate_data": certificate
            }
            
    except Exception as e:
        frappe.log_error(f"Error generating certificate: {str(e)}")
        return {"success": False, "error": str(e)}
