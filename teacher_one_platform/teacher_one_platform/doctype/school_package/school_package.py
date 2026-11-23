import frappe
from frappe import _
from frappe.model.document import Document


class SchoolPackage(Document):
    def validate(self):
        if self.max_seats and self.min_seats and self.min_seats > self.max_seats:
            frappe.throw(_("Minimum seats cannot exceed maximum seats"))
        if (self.seat_price or 0) < 0:
            frappe.throw(_("Seat price cannot be negative"))
        seen = set()
        for r in self.features:
            if r.feature_key in seen:
                frappe.throw(_("Row {0}: {1} is repeated").format(r.idx, r.feature_key))
            seen.add(r.feature_key)
