frappe.listview_settings["School Seat Request"] = {
  onload(list) {
    list.page.add_inner_button(__("Fetch Requests from Schools"), () => frappe.call({
      method: "teacher_one_platform.teacher_one_platform.doctype.school.school.fetch_requests", freeze: true,
      callback: (r) => { frappe.show_alert(__("New requests: {0}", [r.message.new_requests])); list.refresh(); } }));
  },
};
