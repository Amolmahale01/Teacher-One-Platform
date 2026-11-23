frappe.ui.form.on("School", {
  refresh(frm) {
    if (frm.is_new()) return;
    const M = "teacher_one_platform.teacher_one_platform.doctype.school.school.";
    if (frm.doc.provision_status === "Running") {
      frm.dashboard.set_headline(__("Creating the school site... this page refreshes by itself."));
      setTimeout(() => { if (cur_frm && cur_frm.doc.name === frm.doc.name) frm.reload_doc(); }, 8000);
    }
    if (["Approved", "Active"].includes(frm.doc.status) && ["Not Started", "Failed"].includes(frm.doc.provision_status)) {
      frm.add_custom_button(__(frm.doc.provision_status === "Failed" ? "Retry Provisioning" : "Provision Site"), () => {
        if (frm.is_dirty()) { frappe.msgprint(__("Save the form first.")); return; }
        frappe.confirm(__("Create the site {0} now?", [frm.doc.site_name || __("(auto name)")]), () =>
          frappe.call({ method: M + "provision", args: { name: frm.doc.name }, freeze: true,
            callback: () => frm.reload_doc() }));
      }).addClass("btn-primary");
    }
    if (frm.doc.provision_status === "Done") {
      frm.add_custom_button(__("Show Admin Login (once)"), () => frappe.call({
        method: M + "reveal_admin_password", args: { name: frm.doc.name },
        callback: (r) => frappe.msgprint({ title: __("School Admin login"), indicator: "green",
          message: __("URL: http://{0}:8000<br>Email: {1}<br>Password: <b>{2}</b><br>Note it now. It will not be shown again.",
                      [r.message.site, r.message.email, r.message.password]) }) }));
    }
    if (frm.doc.provision_status !== "Running") {
      frm.add_custom_button(__("Sync to School"), () => {
        if (frm.is_dirty()) { frappe.msgprint(__("Save the form first.")); return; }
        frappe.call({ method: M + "sync", args: { name: frm.doc.name }, freeze: true,
          freeze_message: __("Updating the school site..."),
          callback: () => { frappe.show_alert({ message: __("School updated"), indicator: "green" }); frm.reload_doc(); },
          error: () => frm.reload_doc() });
      });
      frm.add_custom_button(__("Allocate Credits"), () => frappe.prompt([
        { fieldname: "credits", label: "Credits", fieldtype: "Int", reqd: 1 },
        { fieldname: "remark", label: "Remark", fieldtype: "Data" },
      ], (v) => frappe.call({ method: M + "allocate_credits", args: Object.assign({ school: frm.doc.name }, v),
        freeze: true, callback: () => { frappe.show_alert({ message: __("Credits added"), indicator: "green" }); frm.reload_doc(); },
        error: () => frm.reload_doc() }), __("Allocate Credits")));
    }
  },
});


frappe.ui.form.on("School", {
  refresh(frm) {
    if (frm.is_new() || !frm.doc.site_name) return;
    const M = "teacher_one_platform.teacher_one_platform.doctype.school.school.";
    frm.add_custom_button(__("Refresh Usage and Requests"), () => frappe.call({
      method: M + "fetch_requests", args: { school: frm.doc.name }, freeze: true,
      callback: (r) => {
        const e = (r.message.errors || []).join("<br>");
        frappe.msgprint({ title: __("Done"), indicator: e ? "orange" : "green",
          message: __("New seat requests: {0}", [r.message.new_requests]) + (e ? "<br>" + e : "") });
        frm.reload_doc();
      } }), __("Seats"));
    if (frm.doc.status === "Active" && frm.doc.admin_email) {
      frm.add_custom_button(__("Reset Admin Password"), () =>
        frappe.confirm(__("Set a new random password for {0}?", [frm.doc.admin_email]), () =>
          frappe.call({ method: M + "reset_admin_password", args: { name: frm.doc.name }, freeze: true,
            callback: (r) => frappe.msgprint({ title: __("New password"), indicator: "green",
              message: __("URL: http://{0}:8000<br>Email: {1}<br>Password: <b>{2}</b><br>Note it now. It will not be shown again.",
                          [r.message.site, r.message.email, r.message.password]) }) })));
    }
  },
});


frappe.ui.form.on("School", {
  refresh(frm) {
    if (frm.is_new() || !frm.doc.site_name || frm.doc.api_key) return;
    frm.add_custom_button(__("Link API"), () => frappe.call({
      method: "teacher_one_platform.teacher_one_platform.doctype.school.school.link_api", args: { name: frm.doc.name }, freeze: true,
      freeze_message: __("Creating the service user and testing..."),
      callback: () => { frappe.show_alert({ message: __("API linked"), indicator: "green" }); frm.reload_doc(); },
      error: () => frm.reload_doc() }), __("Seats"));
  },
});
