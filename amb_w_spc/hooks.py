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

# ========================================
#  FIXTURES (L153 fixtures-discipline rollout 2026-05-20)
# ========================================
# Per cowork-ops 2026-05-20T21:44Z directive (post L153 ratification):
# Filter Custom Field / Property Setter / Client Script / Server Script by
# DocType (dt / doc_type / reference_doctype) rather than module. amb_w_spc
# claims QC / Manufacturing / SPC / Stock / Warehouse / Work Order domain;
# amb_w_tds claims TDS / Sales / COA / BOM / Customer / CRM / Logistics.
#
# UOM: explicit name list per L152 ISO/SI convention — only AMB-QC-specific
# UOMs that the QIP custom_unit + IQI value system references.

_AMB_W_SPC_DOCTYPES = [
    # Owned by amb_w_spc (defined in this app)
    "Batch AMB", "Batch AMB Item", "Batch Output Product",
    "Batch Processing History", "Bot User Configuration",
    "Deviation CAPA Action", "Deviation Team Member", "Deviation Timeline",
    "Doctypes Relationships", "Integration Points",
    "Manufacturing Station", "Material Assessment Log",
    "Material Assessment Log Item", "MRP Material Requirement", "MRP Planning",
    "MRP Planning Item", "MRP Planning Material", "MRP Work Order",
    "Operator Management Settings", "PLC Integration", "PLC Parameter Mapping",
    "Purchase Receipt Integration", "Purchase Receipt Integration Item",
    "Quality Certificate Link", "Real Time Process Data",
    "Sales Order Fulfillment", "Sales Order Fulfillment Item",
    "Sensor Configuration", "Sensor Skill", "SFC Operator",
    "SFC Operator Attendance", "SFC Operator Skill", "SFC Transaction",
    "SPC Alert", "SPC Alert Escalation Notification",
    "SPC Alert New Notification", "SPC Alert Recipient", "SPC Audit Trail",
    "SPC Batch Deviation", "SPC Batch Parameter", "SPC Batch Record",
    "SPC Change Control", "SPC Control Chart", "SPC Corrective Action",
    "SPC Corrective Action Due Reminder Notification",
    "SPC Corrective Action Factor", "SPC Corrective Action Item",
    "SPC Corrective Action New Notification", "SPC Data Point", "SPC Deviation",
    "SPC Electronic Signature", "SPC Environment", "SPC Equipment",
    "SPC Parameter Control Limit", "SPC Parameter Master",
    "SPC Parameter Specification", "SPC Parameter Target Value",
    "SPC Process Capability", "SPC Process Capability Completed Notification",
    "SPC Process Capability Measurement", "SPC Quality Test", "SPC Raw Material",
    "SPC Report", "SPC Report Cpk Value", "SPC Report Generated Notification",
    "SPC Report Parameter", "SPC Report Recipient", "SPC Report Violation",
    "SPC Specification", "SPC Workstation", "Station Equipment",
    "Warehouse Pick Task", "Warehouse Pick Task Item", "Weight Event",
    "Work Order Routing", "Work Order Routing Operation",
    # ERPNext DocTypes amb_w_spc customizes (QC / Manufacturing / Stock)
    "Batch", "Item Barcode", "Item Quality Inspection Parameter",
    "Job Card", "Movement Type", "Quality Inspection",
    "Quality Inspection Parameter", "Quality Inspection Parameter Group",
    "Quality Inspection Template", "Serial and Batch Bundle", "Serial No",
    "Stock Entry", "Stock Entry Detail", "Stock Reconciliation",
    "Stock Reconciliation Item", "Warehouse", "Work Order", "Work Order Item",
    "Workstation",
]

# AMB-QC-specific UOMs per L152 ISO/SI convention. Standard ERPNext UOMs
# (Kg, Liter, Unit, etc.) are NOT listed — they ship with ERPNext core.
_AMB_W_SPC_UOMS = [
    "%",
    "ppm",
    "CFU/g",
    "CFU/mL",
    "mg/kg",
    "g/mL",
    "Brix grados",
    "Color (absorbance 400nm)",
    "Color Gardner",
]

# L153 §4.1 follow-on: Server Scripts with reference_doctype=NULL (scheduled /
# API / cron-driven) need explicit-name capture. Per triage 2026-05-20T23:30Z.
_AMB_W_SPC_NOREF_SERVER_SCRIPTS = [
    "Batch and Serial",                  # Batch + Serial manufacturing
    "get_running_batch_announcements",   # Batch announcements
    "Work Order List Show Drafts",       # Work Order list view
]

# Task #70 (2026-05-29) — Custom Fields on doctypes NOT in _AMB_W_SPC_DOCTYPES
# that amb_w_spc owns because the substrate-aware code paths live in SPC. Tight
# name-exception list UNIONed into the Custom Field fixture filter via
# or_filters; without this, export-fixtures would silently drop these CFs
# (their `dt` misses the doctype-list filter — same trap as L156).
#
# Item-substrate: dt=Item (owned by ERPNext / amb_w_tds; Item is in
# _AMB_W_TDS_DOCTYPES). Picker (phase_1c_tab_v2.js) reads frm.doc.item.substrate
# to filter parameters by Path Y. amb_w_tds's CF filter also catches this CF
# via `dt in _AMB_W_TDS_DOCTYPES` — accepted latent dual-capture per Task #67
# precedent (content identical, last-write-wins is idempotent).
_AMB_W_SPC_CF_EXCEPTIONS = [
    "Item-substrate",
]

# Task #9 (2026-05-30) — canonical QIPG tree roots for fixture filter.
# Mirrors the picker's source-of-truth at apps/amb_w_tds/amb_w_tds/public/js/
# phase_1c_tab_v2.js (SC5V2_COMMON_ROOT + SC5V2_L2_CATEGORIES.qipg). Used as
# `custom_parameter_group_child IN [...]` filter to capture Common Root + 7
# L2 categories + all their direct descendants (~411 records). EXCLUDES:
# the 4 ARCHIVED-2026-05 orphans, the 8 Products * legacy top-levels +
# their substrate-segmented residue (Physicochemical LQDC, Legacy STD
# LQDF/PWDF). Adjust this list if the picker's L2 constants change.
_AMB_W_SPC_CANONICAL_QIPG_PARENTS = [
    "Common Root",
    "Organoleptic", "Physicochemical", "Microbiological",
    "Pesticides", "Contaminant", "Other Analysis",
    "Aloe Vera Nutrients",
]

fixtures = [
    {"doctype": "Custom Field",
     "or_filters": [
         ["dt", "in", _AMB_W_SPC_DOCTYPES],
         ["name", "in", _AMB_W_SPC_CF_EXCEPTIONS],
     ]},
    # Task #70 — 5 canonical Substrate records (LQD/LQDC/LQDF/PWD/PWDF). No
    # filter needed; the doctype is a closed enumeration that always ships
    # whole. JSON-shipped at custom=0 alongside this fixture.
    {"doctype": "Substrate"},
    # Task #9 (2026-05-30) — canonical Quality Inspection Parameter Group
    # tree (Common Root + 7 L2 categories + ~403 direct descendants = ~411
    # records). Filter via or_filters: (name='Common Root') OR (parent IN
    # [Common Root, 7 L2 names]). Includes applicable_substrates Table
    # MultiSelect child rows (Parameter Group Substrate per Task #67),
    # which transport with each parent doc. Excludes 4 ARCHIVED-2026-05
    # orphans + 8 Products * legacy top-levels + 3 substrate-segmented
    # residue groups (Legacy STD LQDF/PWDF, Physicochemical LQDC).
    {"doctype": "Quality Inspection Parameter Group",
     "or_filters": [
         ["name", "=", "Common Root"],
         ["custom_parameter_group_child", "in", _AMB_W_SPC_CANONICAL_QIPG_PARENTS],
     ]},
    {"doctype": "Property Setter",  "filters": [["doc_type", "in", _AMB_W_SPC_DOCTYPES]]},
    {"doctype": "Client Script",    "filters": [["dt", "in", _AMB_W_SPC_DOCTYPES]]},
    # Server Script: UNION via or_filters only — see amb_w_tds hooks.py note.
    # filters+or_filters in same dict = AND-of-both (intersection); for UNION
    # we need both conditions inside or_filters as siblings.
    {
        "doctype": "Server Script",
        "or_filters": [
            ["reference_doctype", "in", _AMB_W_SPC_DOCTYPES],
            ["name", "in", _AMB_W_SPC_NOREF_SERVER_SCRIPTS],
        ],
    },
    {"doctype": "UOM",              "filters": [["name", "in", _AMB_W_SPC_UOMS]]},
    {"doctype": "Notification",     "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Workspace",        "filters": [["name", "like", "AMB%"]]},
    {"doctype": "Dashboard Chart",  "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Number Card",      "filters": [["module", "=", "SPC Quality Management"]]},
    {"doctype": "Report",           "filters": [["module", "=", "SPC Quality Management"]]},
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

# L187 (2026-05-31) — Post-fixture-sync QIPG NSM rebuild. Frappe migrate order is:
# 1. Patches → 2. sync_fixtures → 3. after_migrate. sync_fixtures of Task #9's
# 411-record QIPG canonical fixture repositions L2 boundaries (Physicochemical,
# etc.) but does NOT reposition non-fixture QIPGs created by patches (e.g.
# v14_3_10 STEP 1's `Physicochemical Diacetyl Rhein`). after_migrate hook runs
# rebuild_tree AFTER fixture-driven L2 repositioning so non-fixture QIPGs
# realign relative to the final L2 ranges. Idempotent; canary log if Diacetyl
# Rhein still not contained after rebuild. See L187 banked memory.
after_migrate = [
    "amb_w_spc.utils.tree_consistency.rebuild_qipg_tree",
]

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

# Bench CLI commands registration (Phase 1.2 admin commands by claude-ubuntuvm,
# authored 2026-05-12 per kickoff f1b2a8d4). See amb_w_spc/commands.py.
commands = ["amb_w_spc.commands"]
