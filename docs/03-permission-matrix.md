# 03. Permission Matrix

## Roles and admin-controlled features (MVP)

Roles are **Student**, **Staff**, **Worker** and **Admin**. Every page or action is guarded by a *feature*
(`apps/accounts/features.py`). New accounts get their role's defaults and the admin can switch each feature
per user in the admin portal (`/portal/users/`). Admins always have all features. For the state machine,
users map onto workflow roles: *Manage complaints* → `admin`, *Work on assigned jobs* → `technician`,
*Raise / track complaints* → `requester`.

## Role-Based Access Control Matrix (state machine roles)

| Action | Requester | Technician | Admin |
|---|---|---|---|
| **View request** | Own or affected | Assigned only | All |
| **Edit severity** | Before assignment | No | Override with reason |
| **Add comment** | Own or affected | Assigned | Yes |
| **Assign / reassign** | No | No | Yes |
| **Update status, notes, parts** | No | Assigned only | Yes |
| **Report work complete** | No | Assigned only | Yes |
| **Confirm fixed / reopen** | Own or affected | No | Reopen only |
| **View reports** | No | Own workload | All |

---

## Security Invariants

> [!IMPORTANT]
> **Anti-Enumeration Rule (IDOR Protection):**
> Unauthorized access to another user's request **MUST ALWAYS** return HTTP `404 Not Found`, **never** `403 Forbidden`.
> Returning 403 leaks the existence of sensitive maintenance requests or private campus room numbers to unauthorized users. A 404 ensures zero information leakage.
