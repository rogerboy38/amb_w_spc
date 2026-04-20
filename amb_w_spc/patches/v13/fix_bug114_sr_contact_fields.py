# Add at the very beginning of the file
import frappe
from frappe import _


def execute():
    """BUG-114C: Backfill empty contact fields on existing Sample Request AMB docs."""
    srs = frappe.get_all(
        "Sample Request AMB",
        filters={"party_type": ("in", ["Lead", "Customer", "Prospect"])},
        fields=["name", "party_type", "party", "email", "phone", "address", "city", "state", "country"]
    )

    fixed = 0
    for sr in srs:
        if sr.email and sr.phone and sr.address and sr.city:
            continue
        if not sr.party:
            continue

        source_dt = sr.party_type
        if not frappe.db.exists(source_dt, sr.party):
            continue

        doc = frappe.get_doc(source_dt, sr.party)
        updates = {}

        # Email + phone from source flat fields
        if not sr.email:
            updates["email"] = getattr(doc, "email_id", "") or getattr(doc, "email", "") or ""
        if not sr.phone:
            updates["phone"] = (getattr(doc, "mobile_no", "") or
                                getattr(doc, "phone", "") or "")

        # City/state/country from source
        if not sr.city:
            updates["city"] = getattr(doc, "city", "") or ""
        if not sr.state:
            updates["state"] = getattr(doc, "state", "") or ""
        if not sr.country:
            updates["country"] = getattr(doc, "country", "") or ""

        # Address from linked Address doc
        if not sr.address:
            addr_list = frappe.get_all(
                "Dynamic Link",
                filters={"link_doctype": source_dt, "link_name": sr.party, "parenttype": "Address"},
                pluck="parent"
            )
            if addr_list:
                try:
                    a = frappe.get_doc("Address", addr_list[0])
                    parts = [p for p in (a.address_line1, a.address_line2) if p]
                    if parts:
                        updates["address"] = ", ".join(parts)
                    if not updates.get("city") and a.city:
                        updates["city"] = a.city
                    if not updates.get("state") and a.state:
                        updates["state"] = a.state
                    if not updates.get("country") and a.country:
                        updates["country"] = a.country
                except Exception:
                    pass

        # Contact fallback for email/phone
        if (not updates.get("email")) or (not updates.get("phone")):
            contact_list = frappe.get_all(
                "Dynamic Link",
                filters={"link_doctype": source_dt, "link_name": sr.party, "parenttype": "Contact"},
                pluck="parent"
            )
            if contact_list:
                try:
                    c = frappe.get_doc("Contact", contact_list[0])
                    if not updates.get("email"):
                        updates["email"] = c.email_id or ""
                    if not updates.get("phone"):
                        updates["phone"] = c.mobile_no or c.phone or ""
                except Exception:
                    pass

        # Filter out empty updates and apply
        updates = {k: v for k, v in updates.items() if v}
        if updates:
            frappe.db.set_value("Sample Request AMB", sr.name, updates)
            fixed += 1

    frappe.db.commit()
    print(f"BUG-114C: repaired {fixed} Sample Request AMB docs")
