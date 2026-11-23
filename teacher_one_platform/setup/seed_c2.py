import frappe


def run():
    for n, c, pr in (("Pack 500", 500, 400), ("Pack 2000", 2000, 1400), ("Pack 5000", 5000, 3000)):
        if not frappe.db.exists("Credit Pack", n):
            frappe.get_doc({"doctype": "Credit Pack", "pack_name": n, "credits": c, "price": pr}).insert()
    frappe.db.commit()
    print("Packs:", frappe.get_all("Credit Pack", pluck="name"))
