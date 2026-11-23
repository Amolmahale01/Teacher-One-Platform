import frappe
from frappe import _


def execute(filters=None):
    columns = [
        {"label": _("School"), "fieldname": "school", "fieldtype": "Link", "options": "School", "width": 180},
        {"label": _("Package"), "fieldname": "package", "fieldtype": "Data", "width": 100},
        {"label": _("Seats Purchased"), "fieldname": "seats", "fieldtype": "Int", "width": 120},
        {"label": _("Seats Used"), "fieldname": "used", "fieldtype": "Int", "width": 100},
        {"label": _("Seats Free"), "fieldname": "free", "fieldtype": "Int", "width": 100},
        {"label": _("Active Students"), "fieldname": "students", "fieldtype": "Int", "width": 120},
        {"label": _("Student Cap (0 = unlimited)"), "fieldname": "cap", "fieldtype": "Int", "width": 160},
        {"label": _("Updated"), "fieldname": "synced", "fieldtype": "Datetime", "width": 150},
    ]
    data = []
    for s in frappe.get_all("School", fields=["name", "school_name", "package", "seats", "seats_used",
                                              "students_active", "usage_synced"], order_by="school_name asc"):
        cap = frappe.db.get_value("School Package", s.package, "student_cap") or 0
        data.append({"school": s.name, "package": s.package, "seats": s.seats, "used": s.seats_used or 0,
                     "free": (s.seats or 0) - (s.seats_used or 0), "students": s.students_active or 0,
                     "cap": cap, "synced": s.usage_synced})
    return columns, data
