# Problem
CKAN 2.x bearer-token authentication is inconsistent for API authorization. The same Tapis JWT can resolve an explicit CKAN user via `user_show`, but fails current-user organization lookup and package edit authorization. This breaks Upstream station/campaign publishing to CKAN because org membership checks and dataset writes both fail for valid CKAN users.

# Current Behavior
- Clicking publish in Upstream reaches the backend, but CKAN-backed station publish fails even for a user who is actually an admin in the target CKAN organization.
- `organization_list_for_user` returns an empty result for a valid bearer JWT.
- `package_patch` fails with an authorization error and a blank user context: `Access denied: User  not authorized to edit package ...`
- `X-Tapis-Token` no longer works against CKAN 2.11.4 and returns `401 Invalid or expired X-Tapis-Token`.
- Upstream receives false negatives on org membership and blocks or fails CKAN publication.

# Expected Behavior
- A valid Tapis bearer JWT for CKAN user `wmobley` should resolve the current authenticated CKAN user context consistently.
- `organization_list_for_user` should return organizations including `setx-uifl` for `wmobley`.
- `package_patch` should authorize edits for datasets owned by organizations where `wmobley` is an admin.
- Bearer-token auth should work consistently for both read and write authorization paths.

# Tasks
- Debug CKAN 2.x token-auth current-user resolution for API requests.
- Inspect the auth/plugin/middleware path that maps `Authorization: Bearer <JWT>` to CKAN request user context.
- Verify why `user_show?id=wmobley` succeeds while `organization_list_for_user` returns `[]`.
- Verify why `package_patch` fails auth with blank user context for the same JWT.
- Confirm whether CKAN 2.x intentionally dropped `X-Tapis-Token` support or if that regression is accidental.
- Fix organization membership lookup for bearer-authenticated users.
- Fix package edit authorization for bearer-authenticated users.
- Test with a real Tapis JWT for CKAN user `wmobley`.

# Files To Check
- `ckan-docker` auth/plugin configuration related to Tapis OAuth2 / JWT bearer authentication
- Any CKAN extension or middleware that maps JWTs to CKAN users / `g.user` / API auth context
- Any code paths handling `organization_list_for_user` authorization
- Any code paths handling `package_patch` authorization
- Repo docs currently describing bearer auth behavior: [README.md](/Users/wmobley/Documents/GitHub/upstream/ckan-docker/README.md)

# Evidence / Repro
These curls demonstrate the issue with the same valid JWT:

1. Explicit user lookup works:

```bash
curl -sS 'https://ckan.tacc.utexas.edu/api/3/action/user_show?id=wmobley' \
  -H "Authorization: Bearer ${JWT}" \
  -H 'Content-Type: application/json' | jq
```

2. Current-user org lookup fails:

```bash
curl -sS 'https://ckan.tacc.utexas.edu/api/3/action/organization_list_for_user?all_fields=true' \
  -H "Authorization: Bearer ${JWT}" \
  -H 'Content-Type: application/json' | jq
```

Result:

```json
{"success": true, "result": []}
```

3. Package write auth fails:

```bash
curl -sS 'https://ckan.tacc.utexas.edu/api/3/action/package_patch' \
  -H "Authorization: Bearer ${JWT}" \
  -H 'Content-Type: application/json' \
  --data '{"id":"a64f1980-1d5d-45db-a740-7d27f4603b30","private":true}' | jq
```

Result:

```json
{
  "error": {
    "__type": "Authorization Error",
    "message": "Access denied: User  not authorized to edit package a64f1980-1d5d-45db-a740-7d27f4603b30"
  },
  "success": false
}
```

4. `X-Tapis-Token` no longer works:

```bash
curl -i 'https://ckan.tacc.utexas.edu/api/3/action/organization_list_for_user?all_fields=true' \
  -H "X-Tapis-Token: ${JWT}" \
  -H 'Content-Type: application/json'
```

Result:
- `401 Unauthorized` with `Invalid or expired X-Tapis-Token`

5. CKAN data confirms the user and org membership are real:
- `user_show?id=wmobley` returns active CKAN user `wmobley`
- `organization_show?id=setx-uifl&include_users=true` shows `wmobley` with `capacity: "admin"`

# Acceptance Criteria
- Bearer-authenticated `organization_list_for_user` returns `setx-uifl` for `wmobley`
- Bearer-authenticated `package_patch` succeeds for datasets in orgs where `wmobley` is admin
- CKAN authorization no longer reports blank user context for valid bearer JWTs
- Upstream station publish succeeds without false org-membership failures once CKAN auth is fixed
