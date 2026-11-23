from gen_lib import *

make("Teacher One Platform", "School Seat Request", [
    F("school", "School", "Link", "School", 1, in_list_view=1, read_only=1),
    F("school_request", "School-side ID", read_only=1),
    F("seats", "Additional Seats", "Int", read_only=1, in_list_view=1),
    F("reason", "Reason", "Small Text", read_only=1),
    F("requested_by", "Requested By", read_only=1),
    F("status", "Status", "Select", "Pending\nApproved\nRejected", default="Pending", read_only=1, in_list_view=1),
    F("remark", "Decision Remark", "Small Text", read_only=1),
    F("result", "Result", "Small Text", read_only=1),
], autoname="format:SSR-{#####}", perms=[P("System Manager", **FULL)])
