import frappe
from frappe import _
from frappe.model.document import Document
from teacher_one_platform.sync import run_on_site, FEATURES


class School(Document):
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


@frappe.whitelist()
def sync(name):
    frappe.only_for("System Manager")
    d = frappe.get_doc("School", name)
    if d.status not in ("Approved", "Active", "Suspended"):
        frappe.throw(_("Approve the school first"))
    pkg = frappe.get_doc("School Package", d.package)
    on = {r.feature_key for r in pkg.features if r.enabled}
    kw = dict(plan_name=pkg.name, seat_limit=d.seats, student_cap=pkg.student_cap or 0, valid_till=str(d.valid_till) if d.valid_till else None,
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


# ================= provisioning (hissa B) =================
import os
import re


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "school"


def _check_site_name(site):
    suffix = frappe.conf.get("school_site_suffix") or ".localhost"
    if not site or not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9-]+)+", site):
        frappe.throw(_("Invalid site name: {0}").format(site))
    if not site.endswith(suffix):
        frappe.throw(_("Site name must end with {0}").format(suffix))
    if site == frappe.local.site:
        frappe.throw(_("This is the control site's own name"))


@frappe.whitelist()
def provision(name):
    frappe.only_for("System Manager")
    d = frappe.get_doc("School", name)
    if d.status not in ("Approved", "Active"):
        frappe.throw(_("Set the school status to Approved first"))
    if d.provision_status in ("Running", "Done"):
        frappe.throw(_("Provisioning is {0}").format(d.provision_status))
    if not d.admin_email:
        frappe.throw(_("Admin Email is required"))
    if not frappe.conf.get("mariadb_root_password"):
        frappe.throw(_("Set mariadb_root_password in the control site config first"))
    if not d.site_name:
        d.db_set("site_name", _slug(d.school_name) + (frappe.conf.get("school_site_suffix") or ".localhost"))
        d.reload()
    _check_site_name(d.site_name)
    d.db_set({"provision_status": "Running", "provision_log": ""})
    frappe.db.commit()
    frappe.enqueue("teacher_one_platform.teacher_one_platform.doctype.school.school._provision_job",
                   queue="long", timeout=1800, name=name)
    return "started"


def _provision_job(name):
    from frappe.utils import random_string, now_datetime
    from frappe.utils.password import set_encrypted_password
    from teacher_one_platform.sync import run_bench, run_on_site
    d = frappe.get_doc("School", name)
    site = d.site_name
    root = frappe.conf.get("mariadb_root_password")
    admin_pwd = "Adm#" + random_string(8) + "5!"
    api_key, api_secret = frappe.generate_hash(length=15), frappe.generate_hash(length=15)
    log = []

    def step(msg):
        log.append("%s  %s" % (now_datetime().strftime("%H:%M:%S"), msg))
        frappe.db.set_value("School", name, "provision_log", "\n".join(log))
        frappe.db.commit()

    def mask(t):
        return (t or "").replace(root, "***").replace(admin_pwd, "***").replace(api_secret, "***")

    try:
        exists = os.path.isdir(os.path.join(frappe.utils.get_bench_path(), "sites", site))
        if exists:
            step("Site already exists, skipping creation")
        else:
            step("Creating site %s (1-2 min)..." % site)
            ok, out = run_bench(["new-site", site, "--mariadb-root-password", root,
                                 "--admin-password", frappe.conf.get("default_site_admin_password") or "123", "--install-app", "teacher_one"])
            if not ok:
                raise Exception("new-site failed: " + mask(out)[-400:])
            step("Site created, teacher_one installed")
        ok, out = run_bench(["--site", site, "set-admin-password",
                             frappe.conf.get("default_site_admin_password") or "123"])
        step("Administrator password set to the default" if ok else "Could not set the Administrator password")
        step("Setting up roles, settings, workspaces...")
        ok, out = run_on_site(site, "teacher_one.setup.provision.bootstrap",
                              dict(admin_email=d.admin_email, admin_name=d.admin_name or "Principal",
                                   admin_mobile=d.admin_mobile or "", admin_password=admin_pwd, api_key=api_key, api_secret=api_secret,
                                   school_name=d.school_name), timeout=900)
        if not ok:
            raise Exception("bootstrap failed: " + mask(out)[-400:])
        frappe.db.set_value("School", name, "api_key", api_key)
        frappe.db.set_value("School", name, "api_secret_enc", __import__("frappe.utils.password", fromlist=["encrypt"]).encrypt(api_secret))
        frappe.db.commit()
        step("Bootstrap done, first School Admin created, API linked")
        run_bench(["--site", site, "set-admin-password",
                   frappe.conf.get("default_site_admin_password") or "123"])
        run_bench(["--site", site, "clear-cache"])
        step("Cache cleared")
        ok, out = run_bench(["--site", site, "execute", "teacher_one.setup.repair.run"])
        run_bench(["--site", site, "set-admin-password",
                   frappe.conf.get("default_site_admin_password") or "123"])
        step("Site repair done" if ok else "Site repair FAILED: " + mask(out)[-200:])
        sync(name)
        step("Plan, seats, features synced")
        pkg_credits = frappe.db.get_value("School Package", d.package, "free_credits") or 0
        if pkg_credits and not frappe.db.exists("Credit Allocation", {"school": name, "remark": "Free credits"}):
            a = frappe.get_doc({"doctype": "Credit Allocation", "school": name, "credits": pkg_credits,
                                "remark": "Free credits", "status": "Pending"}).insert()
            frappe.db.commit()
            _apply_allocation(a.name)
            step("%s free credits added" % pkg_credits)
        set_encrypted_password("School", name, admin_pwd, "admin_password_once")
        frappe.db.set_value("School", name, {"provision_status": "Done", "status": "Active"})
        step("DONE")
    except Exception:
        frappe.db.rollback()
        log.append("FAILED: " + mask(frappe.get_traceback())[-600:])
        frappe.db.set_value("School", name, {"provision_status": "Failed", "provision_log": "\n".join(log)})
    frappe.db.commit()


@frappe.whitelist()
def reveal_admin_password(name):
    """Ek hi baar dikhta hai, phir hat jata hai."""
    frappe.only_for("System Manager")
    from frappe.utils.password import get_decrypted_password, delete_all_passwords_for
    pwd = get_decrypted_password("School", name, "admin_password_once", raise_exception=False)
    if not pwd:
        frappe.throw(_("No stored password. It was already shown once. Provision again or reset it on the school site."))
    frappe.db.delete("__Auth", {"doctype": "School", "name": name, "fieldname": "admin_password_once"})
    d = frappe.get_doc("School", name)
    return {"site": d.site_name, "email": d.admin_email, "password": pwd}


# ================= hissa C1: seats, usage, reset password =================
def _pull(name):
    from teacher_one_platform.sync import run_json, run_on_site
    d = frappe.get_doc("School", name)
    ok, data = run_json(d.site_name, "teacher_one.setup.sync.usage", {})
    if not ok:
        return 0, data
    d.db_set({"credits_balance": data.get("credit_balance", 0), "seats_used": data.get("seats_used", 0), "students_active": data.get("students_active", 0),
              "usage_synced": frappe.utils.now_datetime()})
    new = 0
    for r in data.get("pending", []):
        ex = frappe.db.get_value("School Seat Request", {"school": name, "school_request": r["name"]},
                                 ["name", "status", "remark"], as_dict=True)
        if not ex:
            frappe.get_doc({"doctype": "School Seat Request", "school": name, "school_request": r["name"],
                            "seats": r["seats"], "reason": r.get("reason"), "requested_by": r.get("requested_by"),
                            "status": "Pending"}).insert(ignore_permissions=True)
            new += 1
        elif ex.status != "Pending":      # control me decide ho chuka, school par push dobara
            run_on_site(d.site_name, "teacher_one.setup.sync.set_request_status",
                        dict(name=r["name"], status=ex.status, remark=ex.remark or ""))
    frappe.db.commit()
    return new, "ok"


@frappe.whitelist()
def fetch_requests(school=None):
    frappe.only_for("System Manager")
    f = {"status": "Active", "site_name": ["is", "set"]}
    if school:
        f["name"] = school
    new, errors = 0, []
    for n in frappe.get_all("School", f, pluck="name"):
        c, msg = _pull(n)
        new += c
        if msg != "ok":
            errors.append("%s: %s" % (n, str(msg)[-120:]))
    return {"new_requests": new, "errors": errors}


def daily_fetch():
    for n in frappe.get_all("School", {"status": "Active", "site_name": ["is", "set"]}, pluck="name"):
        try:
            _pull(n)
        except Exception:
            frappe.log_error(title="Usage fetch failed: %s" % n, message=frappe.get_traceback())


@frappe.whitelist()
def approve_request(name, remark=""):
    frappe.only_for("System Manager")
    from teacher_one_platform.sync import run_on_site
    r = frappe.get_doc("School Seat Request", name)
    if r.status != "Pending":
        frappe.throw(_("This request is already {0}").format(r.status))
    d = frappe.get_doc("School", r.school)
    mx = frappe.db.get_value("School Package", d.package, "max_seats") or 0
    old, new = d.seats, d.seats + r.seats
    if mx and new > mx:
        frappe.throw(_("The package allows at most {0} seats. Change the package first.").format(mx))
    d.db_set("seats", new)
    frappe.db.commit()
    try:
        sync(d.name)
    except Exception:
        d.db_set("seats", old)
        frappe.db.commit()
        raise
    r.db_set({"status": "Approved", "remark": remark or "", "result": "Seats %s to %s" % (old, new)})
    ok, msg = run_on_site(d.site_name, "teacher_one.setup.sync.set_request_status",
                          dict(name=r.school_request, status="Approved", remark=remark or ""))
    if not ok:
        r.db_set("result", "Seats %s to %s. School status push failed, it retries on next fetch." % (old, new))
    frappe.db.commit()
    return new


@frappe.whitelist()
def reject_request(name, remark):
    frappe.only_for("System Manager")
    from teacher_one_platform.sync import run_on_site
    r = frappe.get_doc("School Seat Request", name)
    if r.status != "Pending":
        frappe.throw(_("This request is already {0}").format(r.status))
    if not (remark or "").strip():
        frappe.throw(_("Write a remark for the school"))
    d = frappe.get_doc("School", r.school)
    r.db_set({"status": "Rejected", "remark": remark, "result": "Rejected"})
    run_on_site(d.site_name, "teacher_one.setup.sync.set_request_status",
                dict(name=r.school_request, status="Rejected", remark=remark))
    frappe.db.commit()
    return "ok"


@frappe.whitelist()
def reset_admin_password(name):
    """Naya random password. Sirf is response me dikhta hai, kahin store nahi hota."""
    frappe.only_for("System Manager")
    from frappe.utils import random_string
    from teacher_one_platform.sync import run_on_site
    d = frappe.get_doc("School", name)
    if not d.site_name or not d.admin_email:
        frappe.throw(_("Site Name and Admin Email are required"))
    pwd = "Adm#" + random_string(8) + "5!"
    ok, msg = run_on_site(d.site_name, "teacher_one.setup.sync.reset_admin", dict(email=d.admin_email, password=pwd))
    if not ok:
        frappe.throw(_("Reset failed: {0}").format(msg[-300:]))
    return {"site": d.site_name, "email": d.admin_email, "password": pwd}


# ================= hissa C2: payments =================
@frappe.whitelist()
def confirm_payment(name):
    frappe.only_for("System Manager")
    from frappe.utils import add_months, getdate, nowdate
    p = frappe.get_doc("School Payment", name)
    if p.status != "Pending":
        frappe.throw(_("Already {0}").format(p.status))
    d = frappe.get_doc("School", p.school)
    if d.status not in ("Approved", "Active"):
        frappe.throw(_("School must be Approved or Active"))
    if p.kind == "Credit Pack":
        remark = "Payment " + p.name
        ex = frappe.db.get_value("Credit Allocation", {"school": p.school, "remark": remark}, ["name", "status"], as_dict=True)
        if ex:
            _apply_allocation(ex.name)          # Applied ho to 'already applied', Failed ho to retry
        else:
            a = frappe.get_doc({"doctype": "Credit Allocation", "school": p.school, "credits": p.credits,
                                "remark": remark, "status": "Pending"}).insert()
            frappe.db.commit()
            _apply_allocation(a.name)
        result = "%s credits added" % p.credits
    else:
        old = d.valid_till
        base = max(getdate(old), getdate(nowdate())) if old else getdate(nowdate())
        d.db_set("valid_till", add_months(base, p.renewal_months))
        frappe.db.commit()
        try:
            sync(d.name)
        except Exception:
            d.db_set("valid_till", old)
            frappe.db.commit()
            raise
        result = "Valid till %s to %s" % (old, add_months(base, p.renewal_months))
    p.db_set({"status": "Confirmed", "result": result})
    frappe.db.commit()
    return result



@frappe.whitelist()
def link_api(name):
    """Purane school ko HTTPS API se jodo. Test fail ho to link hata do."""
    frappe.only_for("System Manager")
    from frappe.utils.password import set_encrypted_password
    from teacher_one_platform.sync import _bench_run_on_site, run_json
    d = frappe.get_doc("School", name)
    if not d.site_name:
        frappe.throw(_("Site Name is required"))
    key, secret = frappe.generate_hash(length=15), frappe.generate_hash(length=15)
    ok, msg = _bench_run_on_site(d.site_name, "teacher_one.setup.sync.install_platform_user",
                                 dict(api_key=key, api_secret=secret))
    if not ok:
        frappe.throw(_("Could not create the service user: {0}").format(msg[-300:]))
    frappe.db.set_value("School", name, "api_key", key)
    frappe.db.set_value("School", name, "api_secret_enc", __import__("frappe.utils.password", fromlist=["encrypt"]).encrypt(secret))
    frappe.db.commit()
    ok, data = run_json(d.site_name, "teacher_one.setup.sync.usage", {})
    if not ok:
        frappe.db.set_value("School", name, "api_key", "")
        frappe.db.commit()
        frappe.throw(_("Linked, but the HTTP test failed, so the link was removed: {0}").format(str(data)[-300:]))
    return "linked"
