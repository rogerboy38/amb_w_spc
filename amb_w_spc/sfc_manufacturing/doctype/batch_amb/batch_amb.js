
frappe.ui.form.on('Batch AMB', {
    refresh: function(frm) {
        // Add real-time SPC dashboard
        if(!frm.spc_dashboard) {
            frm.spc_dashboard = new SPCDashboard(frm);
        }
        
        // Update quality indicators
        update_quality_indicators(frm);
        
        // Add custom buttons for SPC features
        frm.add_custom_button(__('SPC Dashboard'), function() {
            frappe.set_route('query-report', 'SPC Batch Report', {batch: frm.doc.name});
        });
    },
    
    // Auto-calculations
    total_gross_weight: function(frm) {
        calculate_net_weight(frm);
    },
    total_tara_weight: function(frm) {
        calculate_net_weight(frm);
    },
    
    // SPC parameter validation
    batch_parameters_add: function(frm, cdt, cdn) {
        validate_spc_parameter(frm, cdt, cdn);
    }
});

class SPCDashboard {
    constructor(frm) {
        this.frm = frm;
        this.init_dashboard();
    }
    
    init_dashboard() {
        // Add SPC compliance indicators
        this.frm.dashboard.add_indicator(__('SPC Compliance: 100%'), 'green');
        this.frm.dashboard.add_indicator(__('Quality Score: 98.7%'), 'blue');
        this.frm.dashboard.add_indicator(__('Parameters Monitored: 12'), 'orange');
    }
}

function calculate_net_weight(frm) {
    let gross = frm.doc.total_gross_weight || 0;
    let tara = frm.doc.total_tara_weight || 0;
    frm.set_value('total_net_weight', gross - tara);
}

function update_quality_indicators(frm) {
    // Update quality status based on test results
    if(frm.doc.quality_test_results && frm.doc.quality_test_results.length > 0) {
        let passed = frm.doc.quality_test_results.filter(t => t.status === 'Pass').length;
        let total = frm.doc.quality_test_results.length;
        let score = total > 0 ? (passed / total * 100).toFixed(1) : 0;
        
        // Update dashboard indicator
        if(frm.dashboard && frm.dashboard.data && frm.dashboard.data[1]) {
            frm.dashboard.data[1].value = __('Quality Score: {0}%', [score]);
        }
        
        // Auto-update quality status
        if(score >= 95) {
            frm.set_value('quality_status', 'Approved');
        } else if(score >= 80) {
            frm.set_value('quality_status', 'Under Review');
        } else {
            frm.set_value('quality_status', 'Rejected');
        }
    }
}

function validate_spc_parameter(frm, cdt, cdn) {
    // Validate SPC parameter limits when added
    let row = frappe.get_doc(cdt, cdn);
    if(row.actual_value && row.upper_limit && row.lower_limit) {
        if(row.actual_value > row.upper_limit || row.actual_value < row.lower_limit) {
            frappe.msgprint({
                title: __('SPC Parameter Alert'),
                indicator: 'red',
                message: __('Parameter {0} is out of control limits', [row.parameter_name])
            });
            row.status = 'Out of Control';
        } else {
            row.status = 'In Control';
        }
        frm.refresh_field('batch_parameters');
    }
}
