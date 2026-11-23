from gen_lib import *

MOD = "Teacher One Platform"
FEATS = "attendance_sms\nmcq_exams\nwhatsapp\nwritten_marks\nreport_cards\nexport\nai_ocr\nvoice_marks"
SM = [P("System Manager", **FULL)]

make(MOD, "School Package Feature", [
    F("feature_key", "Feature", "Select", FEATS, 1, in_list_view=1),
    F("enabled", "Enabled", "Check", default="1", in_list_view=1),
], istable=1)

make(MOD, "School Package", [
    F("package_name", "Package Name", reqd=1, unique=1, in_list_view=1),
    F("seat_price", "Seat Price (per teacher/staff per year)", "Currency", default="365", in_list_view=1),
    F("min_seats", "Minimum Seats", "Int", default="1"),
    F("max_seats", "Maximum Seats (0 = no limit)", "Int", default="0"),
    F("student_cap", "Student Cap (0 = unlimited)", "Int", default="0"),
    F("free_credits", "Included Free Credits", "Int", default="0"),
    F("features", "Features", "Table", "School Package Feature"),
], autoname="field:package_name", perms=SM, code='''
def validate(self):
    if self.max_seats and self.min_seats and self.min_seats > self.max_seats:
        frappe.throw(_("Minimum seats cannot exceed maximum seats"))
    if (self.seat_price or 0) < 0:
        frappe.throw(_("Seat price cannot be negative"))
    seen = set()
    for r in self.features:
        if r.feature_key in seen:
            frappe.throw(_("Row {0}: {1} is repeated").format(r.idx, r.feature_key))
        seen.add(r.feature_key)
''')

make(MOD, "Credit Allocation", [
    F("school", "School", "Link", "School", 1, in_list_view=1),
    F("credits", "Credits", "Int", reqd=1, in_list_view=1),
    F("remark", "Remark"),
    F("status", "Status", "Select", "Pending\nApplied\nFailed", default="Pending", read_only=1, in_list_view=1),
    F("result", "Result", "Small Text", read_only=1),
], autoname="format:CAL-{#####}",
   perms=[P("System Manager", read=1, create=1, report=1, export=1)],
   code='''
def validate(self):
    if not self.is_new():
        frappe.throw(_("A credit allocation cannot be edited."))
    if (self.credits or 0) <= 0:
        frappe.throw(_("Credits must be above 0"))
''')

make(MOD, "School", [
    F("school_name", "School Name", reqd=1, in_list_view=1),
    F("status", "Status", "Select", "Requested\nApproved\nActive\nSuspended\nArchived",
      default="Requested", reqd=1, in_list_view=1),
    F("site_name", "Site Name (e.g. school1.localhost)", in_list_view=1),
    F("sb1", "Admin Contact", "Section Break"),
    F("admin_name", "Admin Name"),
    F("admin_email", "Admin Email", "Data", "Email"),
    F("admin_mobile", "Admin Mobile"),
    F("sb2", "Subscription", "Section Break"),
    F("package", "School Package", "Link", "School Package", 1, in_list_view=1),
    F("seats", "Seats Purchased", "Int", reqd=1),
    F("valid_till", "Valid Till", "Date"),
    F("grace_days", "Grace Days", "Int", default="7"),
    F("sb3", "Credits and Sync", "Section Break"),
    F("credits_allocated", "Credits Allocated (total)", "Int", read_only=1),
    F("last_synced", "Last Synced", "Datetime", read_only=1),
    F("sync_result", "Sync Result", "Small Text", read_only=1),
], autoname="format:SCH-{#####}", title_field="school_name", perms=SM,
   imports="from teacher_one_platform.sync import run_on_site, FEATURES",
   code='''
def validate(self):
    pkg = frappe.db.get_value("School Package", self.package, ["min_seats", "max_seats"], as_dict=True)
    if not self.seats or self.seats < 1:
        frappe.throw(_("Seats must be at least 1"))
    if pkg.min_seats and self.seats < pkg.min_seats:
        frappe.throw(_("This package needs at least {0} seats").format(pkg.min_seats))
    if pkg.max_seats and self.seats > pkg.max_seats:
        frappe.throw(_("This package allows at most {0} seats").format(pkg.max_seats))
    if self.site_name:
        self.site_name = self.site_name.strip().lower()
        if frappe.db.exists("School", {"site_name": self.site_name, "name": ["!=", self.name or ""]}):
            frappe.throw(_("Another school already uses this site"))
''', tail='''
@frappe.whitelist()
def sync(name):
    frappe.only_for("System Manager")
    d = frappe.get_doc("School", name)
    if d.status not in ("Approved", "Active", "Suspended"):
        frappe.throw(_("Approve the school first"))
    pkg = frappe.get_doc("School Package", d.package)
    on = {r.feature_key for r in pkg.features if r.enabled}
    kw = dict(plan_name=pkg.name, seat_limit=d.seats, valid_till=str(d.valid_till) if d.valid_till else None,
              grace_days=d.grace_days or 0, suspended=1 if d.status == "Suspended" else 0,
              features={k: (k in on) for k in FEATURES}, school_name=d.school_name)
    ok, msg = run_on_site(d.site_name, "teacher_one.setup.sync.apply", kw)
    d.db_set({"last_synced": frappe.utils.now_datetime() if ok else d.last_synced,
              "sync_result": "OK" if ok else msg[-300:]})
    frappe.db.commit()
    if not ok:
        frappe.throw(_("Sync failed: {0}").format(msg[-300:]))
    return "ok"


def _apply_allocation(name):
    a = frappe.get_doc("Credit Allocation", name)
    if a.status == "Applied":
        return "already applied"
    site = frappe.db.get_value("School", a.school, "site_name")
    ok, msg = run_on_site(site, "teacher_one.setup.sync.apply_credits", dict(key=a.name, amount=a.credits))
    if ok:
        a.db_set({"status": "Applied", "result": "ok"})
        total = frappe.db.get_value("School", a.school, "credits_allocated") or 0
        frappe.db.set_value("School", a.school, "credits_allocated", total + a.credits)
        frappe.db.commit()
        return "applied"
    a.db_set({"status": "Failed", "result": msg[-300:]})
    frappe.db.commit()
    frappe.throw(_("Could not apply: {0}").format(msg[-300:]))


@frappe.whitelist()
def allocate_credits(school, credits, remark=""):
    frappe.only_for("System Manager")
    if frappe.db.get_value("School", school, "status") not in ("Approved", "Active"):
        frappe.throw(_("School must be Approved or Active"))
    a = frappe.get_doc({"doctype": "Credit Allocation", "school": school, "credits": int(credits),
                        "remark": remark, "status": "Pending"}).insert()
    frappe.db.commit()
    return _apply_allocation(a.name)


@frappe.whitelist()
def retry_allocation(name):
    frappe.only_for("System Manager")
    return _apply_allocation(name)
''')
