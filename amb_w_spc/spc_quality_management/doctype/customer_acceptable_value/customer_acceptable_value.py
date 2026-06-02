"""Customer Acceptable Value — controller with Path A SC2 validations.

Per Hugh's directive (2026-05-24, Path A SC2):
  - value_type='Choice'        → value_text reqd
  - value_type='Numeric Range' → value_min < value_max, both reqd
  - value_type='Both'          → all four required
  - effective_to > effective_from (if both set)
  - On submit: Draft → Approved auto-flip; stamp approved_by + approved_date
  - No duplicate (parameter, customer, method, status=Approved, is_active=1) at same time

Permissions: Quality Manager full, Quality User RWC, Inspector User R, Sales User R,
Customer R via if_owner. Lineage via amended_from + supersedes.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class CustomerAcceptableValue(Document):
    def validate(self):
        self._validate_value_fields()
        self._validate_effective_dates()
        self._validate_no_duplicate_approved()

    def before_submit(self):
        # Auto-flip Draft → Approved + stamp approver
        if self.status == "Draft":
            self.status = "Approved"
        if not self.approved_by:
            self.approved_by = frappe.session.user
        if not self.approved_date:
            self.approved_date = today()

    def _validate_value_fields(self):
        """value_type drives which fields are required."""
        vt = self.value_type
        if vt == "Choice":
            if not self.value_text:
                frappe.throw(_("Value Text is required when Value Type is 'Choice'"))
        elif vt == "Numeric Range":
            if self.value_min is None or self.value_max is None:
                frappe.throw(_("Both Value Min and Value Max are required when Value Type is 'Numeric Range'"))
            if self.value_min >= self.value_max:
                frappe.throw(_("Value Min must be less than Value Max"))
        elif vt == "Both":
            if not self.value_text:
                frappe.throw(_("Value Text is required when Value Type is 'Both'"))
            if self.value_min is None or self.value_max is None:
                frappe.throw(_("Both Value Min and Value Max are required when Value Type is 'Both'"))
            if self.value_min >= self.value_max:
                frappe.throw(_("Value Min must be less than Value Max"))

    def _validate_effective_dates(self):
        """effective_to must be after effective_from if both set."""
        if self.effective_from and self.effective_to:
            if getdate(self.effective_to) <= getdate(self.effective_from):
                frappe.throw(_("Effective To must be after Effective From"))

    def _validate_no_duplicate_approved(self):
        """No two Approved+active CAVs for same (parameter, customer, method) at the same time."""
        if self.status != "Approved" or not self.is_active:
            return
        # Find any other Approved + active record for the same triplet
        filters = {
            "parameter": self.parameter,
            "customer": self.customer,
            "status": "Approved",
            "is_active": 1,
            "name": ["!=", self.name],
        }
        if self.method:
            filters["method"] = self.method
        else:
            filters["method"] = ["is", "not set"]

        # Time-window overlap check (current record's effective window must not overlap)
        existing = frappe.get_all(
            "Customer Acceptable Value",
            filters=filters,
            fields=["name", "effective_from", "effective_to"],
        )
        for other in existing:
            if self._date_windows_overlap(other.effective_from, other.effective_to):
                frappe.throw(
                    _("Duplicate Approved Customer Acceptable Value exists for this parameter+customer+method+time-window: {0}").format(
                        frappe.bold(other.name)
                    )
                )

    def _date_windows_overlap(self, other_from, other_to):
        """Return True if (self.effective_from, self.effective_to) overlaps (other_from, other_to).
        Open-ended (None) = infinite in that direction."""
        my_from = getdate(self.effective_from) if self.effective_from else None
        my_to = getdate(self.effective_to) if self.effective_to else None
        their_from = getdate(other_from) if other_from else None
        their_to = getdate(other_to) if other_to else None

        # Two ranges overlap if: NOT (my_to < their_from OR my_from > their_to)
        if my_to and their_from and my_to < their_from:
            return False
        if my_from and their_to and my_from > their_to:
            return False
        return True
