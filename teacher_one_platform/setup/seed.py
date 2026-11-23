import frappe

PLANS = {
    "Starter": ["attendance_sms", "mcq_exams"],
    "Pro": ["attendance_sms", "mcq_exams", "whatsapp", "written_marks", "report_cards", "export"],
    "Elite": ["attendance_sms", "mcq_exams", "whatsapp", "written_marks", "report_cards", "export",
              "ai_ocr", "voice_marks"],
}


def run():
    for name, feats in PLANS.items():
        if frappe.db.exists("School Package", name):
            continue
        frappe.get_doc({"doctype": "School Package", "package_name": name, "seat_price": 365, "min_seats": 1,
                        "max_seats": 500, "student_cap": 0,
                        "features": [{"feature_key": f, "enabled": 1} for f in feats]}).insert()
    frappe.db.commit()
    print("Packages:", frappe.get_all("School Package", pluck="name"))
