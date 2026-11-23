frappe.ui.form.on("School Payment", {
  refresh(frm) {
    if (frm.is_new() || frm.doc.status !== "Pending") return;
    frm.add_custom_button(__("Confirm Payment"), () => {
      if (frm.is_dirty()) { frappe.msgprint(__("Save the form first.")); return; }
      frappe.confirm(__("Confirm that the money is received? This adds credits or extends validity."), () =>
        frappe.call({ method: "teacher_one_platform.teacher_one_platform.doctype.school.school.confirm_payment", args: { name: frm.doc.name }, freeze: true,
          callback: (r) => { frappe.show_alert({ message: r.message, indicator: "green" }); frm.reload_doc(); },
          error: () => frm.reload_doc() }));
    }).addClass("btn-primary");
  },
});
