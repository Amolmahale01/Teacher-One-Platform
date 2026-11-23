import frappe
from frappe import _
from frappe.model.document import Document


class SchoolPayment(Document):
    def validate(self):
        before = self.get_doc_before_save()
        if before and before.status == "Confirmed":
            frappe.throw(_("A confirmed payment cannot be edited."))
        if self.kind == "Credit Pack":
            pack = frappe.db.get_value("Credit Pack", self.credit_pack, ["credits", "enabled"], as_dict=True)
            if not pack or not pack.enabled:
                frappe.throw(_("Choose an enabled credit pack"))
            self.credits = pack.credits
            self.renewal_months = 0
        else:
            self.credit_pack, self.credits = None, 0
            if (self.renewal_months or 0) < 1:
                frappe.throw(_("Renewal months must be at least 1"))
        if (self.amount or 0) <= 0:
            frappe.throw(_("Amount must be above 0"))
