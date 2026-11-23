import frappe
from frappe import _
from frappe.model.document import Document


class CreditAllocation(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(_("A credit allocation cannot be edited."))
        if (self.credits or 0) <= 0:
            frappe.throw(_("Credits must be above 0"))
