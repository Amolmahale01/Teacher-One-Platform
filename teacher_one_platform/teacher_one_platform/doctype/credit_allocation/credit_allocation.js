frappe.ui.form.on("Credit Allocation", {
  refresh(frm) {
    if (frm.is_new() || frm.doc.status === "Applied") return;
    frm.add_custom_button(__("Retry"), () => frappe.call({
      method: "teacher_one_platform.teacher_one_platform.doctype.school.school.retry_allocation", args: { name: frm.doc.name }, freeze: true,
      callback: () => frm.reload_doc(), error: () => frm.reload_doc() }));
  },
});
