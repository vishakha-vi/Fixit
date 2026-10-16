"""Feature access catalogue.

Every page or action in FixIt is guarded by one of these feature codes. Admins
always have every feature; for everyone else the admin picks the features per
user in the admin portal. New accounts start with their role's defaults.
"""

SUBMIT_COMPLAINT = "submit_complaint"
TRACK_COMPLAINT = "track_complaint"
WORK_ON_COMPLAINTS = "work_on_complaints"
VIEW_ALL_COMPLAINTS = "view_all_complaints"
MANAGE_COMPLAINTS = "manage_complaints"
DASHBOARD = "dashboard"
REMINDERS = "reminders"
OWN_PAYMENTS = "own_payments"
WORKER_PAYMENTS = "worker_payments"
WORKER_LOCATOR = "worker_locator"

# (code, label, description) in display order
FEATURES = [
    (SUBMIT_COMPLAINT, "Raise complaints", "Create new maintenance complaints."),
    (TRACK_COMPLAINT, "Track own complaints", "Track own complaints, confirm fixes and reopen."),
    (WORK_ON_COMPLAINTS, "Work on assigned jobs", "Start, pause and report fixed on assigned jobs."),
    (VIEW_ALL_COMPLAINTS, "View all complaints", "Read-only access to every complaint on campus."),
    (MANAGE_COMPLAINTS, "Manage complaints", "Review, assign, reassign, reject, merge and cancel."),
    (DASHBOARD, "Dashboard", "Campus-wide complaint statistics."),
    (REMINDERS, "Reminders", "Send reminders and receive reminder notifications."),
    (OWN_PAYMENTS, "My earnings", "See own job payments (workers)."),
    (WORKER_PAYMENTS, "Worker payments", "Record, approve and pay all worker payments."),
    (WORKER_LOCATOR, "Worker locator", "See which area every worker is located in."),
]

ALL_FEATURE_CODES = [code for code, _, _ in FEATURES]
FEATURE_LABELS = {code: label for code, label, _ in FEATURES}

ROLE_DEFAULT_FEATURES = {
    "student": [SUBMIT_COMPLAINT, TRACK_COMPLAINT, REMINDERS],
    "staff": [
        SUBMIT_COMPLAINT,
        TRACK_COMPLAINT,
        VIEW_ALL_COMPLAINTS,
        DASHBOARD,
        REMINDERS,
        WORKER_LOCATOR,
    ],
    "worker": [WORK_ON_COMPLAINTS, REMINDERS, OWN_PAYMENTS],
    "admin": list(ALL_FEATURE_CODES),
}


def default_features_for_role(role: str) -> list[str]:
    return list(ROLE_DEFAULT_FEATURES.get(role, []))


def clean_feature_codes(codes) -> list[str]:
    """Drop unknown codes and duplicates, keeping catalogue order."""
    wanted = set(codes or [])
    return [code for code in ALL_FEATURE_CODES if code in wanted]
