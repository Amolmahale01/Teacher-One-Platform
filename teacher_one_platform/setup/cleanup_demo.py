import frappe

# Sirf generated data. School Package / Credit Pack (configuration) nahi chhoone wale.
GENERATED = ["School Payment", "School Seat Request", "Credit Allocation", "School"]   # School sabse last


def run():
    for dt in GENERATED:
        names = frappe.get_all(dt, pluck="name")
        for n in names:
            frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
        print("deleted", len(names), dt)
    frappe.db.sql("delete from `tabSeries` where name = 'SCH-'")      # naya school SCH-00001 se shuru
    frappe.db.commit()
    print("kept: School Package", frappe.db.count("School Package"), "| Credit Pack", frappe.db.count("Credit Pack"))
