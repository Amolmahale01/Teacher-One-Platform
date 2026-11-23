import os
import shutil
import subprocess
import frappe
import requests

FEATURES = ["attendance_sms", "mcq_exams", "whatsapp", "written_marks", "report_cards",
            "export", "ai_ocr", "voice_marks"]


def _bench_run_on_site(site, method, kwargs, timeout=180):
    """School site par Frappe call ke through custom method chalao."""
    root = frappe.utils.get_bench_path()

    if not site or not os.path.isdir(os.path.join(root, "sites", site)):
        return False, "site '%s' not found on this bench" % site

    payload = {"fn": method}
    payload.update(kwargs or {})

    cmd = [
        shutil.which("bench") or "bench",
        "--site", site,
        "execute", "frappe.call",
        "--kwargs", repr(payload)
    ]

    try:
        p = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"

    lines = [l.strip().strip('"') for l in (p.stdout or "").splitlines()]

    if p.returncode == 0 and "ok" in lines:
        return True, "ok"

    return False, ((p.stderr or "") + (p.stdout or ""))[-500:] or "failed"

def run_bench(args, timeout=900):
    """bench command chalao (jaise new-site). Return (ok, output)."""
    root = frappe.utils.get_bench_path()
    try:
        p = subprocess.run([shutil.which("bench") or "bench"] + args, cwd=root, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return p.returncode == 0, ((p.stdout or "") + (p.stderr or ""))[-1500:]


def _bench_run_json(site, method, kwargs, timeout=180):
    """School site par function chalao aur uska dict wapas lo. Return (ok, data|error)."""
    import json
    import ast
    root = frappe.utils.get_bench_path()
    if not site or not os.path.isdir(os.path.join(root, "sites", site)):
        return False, "site '%s' not found on this bench" % site
    cmd = [shutil.which("bench") or "bench", "--site", site, "execute", method, "--kwargs", repr(kwargs)]
    try:
        p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if p.returncode != 0:
        return False, ((p.stderr or "") + (p.stdout or ""))[-500:]
    for line in reversed((p.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return True, json.loads(line)
            except ValueError:
                try:
                    return True, ast.literal_eval(line)
                except Exception:
                    pass
    return False, "no data returned: " + (p.stdout or "")[-300:]



def _http(site, method, kwargs, timeout=120):
    """None = HTTP use nahi hoga (bench se chalao). Warna (ok, data)."""
    from frappe.utils.password import get_decrypted_password
    mode = frappe.conf.get("platform_transport") or "auto"
    if mode == "bench":
        return None
    name = frappe.db.get_value("School", {"site_name": site}, "name")
    key = frappe.db.get_value("School", name, "api_key") if name else None
    secret = None
    if key:
        from frappe.utils.password import decrypt
        enc = frappe.db.get_value("School", name, "api_secret_enc")
        try:
            secret = decrypt(enc) if enc else None
        except Exception:
            secret = None
    if not (key and secret):
        return (False, "school is not linked to the API. Use Link API on the School form") if mode == "http" else None
    base = (frappe.conf.get("school_base_url_template") or "http://{site}:8000").format(site=site)
    headers = {"Authorization": "token %s:%s" % (key, secret), "X-Frappe-Site-Name": site}
    try:
        r = requests.post(base + "/api/method/" + method, json=kwargs, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return False, "network error: %s" % str(e)[:150]
    if r.status_code != 200:
        return False, "HTTP %s: %s" % (r.status_code, r.text[-300:])
    try:
        return True, r.json().get("message")
    except ValueError:
        return False, "bad response"


def run_on_site(site, method, kwargs, timeout=180):
    res = _http(site, method, kwargs, min(timeout, 120))
    if res is None:
        return _bench_run_on_site(site, method, kwargs, timeout)
    ok, data = res
    if ok and data == "ok":
        return True, "ok"
    return False, str(data)[-500:]


def run_json(site, method, kwargs, timeout=180):
    res = _http(site, method, kwargs, min(timeout, 120))
    if res is None:
        return _bench_run_json(site, method, kwargs, timeout)
    ok, data = res
    if ok and isinstance(data, dict):
        return True, data
    return False, str(data)[-500:]


# ================= self-healing API link (final definitions) =================
def _creds(name):
    """(key, secret) ya None. Decrypt fail ho to None."""
    from frappe.utils.password import decrypt
    key = frappe.db.get_value("School", name, "api_key")
    enc = frappe.db.get_value("School", name, "api_secret_enc")
    if not (key and enc):
        return None
    try:
        secret = decrypt(enc)
    except Exception:
        return None
    return (key, secret) if secret else None


def relink(name):
    """Bench se naya service-user key banao aur store karo. True/False."""
    from frappe.utils.password import encrypt
    site = frappe.db.get_value("School", name, "site_name")
    if not site:
        return False
    key, secret = frappe.generate_hash(length=15), frappe.generate_hash(length=15)
    ok, msg = _bench_run_on_site(site, "teacher_one.setup.sync.install_platform_user",
                                 dict(api_key=key, api_secret=secret))
    if not ok:
        frappe.log_error(title="API relink failed: %s" % site, message=msg)
        return False
    frappe.db.set_value("School", name, {"api_key": key, "api_secret_enc": encrypt(secret)})
    frappe.db.commit()
    return True


def _http(site, method, kwargs, timeout=120, _retry=True):
    """None = bench se chalao. Warna (ok, data)."""
    mode = frappe.conf.get("platform_transport") or "auto"
    if mode == "bench":
        return None
    name = frappe.db.get_value("School", {"site_name": site}, "name")
    if not name:
        return None
    creds = _creds(name)
    if not creds:
        if not relink(name):
            if mode == "http":
                return False, "school API link could not be created. Check that the school site is reachable"
            return None
        creds = _creds(name)
        if not creds:
            return None
    base = (frappe.conf.get("school_base_url_template") or "http://{site}:8000").format(site=site)
    headers = {"Authorization": "token %s:%s" % creds, "X-Frappe-Site-Name": site}
    try:
        r = requests.post(base + "/api/method/" + method, json=kwargs, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return None if mode == "auto" else (False, "network error: %s" % str(e)[:150])
    if r.status_code in (401, 403) and _retry:
        # key badal gayi ya user disable hua: ek baar relink karke dobara
        if relink(name):
            return _http(site, method, kwargs, timeout, _retry=False)
    if r.status_code != 200:
        return False, "HTTP %s: %s" % (r.status_code, r.text[-300:])
    try:
        return True, r.json().get("message")
    except ValueError:
        return False, "bad response"


def ensure_all_linked():
    """Daily job: har school (suspended samet) ka link theek rakho."""
    if (frappe.conf.get("platform_transport") or "auto") == "bench":
        return
    for n in frappe.get_all("School", {"site_name": ["is", "set"]}, pluck="name"):
        try:
            if not _creds(n):
                relink(n)
        except Exception:
            frappe.log_error(title="ensure_all_linked %s" % n, message=frappe.get_traceback())


# ================= self-healing API link (final definitions) =================
def _creds(name):
    """(key, secret) ya None. Decrypt fail ho to None."""
    from frappe.utils.password import decrypt
    key = frappe.db.get_value("School", name, "api_key")
    enc = frappe.db.get_value("School", name, "api_secret_enc")
    if not (key and enc):
        return None
    try:
        secret = decrypt(enc)
    except Exception:
        return None
    return (key, secret) if secret else None


def relink(name):
    """Bench se naya service-user key banao aur store karo. True/False."""
    from frappe.utils.password import encrypt
    site = frappe.db.get_value("School", name, "site_name")
    if not site:
        return False
    key, secret = frappe.generate_hash(length=15), frappe.generate_hash(length=15)
    ok, msg = _bench_run_on_site(site, "teacher_one.setup.sync.install_platform_user",
                                 dict(api_key=key, api_secret=secret))
    if not ok:
        frappe.log_error(title="API relink failed: %s" % site, message=msg)
        return False
    frappe.db.set_value("School", name, {"api_key": key, "api_secret_enc": encrypt(secret)})
    frappe.db.commit()
    return True


def _http(site, method, kwargs, timeout=120, _retry=True):
    """None = bench se chalao. Warna (ok, data)."""
    mode = frappe.conf.get("platform_transport") or "auto"
    if mode == "bench":
        return None
    name = frappe.db.get_value("School", {"site_name": site}, "name")
    if not name:
        return None
    creds = _creds(name)
    if not creds:
        if not relink(name):
            if mode == "http":
                return False, "school API link could not be created. Check that the school site is reachable"
            return None
        creds = _creds(name)
        if not creds:
            return None
    base = (frappe.conf.get("school_base_url_template") or "http://{site}:8000").format(site=site)
    headers = {"Authorization": "token %s:%s" % creds, "X-Frappe-Site-Name": site}
    try:
        r = requests.post(base + "/api/method/" + method, json=kwargs, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return None if mode == "auto" else (False, "network error: %s" % str(e)[:150])
    if r.status_code in (401, 403) and _retry:
        # key badal gayi ya user disable hua: ek baar relink karke dobara
        if relink(name):
            return _http(site, method, kwargs, timeout, _retry=False)
    if r.status_code != 200:
        return False, "HTTP %s: %s" % (r.status_code, r.text[-300:])
    try:
        return True, r.json().get("message")
    except ValueError:
        return False, "bad response"


def ensure_all_linked():
    """Daily job: har school (suspended samet) ka link theek rakho."""
    if (frappe.conf.get("platform_transport") or "auto") == "bench":
        return
    for n in frappe.get_all("School", {"site_name": ["is", "set"]}, pluck="name"):
        try:
            if not _creds(n):
                relink(n)
        except Exception:
            frappe.log_error(title="ensure_all_linked %s" % n, message=frappe.get_traceback())


# ---- HTTP sirf whitelisted sync API ke liye. bootstrap, install_platform_user waghera bench se ----
_http_inner = _http


def _http(site, method, kwargs, timeout=120, _retry=True):
    if not method.startswith("teacher_one.setup.sync.") or method.endswith(".install_platform_user"):
        return None
    return _http_inner(site, method, kwargs, timeout, _retry)
