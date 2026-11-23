frappe.ui.form.on("School Seat Request", {
  refresh(frm) {
    if (frm.is_new() || frm.doc.status !== "Pending") return;
    frm.add_custom_button(__("Approve"), () => frappe.prompt(
      { fieldname: "remark", label: "Remark (optional)", fieldtype: "Data" },
      (v) => frappe.call({ method: "teacher_one_platform.teacher_one_platform.doctype.school.school.approve_request", args: { name: frm.doc.name, remark: v.remark || "" },
        freeze: true, callback: () => frm.reload_doc(), error: () => frm.reload_doc() }), __("Approve")))
      .addClass("btn-primary");
    frm.add_custom_button(__("Reject"), () => frappe.prompt(
      { fieldname: "remark", label: "Reason for rejection", fieldtype: "Small Text", reqd: 1 },
      (v) => frappe.call({ method: "teacher_one_platform.teacher_one_platform.doctype.school.school.reject_request", args: { name: frm.doc.name, remark: v.remark },
        freeze: true, callback: () => frm.reload_doc() }), __("Reject")));
  },
});
