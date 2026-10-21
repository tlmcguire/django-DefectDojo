# Security Analysis

CSCI 360: Software Architecture, Security, and Testing | Fall 2026 - Tyler McGuire

Prepared with Claude Code (Anthropic), run inside the local clone of this fork. Code claims below cite files and line numbers read in this repository at version 3.2.300 (`__version__` in `dojo/__init__.py:7`). Every advisory cited was opened and read through the GitHub API (`gh api repos/.../security-advisories/<id>` or `gh api advisories/<id>`), and each has its link. Full disclosure is in the AI Use Log at the bottom.

**Commits**

- Code control: [`6b5ef59`](https://github.com/tlmcguire/django-DefectDojo/commit/6b5ef59a6de24a5ad9004ad1f545f96f1292d2d1) - `A5-Fix: Revoke API token when a forced password reset completes in change_password view`
- Documentation: `A5: Add security analysis and misuse cases` (this page, diagrams, SBOM)

**Sources committed in [`class-docs/`](../class-docs)** (this fork keeps course material there because `/docs` is DefectDojo's own Hugo site): `misuse-case-diagram.puml`, `trust-boundary-diagram.mmd`, `sbom.json`.

---

## Part 1: Misuse Case Diagram

Source: `class-docs/misuse-case-diagram.puml` (extends `use-case-diagram.puml` from A1b). PlantUML was not installed here, so this diagram is **not rendered**; the source was checked by reading only.

Five misuse cases (dark), two attackers outside the boundary, three controls:

| Misuse case | Threatens | Mitigated by |
|---|---|---|
| Retain Access After Forced Password Reset | Authenticate / Use API Token | Revoke API token on forced reset (the A5-Fix, Part 7) |
| Read Another Product's Data | Triage a Finding, Accept Risk | Per-object authorization (`dojo/authorization`) |
| Abuse Stored Integration Credentials | Import Scan Results | Per-object authorization (same layer) |
| Upload Malicious Attachment | Import Scan Results | none today (see Part 3, crossing 15) |
| Forge JIRA Webhook | Triage a Finding | Webhook secret in URL path (`dojo/jira/views.py`) |

---

## Part 2: Two Fully-Dressed Misuse Cases

### Misuse Case A: Retain Access After Forced Password Reset

**Attacker.** An authenticated insider or outsider who has obtained one user's password (phished, reused, or guessed). They want durable, quiet access to that user's products and findings through the API, and want it to survive the victim noticing and resetting.

**Preconditions.**

1. The attacker knows the victim's password.
2. `DD_API_TOKENS_ENABLED` and `DD_API_TOKEN_AUTH_ENDPOINT_ENABLED` are true (both default true, `settings.dist.py:267-269, 699-701`).
3. An administrator later sets the victim's `force_password_reset` flag, or the rate limiter lockout sets it (`dojo/decorators.py:163`).

**Attack scenario.**

1. Attacker POSTs the victim's username and password to `/api/v2/api-token-auth/` (`dojo/urls.py:218`) and receives the victim's API token.
2. Attacker stores the token. Nothing about the account changes, so the victim notices nothing.
3. The victim, or an administrator, notices suspicious activity and sets the forced-reset flag.
4. The victim logs in through the browser; `middleware.py:109` redirects every session request to `change_password`.
5. The victim sets a new password (`dojo/user/ui/views.py`, `change_password`). The password and flag are updated.
6. Attacker keeps calling `/api/v2/...` with the token from step 1. The API authenticates by token (`settings.dist.py:721`) and never consults the password or the reset flag.

**Intervention points.**

- Step 1: rate limiting on the token endpoint. It is wrapped in `dojo_ratelimit` but that decorator only blocks when `DD_RATE_LIMITER_BLOCK` is true, and it is off by default (`settings.dist.py:244`).
- Step 5/6: revoke the token when the reset completes. This is the control implemented in Part 7. Before it, nothing at step 5 touched the token.
- Step 3: refuse to issue a token while a reset is pending (not implemented; see Part 7 "does not fix").

**Consequence.** The attacker keeps the victim's full API permissions (read and write findings, import scans, depending on the victim's role) after the victim believes the account is recovered. The victim and the organisation lose the integrity of the reset as a recovery action. DefectDojo itself rates the same flaw medium (CVSS 3.1 `AV:N/AC:H/PR:L ... C:L/I:L`) in [GHSA-66vh-fm67-46vw](https://github.com/DefectDojo/django-DefectDojo/security/advisories/GHSA-66vh-fm67-46vw).

### Misuse Case B: Upload Malicious Attachment

**Attacker.** An authenticated user with permission to attach files to a finding, test or engagement (a low-privilege product member is enough). They want to read memory from the server process (secrets, other users' data in heap) or crash the web workers.

**Preconditions.**

1. The attacker can attach a file to an object (`manage_files`, `dojo/urls.py:243`).
2. The server runs Pillow older than 13.0.0 (this repo pins `Pillow==12.3.0`, `requirements.txt:33`).
3. Someone (the attacker, or a victim colleague) opens the page that renders the finding's images.

**Attack scenario.**

1. Attacker crafts a malformed compressed TIFF (the duplicated-tag technique described in [GHSA-c6hw-5grf-ff96](https://github.com/advisories/GHSA-c6hw-5grf-ff96)) and names it `photo.png`.
2. Attacker uploads it. `FileUpload.clean()` checks only the filename suffix against `DD_FILE_UPLOAD_TYPES`, which includes `.png` (`dojo/file_uploads/models.py:66-76`, `settings.dist.py:258`). The file is accepted.
3. `get_file_images()` decides the file is an image from the filename alone (`dojo/utils.py:1780-1781`).
4. The page template requests `finding/image/<token>`; that route is login-exempt and token-gated (`settings.dist.py:548`).
5. `download_finding_pic` (`dojo/finding/ui/views.py:2250`) runs `ImageSpec(...).generate()`. Pillow identifies the format from the file bytes, not the name, selects the TIFF decoder, and decodes.
6. The decoder reads past a heap buffer and writes the bytes into the pixels of the generated JPEG, which is streamed back to the requester.

**Intervention points.**

- Step 2: verify content, not name (compare magic bytes to the claimed extension; reject files that fail). Belongs in `FileUpload.clean()`.
- Step 5: decode inside a limited, separate process (a Celery task with resource limits) and restrict Pillow to the expected formats with `Image.open(..., formats=[...])`.
- Dependency level: upgrade Pillow to 13.0.0 or later.

**Consequence.** Per the advisory, fragments of server process heap, including pointer values, are returned as image pixels; a slightly different file crashes the worker. The system loses confidentiality of whatever sits in that process's memory and some availability. I did **not** build or run an exploit; this chain is reasoned from the code and the advisory text, and whether the leaked bytes would contain anything valuable is not established.

---

## Part 3: Trust Boundary Diagram

Source: `class-docs/trust-boundary-diagram.mmd` (Mermaid flowchart; written to the grammar, **not rendered** here). Six zones: untrusted internet, edge (nginx), application, data stores, third-party services, and build/release. Each numbered arrow is a boundary crossing.

### Crossings, what is validated, and by whom

| # | Crossing | What is validated, and by which component |
|---|---|---|
| 1 | Anonymous -> login form | Django `LoginView` checks credentials. Throttling via `dojo_ratelimit`, but it only blocks if `DD_RATE_LIMITER_BLOCK` is true (default off, `settings.dist.py:244`); `request.limited` is set (`decorators.py:156`) but nothing else in `dojo/` reads it. **Effectively unthrottled by default.** |
| 2 | Anonymous -> `/api/v2/api-token-auth/` | Credentials checked by DRF `obtain_auth_token`. Same default-off rate limit (`urls.py:218`). **Does not check `force_password_reset`.** |
| 3 | Anonymous -> `password_reset/`, `finding/image/<token>` | Login-exempt by regex list (`settings.dist.py:541-553`). Image route validated only by `FileAccessToken` lookup, deleted on use (`finding/ui/views.py`). |
| 4 | Browser session -> app | Django session + CSRF middleware. Cookie `Secure` flags default **false** (`settings.dist.py:61,65`), so TLS must be enforced by deployment. |
| 5 | API client -> `/api/v2/` | DRF authenticators (session, basic, token), `DjangoModelPermissions`, then per-object checks in `dojo/authorization`. **API tokens have no expiry.** |
| 6 | nginx -> uwsgi | nginx caps body at 800 MB (`nginx/nginx.conf:14`) and hides its version. Django validates `Host` via `ALLOWED_HOSTS` (`settings.dist.py:345`). |
| 7 | Scan upload -> app | Extension allow-list `DD_FILE_IMPORT_TYPES` (`dojo/validators.py:107`). No content check beyond what the chosen parser does. |
| 8 | App -> parser | Each of ~250 parsers owns its own parsing safety. Project convention is `defusedxml`; a spot check found direct `lxml`/`xml.etree` imports in `fortify/fpr_parser.py`, `burp_suite_dast/parser.py`, `sonarqube/soprasteria_helper.py` which I did **not** audit for XXE. |
| 9 | Attachment upload -> app | `FileUpload.clean()` checks filename suffix only (`file_uploads/models.py:66`). **Content is not validated.** |
| 10 | App -> PostgreSQL | Django ORM parameterises queries. Authorization is applied by queryset filters, not by the database. TLS to the DB is not configured by default (not verified beyond `DD_DATABASE_URL`). |
| 11-12 | App -> broker -> worker | `CELERY_ACCEPT_CONTENT = ["json"]` (`settings.dist.py:929`) rules out pickle. The compose default broker is `redis://valkey:6379/0` with no password (`docker-compose.yml:52`), so protection is network isolation only. |
| 13 | Worker -> PostgreSQL | Same as 10. |
| 14 | App -> media storage | Names randomised by `UniqueUploadNameProvider`; reads go through `protected_serve`, which loads the `FileUpload`, finds its parent object and calls `user_has_permission_or_403` (`dojo/views.py:118-130`). |
| 15 | Media -> Pillow decode | **Nothing validates content.** Pillow picks the decoder from file bytes. See the trust finding below. |
| 16 | Worker -> JIRA | Credentials from `Tool_Configuration`, encrypted with a key derived from `DD_CREDENTIAL_AES_256_KEY`. Server certificate validation is the HTTP library's default. |
| 17 | Worker -> notification webhooks | `Notification_Webhooks.url` is a plain `URLField`; the request is sent with `requests.request(url=...)` (`notifications/helper.py:552`) with no private-address filter. Creation is restricted to superusers (`notifications/ui/views.py:34`), which limits but does not remove the SSRF exposure. |
| 18 | JIRA -> `/jira/webhook/<secret>` | Unauthenticated route. Validated by: JIRA integration and webhook enabled, secret in the URL path compared with `!=` (not constant-time) against the system setting, `application/json`, JSON parse, event whitelist (`dojo/jira/views.py:54-100`). The secret check can be switched off (`disable_jira_webhook_secret`). |
| 19 | IdP -> SAML/OAuth callback | Delegated to the third-party auth libraries. Not audited by me. |
| 20 | Registries -> build | Python pins use `==` without hashes; GitHub Actions are pinned to commit SHAs (`release-2-tag-docker-push.yml:22`); base image pinned by digest (`Dockerfile.django-debian:8`). |
| 21 | CI -> Docker Hub | No signing or attestation step (Part 6). |

### Findings, stated plainly

- **Nothing validates** attachment content (9, 15), the default rate limit does nothing (1, 2), and the API token ignores the reset state (2, 5). Crossing 17 has no private-address check.
- **Default secrets.** `DD_CREDENTIAL_AES_256_KEY` defaults to `"."` (`settings.dist.py:158`) and `docker-compose.yml:55` ships a fixed public default for both it and `DD_SECRET_KEY`. Anyone who deploys the compose file unchanged encrypts stored integration passwords (`dojo/utils.py:1029`) with a key published in the repository. I did not change this; see Part 7.

### Where the project trusts something it should verify

**The filename extension at crossing 9, as a stand-in for file type.** Upload validation (`file_uploads/models.py:66`) and image detection (`utils.py:1780`) both trust the name the user chose. Pillow, further downstream, trusts the bytes. The two disagree whenever a user renames a file, and the decoder sees whatever the attacker built. If the trust is wrong, an attacker obtains memory disclosure or a worker crash through the image-rendering path (Misuse Case B) instead of being rejected at upload.

---

## Part 4: Threat Model

### Risk 1: API token outlives credential recovery

- **Asset:** a user's API token (a bearer credential).
- **STRIDE:** Spoofing (the attacker acts as the user).
- **OWASP Top 10 (2021):** A07 Identification and Authentication Failures.
- **Likelihood: medium.** Password reuse is common and the token endpoint is not throttled by default (crossing 2). **Impact: medium.** The attacker has that user's permissions, not more.
- **Mitigation:** the lifecycle of a token must be owned by the user model, not by individual views. The control belongs where credentials change: `dojo/user/models.py` (`Dojo_User`) so that every path that changes a password or ends a forced reset revokes the token, instead of only `change_password` in `dojo/user/ui/views.py`. I implemented the narrow slice in the view (Part 7) and recommend moving it into a model method or `post_save` signal so the email-reset path and admin resets are covered too. Also set `TokenAuthentication` expiry.

### Risk 2: Cross-product authorization gaps

- **Asset:** findings, notes, and stored integration credentials belonging to products the caller is not a member of.
- **STRIDE:** Information disclosure (also Elevation of privilege for write paths).
- **OWASP:** A01 Broken Access Control.
- **Likelihood: high.** The project has published dozens of this class in 2026 alone (Part 5). **Impact: medium** (CVSS vectors on the ones I read are `C:L`, but the data is vulnerability details).
- **Mitigation:** enforce at the queryset layer (`dojo/authorization/query_filters.py`, `query_registrations.py`) and in one shared serializer guard (`dojo/authorization/serializer_guards.py`) so a view or serializer cannot reach an object without passing through them. Per-view `user_has_permission_or_403` calls are the wrong owner because each new view must remember to add one. The existing meta-tests (`unittests/test_authorization_queryset_coverage.py`) already point this way.

### Risk 3: Untrusted file content reaches native decoders

- **Asset:** the web worker process memory and availability.
- **STRIDE:** Information disclosure (heap bytes in thumbnails) and Denial of service (decoder crash).
- **OWASP:** A06 Vulnerable and Outdated Components, with A04 Insecure Design for trusting the extension.
- **Likelihood: medium** (needs an upload permission and a viewer; the Pillow bug is real, my exploitability analysis is not tested). **Impact: medium-high** (process memory, and workers are shared across all products).
- **Mitigation:** validate content at the upload boundary in `FileUpload.clean()` (`dojo/file_uploads/models.py`), because that is the one place every upload path (UI, API, import) already passes through. Keep image decoding in `download_finding_pic` restricted to expected formats. Raise `Pillow` to >=13.0.0 in `requirements.txt`. Validating in the template or in the view would miss the API upload path.

---

## Part 5: Security Bug History

DefectDojo publishes GitHub security advisories; I listed them with `gh api repos/DefectDojo/django-DefectDojo/security-advisories`.

### Issue 1: stored integration credentials usable across products - [GHSA-mq99-2cr2-xww9](https://github.com/DefectDojo/django-DefectDojo/security/advisories/GHSA-mq99-2cr2-xww9), follow-up [GHSA-v43c-xr7j-vh82](https://github.com/DefectDojo/django-DefectDojo/security/advisories/GHSA-v43c-xr7j-vh82)

- **What it was.** A product member could select any tool configuration on the instance, including admin-created ones for other products, when adding an API scan configuration. Saving made the server authenticate to the third-party system with that credential. Affected versions `<= 3.1.303`, fixed in 3.1.305; CWE-862/863; CVSS vector `AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N`.
- **Architectural root cause.** Authorization attached to *views*, while the data the view accepted (a foreign key to a credential) was never checked against the caller. The server used its own stored authority on the caller's behalf (a confused deputy). Any writer of the field was unprotected.
- **Narrow or structural?** Narrow first. Fix PR #15445 touched five files (`product/api/serializer.py`, `product/ui/forms.py`, `product/ui/views.py`, `tool_config/queries.py`, plus a test): it scoped the choices on one field in a few writers. The second advisory, GHSA-v43c, states "That fix reached only part of the affected surface" and that it stayed reachable through 3.2.100. The structural fix, PR #15650, added `dojo/authorization/serializer_guards.py` and applied "a shared guard ... to every writer of the affected field". (I read the PR file lists through `gh pr view`, not the diffs.) The same class can reappear on any other foreign key a user can set to an object they cannot see.
- **OWASP:** A01 Broken Access Control.

### Issue 2: API token remained valid after forced password reset - [GHSA-66vh-fm67-46vw](https://github.com/DefectDojo/django-DefectDojo/security/advisories/GHSA-66vh-fm67-46vw)

- **What it was.** An attacker who knew a password could obtain an API token and keep using it after the user completed a forced reset. Affected `>= 2.1.0, <= 3.3.100`, fixed 3.3.200; CWE-613 (insufficient session expiration); CVSS `AV:N/AC:H/PR:L/UI:N/S:U/C:L/I:L/A:N`.
- **Architectural root cause.** Two authentication mechanisms with different lifecycles. The session path honours the forced-reset state (`middleware.py:109`); the API path authenticates by a long-lived bearer token that is independent of the password. Credential state and token state are separate records with nothing tying them together.
- **Narrow or structural?** The advisory describes the fix as revoking the token when a forced reset completes and not issuing one while a reset is pending, merged as PR #15954 (files: `dojo/user/models.py`, `api/serializer.py`, `api/views.py`, `dojo/urls.py`, plus a test). That ties the token to the reset state, which is a modest structural fix, but it addresses *forced resets only*. A voluntary password change or an administrator password change by other paths is the same class and, as far as I read, not covered.
- **OWASP:** A07 Identification and Authentication Failures.
- **Note.** This checkout (3.2.300) predates that fix, which is why I used it for Part 7. I confirmed the fix is absent here: `change_password` did not touch tokens and `dojo/user/models.py` had no token handling.

---

## Part 6: Supply Chain and Dependency Analysis

### SBOM

`class-docs/sbom.json`, CycloneDX 1.6, generated by tools, not by hand:

- Python: `cyclonedx-py environment` (cyclonedx-bom 7.5.0) over a clean virtualenv installed from `requirements.txt` (without `uWSGI`, which needs a compiler toolchain). The venv's own `pip` is removed from the list.
- JavaScript: `@cyclonedx/cdxgen` over `components/` (`yarn.lock`).
- The two outputs were merged with a short script. I used these tools rather than Syft because Syft was not installable here (`brew install syft osv-scanner` failed on this macOS release).

**Two numbers.**

| | Count |
|---|---|
| Declared directly | **105** = 65 Python (`requirements.txt`) + 37 JS runtime + 3 JS dev (`components/package.json`) |
| Packages in the SBOM | **300** = 133 Python + 167 JS |

The gap exists because every direct dependency drags in its own dependencies (Celery alone brings kombu, billiard, vine, amqp and more) and the SBOM records the whole resolved tree.

### Known vulnerabilities

I ran `pip-audit --path <venv>/site-packages` for Python (36 distinct advisory IDs across six runtime packages: Django 2, djangorestframework 2, GitPython 7, Pillow 8, PyJWT 14, urllib3 3) and queried the OSV API with every npm purl from the SBOM (four packages: bootstrap 3.4.1, braces 3.0.3, moment 2.30.1, source-map-js 1.2.1). The three I read in full:

| Advisory | Package and range | Breaks | Reachable? |
|---|---|---|---|
| [GHSA-c6hw-5grf-ff96 / CVE-2026-112404](https://github.com/advisories/GHSA-c6hw-5grf-ff96) (high) | Pillow `>= 8.1.0, < 13.0.0` (repo pins 12.3.0), fixed 13.0.0 | Confidentiality (heap bytes in output pixels), also availability (crash) | **Yes** |
| [GHSA-g47c-3xmw-q6m2 / CVE-2026-73229](https://github.com/advisories/GHSA-g47c-3xmw-q6m2) (medium) | djangorestframework `<= 3.17.1`, fixed 3.17.2 | Confidentiality | **No** |
| [GHSA-q238-5cxm-5c9h / CVE-2026-15830](https://github.com/advisories/GHSA-q238-5cxm-5c9h) (medium) | Django `< 5.2.17` (repo pins 5.2.16) | Availability | **No** |

Also read: [GHSA-4p3w-j4w9-5jqw](https://github.com/advisories/GHSA-4p3w-j4w9-5jqw) (moment, path traversal via locale name, fixed 2.31.0), [GHSA-q58r-hwc8-rm9j](https://github.com/advisories/GHSA-q58r-hwc8-rm9j) and [GHSA-vxmc-5x29-h64v](https://github.com/advisories/GHSA-vxmc-5x29-h64v) (Bootstrap 3.4.1 XSS; the API shows no patched version, because Bootstrap 3 is end of life).

### Reachability

- **Pillow: reachable.** Call path: attachment upload (`FileUpload`, extension-only validation, `file_uploads/models.py:66`) -> finding page template -> `pic_token` (`display_tags.py:511`) -> route `finding/image/<token>` (`finding/ui/urls.py:153`) -> `download_finding_pic` (`finding/ui/views.py:2250`) -> `ImageSpec.generate()` (imagekit, which calls `PIL.Image.open`). Pillow chooses the TIFF decoder from file content, so a TIFF named `.png` passes upload validation. I traced the path by reading; I did not run an exploit.
- **DRF `AdminRenderer`: not reachable.** `DEFAULT_RENDERER_CLASSES` is `JSONRenderer` only (`settings.dist.py:712-714`) and `grep AdminRenderer dojo/` finds no use. The package is in the tree; the feature is off.
- **Django GeoDjango: not reachable.** `grep django.contrib.gis dojo/` returns nothing; GIS is not an installed app.
- I did **not** trace the PyJWT advisories: `dojo/` has no `import jwt`, so any use would be through another dependency, which I did not follow.

### Provenance

- **In place:** third-party Actions pinned to commit SHAs (e.g. `release-2-tag-docker-push.yml:22`); base image pinned by digest (`Dockerfile.django-debian:8`); Python versions pinned with `==` (no hashes); Renovate and Dependabot configs under `.github/`.
- **Missing:** a search of `.github/workflows` for `cosign`, `attest`, `sigstore`, `slsa`, `provenance`, `sbom` returned no hits. The latest upstream release (3.4.201) lists only `defectdojo-1.9.59.tgz`, `oas.json`, `oas.yaml`, `schema-snapshot.manifest.json`, `schema-snapshot.sql` as assets, with no `.sig` or `.intoto.jsonl`. So a user downloading a release artifact today **cannot prove** it was built from the commit it names. I did not check whether `docker/build-push-action` attaches default BuildKit provenance to the pushed images; that is unverified.

### OWASP mapping

- **A06 Vulnerable and Outdated Components:** Pillow 12.3.0, GitPython 3.1.58, PyJWT 2.13.0, urllib3 2.7.0, Django 5.2.16 behind current fixes, plus Bootstrap 3.4.1 (no upstream fix at all).
- **A08 Software and Data Integrity Failures:** no signatures or attestations on releases; no hash pinning of Python dependencies; `django-tagulous` is installed from a pinned commit of a personal fork (`requirements.txt`, `git+https://github.com/valentijnscholten/...@2b514f9`), which is a deliberate and documented choice but is an integrity dependency on one individual's repository.

### Recommendation

Add keyless Sigstore signing and a build-provenance attestation to the release workflow that pushes images (`release-2-tag-docker-push.yml` and `release-x-manual-merge-container-digests.yml`, signing the final merged manifest digest) using `actions/attest-build-provenance` or `cosign sign`. **Cost:** a job-level `id-token: write` and `attestations: write` permission, a few extra CI minutes per release, and documentation so users run `cosign verify` / `gh attestation verify`. There are no long-lived keys to manage, because signing is tied to the workflow identity. The maintainers' ongoing cost is keeping the signing step working when the merge-digest flow changes.

---

## Part 7: Implement One Control

**Control.** Revoke the user's API token when a forced password reset completes, in the `change_password` view. Commit [`6b5ef59`](https://github.com/tlmcguire/django-DefectDojo/commit/6b5ef59a6de24a5ad9004ad1f545f96f1292d2d1).

**Closes:** Misuse Case A and threat model Risk 1. **Defends:** crossing 5 (API client -> `/api/v2/`), by making a token issued before a reset stop authenticating after it. It is also the follow-through for crossing 2.

### Before (`dojo/user/ui/views.py`, parent commit)

```python
249            new_password = form.cleaned_data["new_password"]
250
251            user.set_password(new_password)
252            user.disable_force_password_reset()
253            user.save()
```

### After (`dojo/user/ui/views.py`)

```python
249            new_password = form.cleaned_data["new_password"]
250
251            # A forced reset means the old password may be known to someone else (admin
252            # flag or brute-force lockout). Any API token minted with it must not outlive
253            # the reset, or the old credential keeps working through the API.
254            was_forced_reset = Dojo_User.force_password_reset(user)
255
256            user.set_password(new_password)
257            user.disable_force_password_reset()
258            user.save()
259            if was_forced_reset:
260                Token.objects.filter(user=user).delete()
```

(`Token` was already imported at `views.py:26`.) New test file: `unittests/test_forced_password_reset_revokes_api_token.py` (2 tests).

**Why this component.** `change_password` is the only caller of `disable_force_password_reset()` in the repository (`grep` finds one), and is the single place where "a forced reset completed" is observable. Revoking only when the flag *was* set means a voluntary password change does not log the user out of their CI jobs (the second test checks this). The better long-term home is `Dojo_User` itself, so every credential-change path inherits it; I kept the commit to the smallest slice.

**Verification.** Docker was not running, so `./run-unittest.sh` was not used. I instead ran Django's runner locally against a throwaway PostgreSQL (the repo requires `pghistory`/`pgtrigger`):

```
python manage.py test unittests.test_forced_password_reset_revokes_api_token \
  unittests.test_user_ui_timestamps unittests.test_apiv2_user \
  unittests.test_user_ui_identity_authz unittests.test_user_validators --noinput
Ran 37 tests in 5.702s
OK
```

Without the fix, the new test failed (`AssertionError: True is not false`, token still present); with it, it passes. `ruff check --config ruff.toml` passed on both changed files. I did **not** run the whole suite, the integration tests, or a Docker image build.

**What it does not fix.**

- The token endpoint still issues tokens **while a reset is pending**, and `TokenAuthentication` ignores `force_password_reset` entirely (the middleware guard at `middleware.py:109` is session-only). Between the moment the flag is set and the moment the reset completes, an attacker holding the old password can still mint and use tokens; only tokens existing at completion are now revoked.
- Other credential changes (administrator password change, email-link reset via `DojoPasswordResetConfirmView`) do not revoke tokens.
- Tokens still never expire, and rate limiting is still off by default.
- The default-key problem (`DD_CREDENTIAL_AES_256_KEY` = `"."`, public compose default) is untouched. I considered failing startup on that default but `Dockerfile.nginx-alpine:67` runs `collectstatic` with no key set, so the change would have broken the image build and needed more than one commit.

---

## Part 8: Present in Class (talking points)

1. **Diagram and misuse case:** show the misuse diagram; walk Misuse Case A (token survives the reset), steps 1, 5, 6.
2. **First mitigation:** tie token lifetime to credential state in `Dojo_User` (`dojo/user/models.py`), not in each view.
3. **Dependency risk:** Pillow CVE-2026-112404 is reachable via `download_finding_pic`; the DRF and GeoDjango advisories are in the tree but not reachable.
4. **Control:** open `6b5ef59`; it defends crossing 5.

---

## AI Use Log

**Tool:** Claude Code (Anthropic), run in this clone at `/Users/tyler/Projects/django-DefectDojo` on branch `coursework/a8-design-patterns` (cut from `master`; the repo's `AGENTS.md` flags `master` for release work only, and this is coursework in my fork, not a patch for upstream).

**What I asked it to do, and what it did:**

1. Read the assignment `.docx` and the earlier write-ups for the house format.
2. Read the code for the boundary crossings (settings, middleware, `dojo/jira/views.py`, uploads, notifications, nginx config) and chose the control by finding a real gap: the upstream advisory GHSA-66vh-fm67-46vw was not fixed in this checkout.
3. Listed upstream advisories with `gh api` and read the full text of every advisory cited above.
4. Built a virtualenv, generated the SBOM with `cyclonedx-py` and `cdxgen`, ran `pip-audit` and an OSV query.
5. Implemented the control with a test, confirmed the test fails without the fix, committed it; then wrote this page and the two diagram sources.

**Honest limits, not smoothed over:**

- **Not run:** Docker, `run-unittest.sh`, the integration suite, or the full test suite. Only 37 related tests ran, against a temporary local PostgreSQL.
- **Diagrams not rendered.** PlantUML was not installed; the Mermaid source was not rendered. Both were checked by reading.
- **Syft and osv-scanner were not used** (brew install failed); equivalent tools were. The SBOM is a merge of two tool outputs.
- **The Pillow reachability chain is traced by reading code and the advisory, not exploited.**
- **Fix PR contents (#15445, #15650, #15954)** were read as file lists only, not diffs.
- **Some claims are unverified:** XXE safety of the direct `lxml`/`xml.etree` parsers, whether pushed images already carry default BuildKit provenance, TLS to the database, and the PyJWT call paths.
- The advisory dates and numbers in this simulated timeline come straight from the GitHub API at the time of writing; re-check them before class.
- The analysis and code were written by the AI and need my review. The assignment says I will be asked in class why the control sits in `change_password` rather than the model; I should be able to answer that from Part 7 before I present.
