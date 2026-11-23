import json
import frappe

MOD = "Teacher One Platform"
D, R = "DocType", "Report"

SECTIONS = [
    ("Schools", [("Schools", D, "School"), ("Seat Requests", D, "School Seat Request")]),
    ("Plans and Billing", [("School Packages", D, "School Package"), ("Credit Packs", D, "Credit Pack"),
                           ("Payments", D, "School Payment")]),
    ("Credits", [("Credit Allocations", D, "Credit Allocation"),
                 ("Credit Overview", R, "Credit Overview", "School")]),
    ("Reports", [("Seat Usage", R, "Seat Usage", "School"), ("Credit Overview", R, "Credit Overview", "School")]),
]
QUICK = [("Schools", D, "School"), ("Seat Requests", D, "School Seat Request"), ("Payments", D, "School Payment"),
         ("Seat Usage", R, "Seat Usage", "School")]
CARDS = [("Active Schools", "School", [["School", "status", "=", "Active", False]]),
         ("Pending Seat Requests", "School Seat Request", [["School Seat Request", "status", "=", "Pending", False]]),
         ("Pending Payments", "School Payment", [["School Payment", "status", "=", "Pending", False]]),
         ("Provisioning Failed", "School", [["School", "provision_status", "=", "Failed", False]])]


def _card(label, dt, filters):
    for n in frappe.get_all("Number Card", {"label": label}, pluck="name"):
        frappe.delete_doc("Number Card", n, force=1, ignore_permissions=True)
    return frappe.get_doc({"doctype": "Number Card", "label": label, "type": "Document Type", "document_type": dt,
                           "function": "Count", "filters_json": json.dumps(filters), "is_public": 1,
                           "show_percentage_stats": 0, "module": MOD}).insert(ignore_permissions=True).name


def run():
    label = "Platform Home"
    if frappe.db.exists("Workspace", label):
        frappe.delete_doc("Workspace", label, force=1, ignore_permissions=True)
    names = [(_card(l, dt, f), l) for l, dt, f in CARDS]
    content = [{"id": "t", "type": "header", "data": {"text": '<span class="h3">Platform Overview</span>', "col": 12}}]
    for i, (n, l) in enumerate(names):
        content.append({"id": "n%d" % i, "type": "number_card", "data": {"number_card_name": n, "col": 3}})
    content.append({"id": "sp", "type": "spacer", "data": {"col": 12}})
    content.append({"id": "qh", "type": "header", "data": {"text": '<span class="h5">Quick Actions</span>', "col": 12}})
    shortcuts = []
    for i, x in enumerate(QUICK):
        row = {"label": x[0], "type": "Report" if x[1] == R else "DocType", "link_to": x[2]}
        row.update({"report_ref_doctype": x[3]} if x[1] == R else {"doc_view": "List"})
        shortcuts.append(row)
        content.append({"id": "q%d" % i, "type": "shortcut", "data": {"shortcut_name": x[0], "col": 3}})
    links, seen = [], set()
    for k, (sec, items) in enumerate(SECTIONS):
        links.append({"type": "Card Break", "label": sec})
        for it in items:
            links.append({"type": "Link", "label": it[0], "link_type": "Report" if it[1] == R else "DocType",
                          "link_to": it[2], "onboard": 0, "is_query_report": 1 if it[1] == R else 0,
                          **({"report_ref_doctype": it[3]} if it[1] == R else {})})
        content.append({"id": "c%d" % k, "type": "card", "data": {"card_name": sec, "col": 4}})
    frappe.get_doc({"doctype": "Workspace", "name": label, "label": label, "title": label, "public": 1,
                    "module": MOD, "sequence_id": 1, "content": json.dumps(content),
                    "roles": [{"role": "System Manager"}], "links": links, "shortcuts": shortcuts,
                    "number_cards": [{"number_card_name": n, "label": l} for n, l in names]}).insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()
    print("Platform Home ready")
