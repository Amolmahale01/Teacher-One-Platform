import frappe
from frappe import _
from frappe.model.document import Document


class CreditPack(Document):
    def validate(self):
        if (self.credits or 0) <= 0 or (self.price or 0) < 0:
            frappe.throw(_("Credits must be above 0 and price cannot be negative"))
