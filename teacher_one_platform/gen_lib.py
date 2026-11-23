import json, os, re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
RW = dict(read=1, write=1, create=1, report=1, export=1, print=1, share=1, email=1)
FULL = dict(RW, delete=1)
RO = dict(read=1, report=1, print=1)

def scrub(s):
    return re.sub(r"[\s\-]+", "_", s.strip().lower())

def F(fieldname, label, fieldtype="Data", options=None, reqd=0, **kw):
    d = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "reqd": reqd}
    if options:
        d["options"] = options
    d.update(kw)
    return d

def P(role, **flags):
    return dict(role=role, **flags)

def make(module, name, fields, autoname=None, istable=0, code=None, imports="", tail="",
         title_field=None, single=0, submittable=0, perms=None):
    folder = os.path.join(BASE, scrub(module), "doctype", scrub(name))
    os.makedirs(folder, exist_ok=True)
    open(os.path.join(folder, "__init__.py"), "a").close()
    if perms is None:
        perms = [P("System Manager", **FULL), P("School Admin", **RW), P("School Teacher", **RO)]
    doc = {
        "doctype": "DocType", "name": name, "module": module, "owner": "Administrator",
        "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), "engine": "InnoDB",
        "istable": istable, "editable_grid": 1 if istable else 0,
        "track_changes": 0 if istable else 1, "sort_field": "modified", "sort_order": "DESC",
        "field_order": [f["fieldname"] for f in fields], "fields": fields,
        "permissions": [] if istable else perms,
    }
    if autoname: doc["autoname"] = autoname
    if title_field: doc["title_field"] = title_field
    if single: doc["issingle"] = 1
    if submittable: doc["is_submittable"] = 1
    with open(os.path.join(folder, scrub(name) + ".json"), "w") as fh:
        json.dump(doc, fh, indent=1)
    py = os.path.join(folder, scrub(name) + ".py")
    if not os.path.exists(py):
        body = (code or "pass").strip("\n")
        with open(py, "w") as fh:
            fh.write("import frappe\nfrom frappe import _\nfrom frappe.model.document import Document\n")
            if imports:
                fh.write(imports.strip("\n") + "\n")
            fh.write("\n\nclass %s(Document):\n" % name.replace(" ", ""))
            fh.write("\n".join(("    " + l if l.strip() else l) for l in body.split("\n")) + "\n")
            if tail:
                fh.write("\n\n" + tail.strip("\n") + "\n")
    print("OK ->", module, "/", name)
