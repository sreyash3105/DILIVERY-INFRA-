# Change Record — CR-010

| Field | Detail |
|-------|--------|
| **Change ID** | CR-010 |
| **Date** | 2026-07-01 |
| **Type** | Security Hardening |
| **Severity** | High |
| **Author** | Sreyash Baishkhiyar |
| **Status** | Applied |

---

## Description

Replaced the hardcoded default API key `"test_api_key_123"` in the application seeder with a cryptographically random key generated at runtime. This eliminates a publicly known credential that was committed to source code.

## File Changed

`backend/app/main.py`

## Function / Location

`lifespan()` — auto-seed block, approximately lines 33–44

## Root Cause

The auto-seeder created the default tenant with a fixed, known string:

```python
default_tenant = Tenant(name="Default Tenant A", api_key="test_api_key_123")
print("Auto-seeded default Tenant A (key: 'test_api_key_123') and 3 drivers.")
```

This key was:
1. **Committed to Git** — visible to anyone who clones the repository (public or private leak scenario)
2. **Static across all deployments** — every server that never rotated the key ran with the same known credential
3. **Printed to logs** — confirmed the known key in startup logs, making scraping trivial

The existing `generate_api_key()` utility (`core/security.py`) already produced a `dep_<32-byte-urlsafe-token>` format key using Python's `secrets` module but was only used in the API key rotation endpoint, never in the seeder.

## Change Made

```diff
  from app.models.tenant import Tenant
  from app.models.driver import Driver, DriverStatus
+ from app.core.security import generate_api_key

  async with AsyncSessionLocal() as db:
      tenant_res = await db.execute(select(Tenant).limit(1))
      if not tenant_res.scalars().first():
-         # Seed default tenant with key 'test_api_key_123'
-         default_tenant = Tenant(name="Default Tenant A", api_key="test_api_key_123")
+         # Generate a unique secure key on first boot — never use a hardcoded key in source.
+         # The generated key is printed once to stdout for the developer to copy.
+         generated_key = generate_api_key()
+         default_tenant = Tenant(name="Default Tenant A", api_key=generated_key)
          db.add(default_tenant)
          ...
          await db.commit()
-         print("Auto-seeded default Tenant A (key: 'test_api_key_123') and 3 drivers.")
+         print(f"[STARTUP] Auto-seeded Default Tenant A and 3 drivers.")
+         print(f"[STARTUP] *** API Key (copy this now): {generated_key} ***")
```

## Impact

- **Before:** Every fresh deployment had the same known API key `test_api_key_123`. Any entity with repository access could immediately authenticate as the default tenant.
- **After:** Each new deployment generates a unique `dep_<random>` key. The key is printed once to the startup log for the developer to copy and is never repeated or stored in source control.
- **Existing data:** No impact — the seeder only runs when the database is empty (`Tenant` table has zero rows). Existing deployments are unaffected.
- **Key format:** `dep_` + 32-byte URL-safe base64 token — consistent with the format used by the existing `/analytics/tenant/rotate-key` endpoint.

## Risk Assessment

Low. The seeder runs exactly once per fresh database. The generated key is deterministically logged at startup. No existing callers in a fresh deployment have a previously memorized key to break.

---
