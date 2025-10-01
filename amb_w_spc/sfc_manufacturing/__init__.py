__version__ = "2.0.0"

from frappe import _

def get_data():
	return [
		{
			"module_name": "sfc_manufacturing",  # MUST match directory name
			"color": "blue",
			"icon": "octicon octicon-circuit-board",
			"type": "module",
			"label": _("SFC Manufacturing")
		}
	]
