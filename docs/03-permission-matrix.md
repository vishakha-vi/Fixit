# 03. Permission Matrix

## Role-Based Access Control Matrix

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
