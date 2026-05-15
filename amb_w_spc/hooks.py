app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "Your Company"
app_description = "AMB Statistical Process Control"
app_email = "your-email@example.com"
app_license = "MIT"
app_version = "1.0.0"

# Apps to include in the site
app_include = [
    "Core SPC",
    "SPC Quality Management",
    "System Integration",
    "Operator Management",
    "Sensor Management",
    "Shop Floor Control",
    "SFC Manufacturing",
    "FDA Compliance",
    "Plant Equipment",
    "Real Time Monitoring"
]

# Fixtures - auto-synced on bench migrate / Frappe Cloud deploy
fixtures = [
    {
        "dt": "Notification",
        "filters": [["module", "=", "SPC Quality Management"]]
    },
    {"doctype": "Client Script",       "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Server Script",       "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Workspace",          "filters": [["name", "like", "AMB%"]]},
    {"doctype": "Dashboard Chart",        "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Number Card",        "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Report",        "filters": [["module", "=", "SPC Quality Management"]]},
]

# After install hook
# after_install = "amb_w_spc.setup.after_install"

# ========================================
#  FRONTEND JS INJECTIONS
# ========================================

app_include_js = [
    "/assets/amb_w_spc/js/batch_widget.js",
    "/assets/amb_w_spc/js/sample_request_utils.js",
    "/assets/amb_w_spc/js/sample_request_buttons.js"
]

override_doctype_class = {
    "Batch AMB": "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.BatchAMB",
    # Phase 1A Step 2A — give QIP Group NestedSet tree semantics. Parent pointer is the existing
    # Custom Field `custom_parameter_group_child`. Companion patch:
    # amb_w_spc.patches.v15.setup_qip_group_tree_extension.
    "Quality Inspection Parameter Group": "amb_w_spc.overrides.quality_inspection_parameter_group.QualityInspectionParameterGroup",
    # Phase 1A.5 — TDS Product Specification moved to amb_w_tds (see amb_w_tds/hooks.py doc_events).
    # Even if it were here, override_doctype_class CANNOT work for TDS Product Specification because
    # it has `custom=1`, and Frappe's `import_controller` (frappe/model/base_document.py) returns
    # Document directly for custom=1 without consulting override_doctype_class.
    # same pattern amb_w_spc already uses for Batch AMB (also custom=1).
}

override_doctype_dashboards = {
    "Batch AMB": "amb_w_spc.utils.batch_amb_dashboard.get_data",
}

doc_events = {
    # ---- Batch AMB: Golden number auto-generation via amb_w_spc controller
    "Batch AMB": {
        "validate": [
            "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.batch_amb_validate",
        ],
        "before_save": [
            "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.batch_amb_before_save",
        ],
    },
    # Phase 1A Step 2B doc_events for TDS Product Specification relocated to amb_w_tds/hooks.py
    # during Phase 1A.5 (TDS family consolidation under amb_w_tds; see /tmp/amb_w_spc_hooks.py.pre-phase1a5.* backup).
    # Phase 1B-1 Pattern A2 (ADR-007) — wire MiniMax Agent's validators on the 2 Phase 1B-scope
    # DocTypes. The other 14 validators in core_spc/spc_server_validations.py are deferred to
    # Phase 2 (#21) per ADR-004 amendment 2026-05-14T15:30Z + basket task #107.
    "SPC Parameter Master": {
        "validate": [
            "amb_w_spc.core_spc.spc_server_validations.validate_spc_parameter_master",
        ],
    },
    "SPC Specification": {
        "validate": [
            "amb_w_spc.core_spc.spc_server_validations.validate_spc_specification",
        ],
    },
}

# Whitelist methods for dashboard
#__version__ = "5.2.0"

# Additional dashboard configuration
website_route_rules = [
    {"from_route": "/batch-dashboard/<path:path>", "to_route": "batch_dashboard"}
]
