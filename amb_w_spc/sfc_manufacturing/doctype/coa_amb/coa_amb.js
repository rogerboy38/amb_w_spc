// COA AMB Enhanced Client Script - Complete Working Version
frappe.ui.form.on('COA AMB', {
    onload: function(frm) {
        // Initialize naming series for new documents
        if (frm.is_new() && frm.doc.naming_series) {
            frm.set_value('naming_series', '');
        }
    },
    
    refresh: function(frm) {
        console.log('COA AMB Form Refreshed - Setting up buttons');
        
        // Clear any existing buttons first
        frm.page.clear_icons();
        frm.page.clear_actions();
        
        // Add main action buttons
        frm.add_custom_button(__('📥 Load TDS Parameters'), function() {
            load_tds_parameters_enhanced(frm);
        });
        
        frm.add_custom_button(__('✅ Validate Compliance'), function() {
            validate_tds_compliance_enhanced(frm);
        });
        
        // Add Submit button if compliant and not submitted
        if (frm.doc.docstatus === 0 && frm.doc.validation_status === 'Compliant') {
            frm.add_custom_button(__('🚀 Submit COA'), function() {
                submit_coa_document(frm);
            }).addClass('btn-primary');
            
            frappe.show_alert({
                message: __('✅ Document is compliant and ready for submission'),
                indicator: 'green'
            });
        }
        
        // Add utility buttons
        if(!frm.is_new()) {
            frm.add_custom_button(__('🔍 Debug Values'), function() {
                debug_current_values(frm);
            });
            
            frm.add_custom_button(__('🗑️ Clear Parameters'), function() {
                clear_parameters_with_confirmation(frm);
            });
        }
        
        // Apply enhanced styling
        apply_enhanced_styles();
        
        console.log('Form setup complete. Validation status:', frm.doc.validation_status);
    },
    
    after_save: function(frm) {
        console.log('Document saved. Refreshing buttons...');
        // Refresh to show updated buttons
        setTimeout(function() {
            frm.refresh();
        }, 500);
    },
    
    linked_tds: function(frm) {
        if (frm.doc.linked_tds) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'TDS Product Specification',
                    name: frm.doc.linked_tds
                },
                callback: function(r) {
                    if (r.message) {
                        var param_count = r.message.item_quality_inspection_parameter ? r.message.item_quality_inspection_parameter.length : 0;
                        frappe.show_alert({
                            message: __('TDS Selected: {0} parameters available', [param_count]),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    }
});

// Enhanced TDS Parameter Loading
function load_tds_parameters_enhanced(frm) {
    if (!frm.doc.linked_tds) {
        frappe.msgprint({
            title: __('TDS Required'),
            message: __('Please select a TDS Product Specification first'),
            indicator: 'red'
        });
        return;
    }
    
    if (!frm.doc.name) {
        frappe.confirm(
            __('Document must be saved before loading parameters. Save now?'),
            function() {
                frm.save().then(function() {
                    execute_parameter_loading(frm);
                });
            }
        );
        return;
    }
    
    execute_parameter_loading(frm);
}

function execute_parameter_loading(frm) {
    var loading_dialog = frappe.show_progress(
        __('Loading Parameters'),
        __('Fetching parameters from TDS...'),
        0
    );
    
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'TDS Product Specification',
            name: frm.doc.linked_tds
        },
        callback: function(r) {
            loading_dialog.hide();
            
            if (r.message) {
                process_tds_parameters(r.message, frm);
                frappe.show_alert({
                    message: __('✅ Successfully loaded parameters from TDS'),
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    title: __('Loading Failed'),
                    message: __('Could not load TDS parameters'),
                    indicator: 'red'
                });
            }
        }
    });
}

function process_tds_parameters(tds_doc, frm) {
    if (!tds_doc.item_quality_inspection_parameter || tds_doc.item_quality_inspection_parameter.length === 0) {
        frappe.msgprint({
            title: __('No Parameters'),
            message: __('No parameters found in the selected TDS'),
            indicator: 'orange'
        });
        return;
    }
    
    // Clear existing parameters
    frm.clear_table('coa_quality_test_parameter');
    
    // Add parameters from TDS
    tds_doc.item_quality_inspection_parameter.forEach(function(tds_param) {
        var row = frm.add_child('coa_quality_test_parameter');
        
        // Map TDS fields to COA fields
        row.parameter = tds_param.parameter || 'Parameter';
        row.specification = tds_param.specification || '';
        row.parameter_group = tds_param.parameter_group || '';
        row.value = tds_param.value || '';
        row.custom_uom = tds_param.custom_uom || '';
        row.numeric = tds_param.numeric || 0;
        row.min_value = tds_param.min_value;
        row.max_value = tds_param.max_value;
        row.method = tds_param.custom_method || '';
        row.uom = tds_param.uom || '';
        
        // Initialize result fields
        row.result_value = '';
        row.result_text = 'PENDING';
        row.result_status = 'Pending';
    });
    
    frm.refresh_field('coa_quality_test_parameter');
}

// Enhanced Compliance Validation
function validate_tds_compliance_enhanced(frm) {
    if (!frm.doc.coa_quality_test_parameter || frm.doc.coa_quality_test_parameter.length === 0) {
        frappe.msgprint(__('No parameters to validate'));
        return;
    }
    
    var parameters = frm.doc.coa_quality_test_parameter;
    var validation_results = {
        total: parameters.length,
        passed: 0,
        failed: 0,
        pending: 0,
        skipped: 0,
        issues: []
    };
    
    parameters.forEach(function(param, index) {
        // Skip title rows
        if (is_title_row(param)) {
            validation_results.skipped++;
            param.result_text = '';
            param.result_status = 'N/A';
            return;
        }
        
        var result = validate_parameter_comprehensive(param, index + 1);
        
        if (result.status === 'PASS') {
            validation_results.passed++;
            param.result_text = 'PASS';
            param.result_status = 'Compliant';
        } else if (result.status === 'FAIL') {
            validation_results.failed++;
            param.result_text = 'FAIL';
            param.result_status = 'Non-Compliant';
            validation_results.issues.push(result.message);
        } else {
            validation_results.pending++;
            param.result_text = 'PENDING';
            param.result_status = 'Pending';
        }
    });
    
    // Update document validation status
    update_document_validation_status(frm, validation_results);
    
    // Refresh the form
    frm.refresh_field('coa_quality_test_parameter');
    
    // Show results
    show_validation_results(validation_results, frm);
}

// Comprehensive Parameter Validation
function validate_parameter_comprehensive(param, rowNum) {
    var result = {
        status: 'PENDING',
        message: ''
    };
    
    // Check if result value is provided
    if (!param.result_value || param.result_value.toString().trim() === '') {
        result.status = 'PENDING';
        result.message = 'No result value entered';
        return result;
    }
    
    var resultValue = param.result_value.toString().trim();
    var resultNum = parseFloat(resultValue);
    var acceptanceCriteria = param.value || '';
    var acceptanceUpper = acceptanceCriteria.toUpperCase();
    
    // Handle NEGATIVE criteria
    if (acceptanceUpper.includes('NEGATIVE')) {
        var resultUpper = resultValue.toUpperCase();
        if (resultUpper === 'NEGATIVE' || resultUpper === 'NEG' || resultUpper === 'NONE' || resultValue === '0') {
            result.status = 'PASS';
            result.message = 'Negative result as required';
        } else {
            result.status = 'FAIL';
            result.message = 'Row ' + rowNum + ': Expected negative result but got "' + resultValue + '"';
        }
        return result;
    }
    
    // Handle NOT DETECTABLE criteria
    if (acceptanceUpper.includes('NOT DETECTABLE') || acceptanceUpper.includes('NOT DETECTED') || acceptanceUpper.includes('ND')) {
        var lodValue = extract_lod_value(acceptanceCriteria);
        
        // Check numeric result below LOD
        if (!isNaN(resultNum)) {
            if (resultNum < lodValue) {
                result.status = 'PASS';
                result.message = 'Value below detection limit';
            } else {
                result.status = 'FAIL';
                result.message = 'Row ' + rowNum + ': Value "' + resultValue + '" should be below LOD of ' + lodValue;
            }
        } 
        // Check text-based results
        else if (resultValue.toUpperCase().includes('NOT DETECT') || resultValue.toUpperCase().includes('ND') || resultValue.includes('<')) {
            result.status = 'PASS';
            result.message = 'Not detectable as required';
        } else {
            result.status = 'FAIL';
            result.message = 'Row ' + rowNum + ': Expected not detectable result';
        }
        return result;
    }
    
    // Numeric validation
    if (!isNaN(resultNum)) {
        var minVal = param.min_value ? parseFloat(param.min_value) : null;
        var maxVal = param.max_value ? parseFloat(param.max_value) : null;
        
        var valid = true;
        if (minVal !== null && resultNum < minVal) {
            valid = false;
            result.message = 'Below minimum ' + minVal;
        }
        if (maxVal !== null && resultNum > maxVal) {
            valid = false;
            result.message = 'Above maximum ' + maxVal;
        }
        
        if (valid) {
            result.status = 'PASS';
            result.message = 'Within acceptable range';
        } else {
            result.status = 'FAIL';
            result.message = 'Row ' + rowNum + ': ' + result.message;
        }
    } else {
        // Text validation
        if (acceptanceCriteria && resultValue.toLowerCase() === acceptanceCriteria.toLowerCase()) {
            result.status = 'PASS';
            result.message = 'Matches acceptance criteria';
        } else if (!acceptanceCriteria) {
            result.status = 'PASS';
            result.message = 'No specific criteria to match';
        } else {
            result.status = 'FAIL';
            result.message = 'Row ' + rowNum + ': Doesn\'t match acceptance criteria';
        }
    }
    
    return result;
}

// LOD Value Extraction
function extract_lod_value(criteria) {
    var lodValue = 0;
    var patterns = [
        /LOD\s*([0-9.]+)/i,
        /LIMIT\s*OF\s*DETECTION\s*([0-9.]+)/i,
        /<*\s*([0-9.]+)/,
        /LESS\s*THAN\s*([0-9.]+)/i
    ];
    
    for (var i = 0; i < patterns.length; i++) {
        var match = criteria.match(patterns[i]);
        if (match && match[1]) {
            lodValue = parseFloat(match[1]);
            break;
        }
    }
    
    // Fallback: extract any number
    if (lodValue === 0) {
        var numberMatch = criteria.match(/([0-9.]+)/);
        if (numberMatch && numberMatch[1]) {
            lodValue = parseFloat(numberMatch[1]);
        }
    }
    
    return lodValue;
}

// Title Row Detection
function is_title_row(param) {
    if (!param) return false;
    
    // Check parameter name for title indicators
    if (param.parameter) {
        var paramLower = param.parameter.toLowerCase();
        if (paramLower.includes('title') || 
            paramLower.includes('header') || 
            paramLower.includes('section') ||
            paramLower === 'organoleptic' ||
            paramLower === 'physicochemical' ||
            paramLower === 'microbiological' ||
            paramLower.includes('---') ||
            paramLower.includes('***')) {
            return true;
        }
    }
    
    // Check if it has no validation criteria
    var hasMinMax = (param.min_value !== null && param.min_value !== undefined && param.min_value !== '') ||
                    (param.max_value !== null && param.max_value !== undefined && param.max_value !== '');
    var hasValue = param.value && param.value.trim() !== '';
    
    return !hasMinMax && !hasValue;
}

// Update Document Validation Status
function update_document_validation_status(frm, results) {
    var validation_status = 'Non-Compliant';
    var overall_status = 'FAIL';
    
    if (results.failed === 0 && results.passed > 0) {
        validation_status = 'Compliant';
        overall_status = 'PASS';
    } else if (results.pending > 0 && results.failed === 0) {
        validation_status = 'Pending Review';
        overall_status = 'PENDING';
    } else if (results.passed === 0 && results.failed === 0 && results.pending === 0) {
        validation_status = 'Not Started';
        overall_status = 'PENDING';
    }
    
    // Update the fields
    frm.set_value('validation_status', validation_status);
    frm.set_value('overall_compliance_status', overall_status);
    
    // Save the document
    frm.save().then(function() {
        console.log('Validation status updated to:', validation_status);
        
        // Refresh form to show/hide submit button
        if (validation_status === 'Compliant') {
            setTimeout(function() {
                frm.refresh();
            }, 1000);
        }
    });
}

// Show Validation Results
function show_validation_results(results, frm) {
    var message = '<div style="margin: 10px 0;">' +
        '<h4>📊 Compliance Validation Results</h4>' +
        '<p><strong>Total Parameters:</strong> ' + results.total + '</p>' +
        '<p><strong>✅ PASS:</strong> <span style="color: green;">' + results.passed + '</span></p>' +
        '<p><strong>❌ FAIL:</strong> <span style="color: red;">' + results.failed + '</span></p>' +
        '<p><strong>⏳ PENDING:</strong> <span style="color: orange;">' + results.pending + '</span></p>' +
        '<p><strong>📋 SKIPPED:</strong> <span style="color: blue;">' + results.skipped + '</span></p>' +
        '</div>';
    
    if (results.issues.length > 0) {
        message += '<div style="margin: 10px 0;"><h5>🔍 Validation Issues:</h5><ul style="max-height: 200px; overflow-y: auto;">';
        results.issues.forEach(function(issue) {
            message += '<li style="color: red;">' + issue + '</li>';
        });
        message += '</ul></div>';
    }
    
    if (results.failed === 0 && results.passed > 0) {
        message += '<div style="margin: 10px 0; padding: 10px; background-color: #d4edda; border-radius: 5px; border: 1px solid #c3e6cb;">' +
                   '<h5 style="color: #155724; margin: 0;">✅ All parameters are compliant!</h5>' +
                   '<p style="margin: 5px 0 0 0; color: #155724;">The document is ready for submission.</p>' +
                   '</div>';
    }
    
    frappe.msgprint({
        title: __('Compliance Validation'),
        message: message,
        indicator: results.failed === 0 ? 'green' : 'red'
    });
}

// Submit COA Document
function submit_coa_document(frm) {
    if (frm.doc.validation_status !== 'Compliant') {
        frappe.msgprint({
            title: __('Cannot Submit'),
            message: __('Document must be compliant before submission'),
            indicator: 'red'
        });
        return;
    }
    
    frappe.confirm(
        __('Are you sure you want to submit this COA? This will start the approval workflow.'),
        function() {
            // Show loading indicator
            frappe.show_alert({ message: __('Submitting COA...'), indicator: 'blue' });
            
            // Submit the document
            frm.savesubmit();
        },
        function() {
            console.log('COA submission cancelled');
        }
    );
}

// Utility Functions
function debug_current_values(frm) {
    console.log('=== COA AMB DEBUG INFO ===');
    console.log('Document:', frm.doc.name);
    console.log('Validation Status:', frm.doc.validation_status);
    console.log('Compliance Status:', frm.doc.overall_compliance_status);
    console.log('Docstatus:', frm.doc.docstatus);
    
    if (frm.doc.coa_quality_test_parameter) {
        console.log('Parameters:', frm.doc.coa_quality_test_parameter.length);
        frm.doc.coa_quality_test_parameter.forEach(function(param, index) {
            console.log('Param ' + (index + 1) + ':', {
                parameter: param.parameter,
                result_value: param.result_value,
                min_value: param.min_value,
                max_value: param.max_value,
                value: param.value,
                result_text: param.result_text,
                result_status: param.result_status
            });
        });
    }
    
    frappe.msgprint({
        title: __('Debug Complete'),
        message: __('Check browser console for detailed information'),
        indicator: 'blue'
    });
}

function clear_parameters_with_confirmation(frm) {
    if (!frm.doc.coa_quality_test_parameter || frm.doc.coa_quality_test_parameter.length === 0) {
        frappe.msgprint(__('No parameters to clear'));
        return;
    }
    
    frappe.confirm(
        __('Are you sure you want to clear all {0} parameters?', [frm.doc.coa_quality_test_parameter.length]),
        function() {
            frm.clear_table('coa_quality_test_parameter');
            frm.refresh_field('coa_quality_test_parameter');
            frappe.show_alert({
                message: __('All parameters cleared'),
                indicator: 'orange'
            });
        }
    );
}

// Enhanced Styling
function apply_enhanced_styles() {
    if (!document.getElementById('coa-amb-styles')) {
        var style = document.createElement('style');
        style.id = 'coa-amb-styles';
        style.textContent = 
            '.validation-pass { background-color: #d4edda !important; }' +
            '.validation-fail { background-color: #f8d7da !important; }' +
            '.validation-pending { background-color: #fff3cd !important; }';
        document.head.appendChild(style);
    }
}

console.log('COA AMB Enhanced Client Script loaded successfully');
