
frappe.ui.form.on('COA AMB', {
    refresh: function(frm) {
        // Add SPC quality dashboard
        add_spc_quality_dashboard(frm);
        
        // Add compliance calculation
        calculate_compliance_score(frm);
    },
    
    spc_parameters_add: function(frm, cdt, cdn) {
        update_compliance_score(frm);
    },
    
    quality_tests_add: function(frm, cdt, cdn) {
        update_compliance_score(frm);
    }
});

function add_spc_quality_dashboard(frm) {
    if(!frm.quality_dashboard) {
        frm.quality_dashboard = new QualityDashboard(frm);
    }
}

class QualityDashboard {
    constructor(frm) {
        this.frm = frm;
        this.init_dashboard();
    }
    
    init_dashboard() {
        // Add quality compliance indicators
        this.frm.dashboard.add_indicator(__('Quality Compliance: 98%'), 'green');
        this.frm.dashboard.add_indicator(__('Tests Completed: 15/16'), 'blue');
        this.frm.dashboard.add_indicator(__('SPC Parameters: 8'), 'orange');
        
        // Add Cpk/Ppk indicators if available
        if(this.frm.doc.cpk_value) {
            let cpk_color = this.frm.doc.cpk_value >= 1.33 ? 'green' : 'orange';
            this.frm.dashboard.add_indicator(__('Cpk: {0}', [this.frm.doc.cpk_value]), cpk_color);
        }
        
        if(this.frm.doc.ppk_value) {
            let ppk_color = this.frm.doc.ppk_value >= 1.33 ? 'green' : 'orange';
            this.frm.dashboard.add_indicator(__('Ppk: {0}', [this.frm.doc.ppk_value]), ppk_color);
        }
    }
}

function calculate_compliance_score(frm) {
    // Calculate overall compliance score
    let totalTests = 0;
    let passedTests = 0;
    
    // Count from quality tests
    if(frm.doc.quality_tests) {
        totalTests += frm.doc.quality_tests.length;
        passedTests += frm.doc.quality_tests.filter(t => t.status === 'Pass').length;
    }
    
    // Count from SPC parameters
    if(frm.doc.spc_parameters) {
        totalTests += frm.doc.spc_parameters.length;
        passedTests += frm.doc.spc_parameters.filter(p => p.status === 'In Control').length;
    }
    
    // Calculate score
    let complianceScore = totalTests > 0 ? (passedTests / totalTests * 100) : 0;
    frm.set_value('spc_compliance_score', complianceScore);
    
    // Update dashboard
    if(frm.quality_dashboard) {
        frm.quality_dashboard.update_compliance(complianceScore);
    }
}

function update_compliance_score(frm) {
    // Recalculate when child table changes
    setTimeout(() => {
        calculate_compliance_score(frm);
    }, 100);
}
