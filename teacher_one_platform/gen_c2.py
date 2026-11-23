from gen_lib import *

MOD = "Teacher One Platform"
SM = [P("System Manager", **FULL)]

make(MOD, "Credit Pack", [
    F("pack_name", "Pack Name", reqd=1, unique=1, in_list_view=1),
    F("credits", "Credits", "Int", reqd=1, in_list_view=1),
    F("price", "Price", "Currency", reqd=1, in_list_view=1),
    F("enabled", "Enabled", "Check", default="1"),
], autoname="field:pack_name", perms=SM, code='''
def validate(self):
    if (self.credits or 0) <= 0 or (self.price or 0) < 0:
        frappe.throw(_("Credits must be above 0 and price cannot be negative"))
''')

make(MOD, "School Payment", [
    F("school", "School", "Link", "School", 1, in_list_view=1),
    F("kind", "Kind", "Select", "Credit Pack\nRenewal", reqd=1, in_list_view=1),
    F("credit_pack", "Credit Pack", "Link", "Credit Pack", depends_on="eval:doc.kind=='Credit Pack'",
      mandatory_depends_on="eval:doc.kind=='Credit Pack'"),
    F("credits", "Credits", "Int", read_only=1),
    F("renewal_months", "Renewal Months", "Int", depends_on="eval:doc.kind=='Renewal'",
      mandatory_depends_on="eval:doc.kind=='Renewal'"),
    F("amount", "Amount Received", "Currency", reqd=1, in_list_view=1),
    F("reference", "Payment Reference (UTR / cheque no.)", reqd=1),
    F("status", "Status", "Select", "Pending\nConfirmed", default="Pending", read_only=1, in_list_view=1),
    F("result", "Result", "Small Text", read_only=1),
], autoname="format:PAY-{#####}", perms=SM, code='''
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
''')
