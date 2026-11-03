"""Pure helpers for the Stock Entry `custom_sap_movement_type` Select (no frappe import, DB-free testable).

The Select stores "<code> (<label>)", e.g. "311 (BackFlush - Transfer for Kitting)" - the same
16 options rnd_warehouse_management ships. Code that compares the field to a bare code
("261") must extract the code first, otherwise it never matches a real value.
"""

# The codes offered by the Select (fixtures/custom_field.json). Guarded against drift by
# tests/test_sap_movement_code_validation.py.
KNOWN_CODES = frozenset([
	"101", "102", "103", "104", "105", "106", "107", "108", "109",
	"261", "281", "311", "313", "501", "545", "561",
])


def sap_code(value):
	"""'311 (BackFlush - Transfer for Kitting)' -> '311'; '311' -> '311'; None -> ''."""
	return (value or "").strip().split(" ", 1)[0]
