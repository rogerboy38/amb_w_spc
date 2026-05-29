import frappe
from frappe.model.document import Document


class Substrate(Document):
    """Substrate — canonical material codes for Path Y picker filtering.

    The 5 records (LQD, LQDC, LQDF, PWD, PWDF) are shipped as a fixture and
    function as a closed enumeration. Item.substrate Link points here; the
    picker (phase_1c_tab_v2.js) reads it to filter the QIP catalog by
    applicable_substrates. Task #70 (2026-05-29).
    """
    pass
