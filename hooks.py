from . import __version__ as version

app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB-Wellness"
app_description = "Advanced Manufacturing, Warehouse Management & Statistical Process Control for ERPNext"
app_email = "fcrm@amb-wellness.com"
app_license = "mit"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/amb_w_spc/css/amb_w_spc.css"
# app_include_js = "/assets/amb_w_spc/js/amb_w_spc.js"

# include js, css files in header of web template
# web_include_css = "/assets/amb_w_spc/css/amb_w_spc.css"
# web_include_js = "/assets/amb_w_spc/js/amb_w_spc.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "amb_w_spc/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#  "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#  "methods": "amb_w_spc.utils.jinja_methods",
#  "filters": "amb_w_spc.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "amb_w_spc.install.before_install"
# after_install = "amb_w_spc.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "amb_w_spc.uninstall.before_uninstall"
# after_uninstall = "amb_w_spc.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "amb_w_spc.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#  "Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#  "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#  "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#  "*": {
#   "on_update": "method",
#   "on_cancel": "method",
#   "on_trash": "method"
#  }
# }

# Scheduled Tasks
# ---------------

# Comment out scheduler references until we create the actual functions
# scheduler_events = {
#  "all": [
#   "amb_w_spc.tasks.all"
#  ],
#  "daily": [
#   "amb_w_spc.tasks.daily"
#  ],
#  "hourly": [
#   "amb_w_spc.tasks.hourly"
#  ],
#  "weekly": [
#   "amb_w_spc.tasks.weekly"
#  ],
#  "monthly": [
#   "amb_w_spc.tasks.monthly"
#  ],
# }

# Testing
# -------

# before_tests = "amb_w_spc.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#  "frappe.desk.doctype.event.event.get_events": "amb_w_spc.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#  "Task": "amb_w_spc.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_when_deleting = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["amb_w_spc.utils.before_request"]
# after_request = ["amb_w_spc.utils.after_request"]

# Job Events
# ----------
# before_job = ["amb_w_spc.utils.before_job"]
# after_job = ["amb_w_spc.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#  {
#   "doctype": "{doctype_1}",
#   "filter_by": "{filter_by}",
#   "redact_fields": ["{field_1}", "{field_2}"],
#   "partial": 1,
#  },
#  {
#   "doctype": "{doctype_2}",
#   "filter_by": "{filter_by}",
#   "partial": 1,
#  },
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#  "amb_w_spc.auth.validate"
# ]

# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended for localized DocTypes
# translated_doctypes = []

# Workspaces
# ----------

# workspace pages
workspace_pages = [
    {
        "page": "workspaces/manufacturing.json",
        "label": "Manufacturing",
        "category": "Modules",
        "icon": "chart-line",
        "restrict_to_domain": [],
        "is_standard": 0
    }
]

# Fixtures
# --------

fixtures = [
    {
        "dt": "Workspace",
        "filters": [
            ["module", "=", "AMB W SPC"]
        ]
    }
]
