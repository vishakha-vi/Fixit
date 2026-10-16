# 05. Assumptions and Limitations

This document captures the baseline assumptions and operational boundaries of the FixIt platform.

## Core Assumptions

1. **Completion Codes Prove Interaction, Not Repair Quality:**
   - When a technician uses an on-site completion code provided by the requester, it proves that physical, in-person interaction occurred between the technician and resident at the designated location.
   - It does *not* provide an automated guarantee of craftsmanship, technical longevity, or underlying component quality. The 7-day reopen window allows the requester to contest unresolved or subpar repairs.

2. **Demo-Clock Mode Simulates Time:**
   - In demonstration environments, real-time SLAs (such as 4 hours, 72 hours, or 7 days) cannot be demonstrated without simulated acceleration.
   - When `DEMO_MODE=True`, `apps/core/clock.now()` simulates current time using a persistent offset stored in the `DemoClock` single-row database model.
   - When `DEMO_MODE=False`, `apps/core/clock.now()` always returns the genuine system `timezone.now()`, and any programmatic attempt to advance or reset the clock raises an explicit error.

3. **Campus Connectivity and Identity:**
   - Campus residents and staff authenticate using local username and password credentials.
   - Future phases can integrate institutional SSO (CAS, SAML, Google Workspace); Phase 0 uses standard Django authentication with customized role attribution (`requester`, `technician`, `admin`).

4. **Single Campus Realm:**
   - Locations belong to a single institution with shared maintenance personnel. Multi-tenant campus partitioning is a non-goal for Phase 0.

## Operational Limitations

1. **Hardware Independence:**
   - No reliance on IoT sensors, physical door readers, or external smart-meter hardware. All lifecycle events are human-driven and auditable.

2. **Network Resilience & Offline Limitations:**
   - While assets are vendored locally so the application does not depend on third-party CDNs or internet connectivity once hosted, end-users require network access to submit forms and confirm repairs. Full offline Progressive Web App (PWA) client sync is planned as a stretch consideration (Scenario S11).

3. **Email and SMS Alerts:**
   - Failures in upstream notification providers (SMTP/SMS) must never block database transactions or ticket status changes (Scenario S33). Alerts are asynchronous or best-effort.
