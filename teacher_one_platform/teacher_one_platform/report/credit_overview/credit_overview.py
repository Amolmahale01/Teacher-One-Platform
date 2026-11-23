import frappe
from frappe import _


def execute(filters=None):
    cols = [
        {"label": _("School"), "fieldname": "school", "fieldtype": "Link", "options": "School", "width": 180},
        {"label": _("Credits Allocated (total)"), "fieldname": "allocated", "fieldtype": "Int", "width": 160},
        {"label": _("Balance at School"), "fieldname": "balance", "fieldtype": "Int", "width": 140},
        {"label": _("Used (approx)"), "fieldname": "used", "fieldtype": "Int", "width": 120},
        {"label": _("Payments Confirmed"), "fieldname": "paid", "fieldtype": "Currency", "width": 140},
        {"label": _("Updated"), "fieldname": "synced", "fieldtype": "Datetime", "width": 150},
    ]
    paid = dict(frappe.db.sql("select school, sum(amount) from `tabSchool Payment` where status='Confirmed' group by school") or [])
    data = []
    for s in frappe.get_all("School", fields=["name", "credits_allocated", "credits_balance", "usage_synced"]):
        a, b = s.credits_allocated or 0, s.credits_balance or 0
        data.append({"school": s.name, "allocated": a, "balance": b, "used": max(a - b, 0),
                     "paid": paid.get(s.name, 0), "synced": s.usage_synced})
    return cols, data
