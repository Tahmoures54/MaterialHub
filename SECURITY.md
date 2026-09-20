# Security Policy

## Reporting a vulnerability
Report suspected vulnerabilities privately through the project's established private communication channel or GitHub security reporting mechanism when available. Do not disclose security vulnerabilities publicly before assessment and remediation.

Include the affected component/route, reproducible steps, expected and actual behavior, security impact, and relevant logs with secrets and personal data removed.

## Secrets
Never commit SECRET_KEY, database passwords, API tokens, TLS private keys, TOTP secrets, Docker secret files or production .env files.
Use environment variables, Docker secrets or an external secret manager.

## Authentication
MaterialHub uses Argon2id for new password hashes. Legacy Werkzeug hashes are migrated after successful authentication. TOTP secrets written by the application are encrypted at rest. QR provisioning payloads must not be persisted. Authentication-sensitive routes are rate limited.

## Production configuration
Production must use PostgreSQL, disable Flask debug mode, use Gunicorn, use HTTPS, enable secure session cookies, use a strong SECRET_KEY, and configure Redis-backed rate limiting for multi-worker deployments.

## Tenant isolation
Queries returning business data must apply the appropriate company/tenant scope unless explicitly authorized as a cross-tenant administrative operation. New queries must include authorization and cross-tenant regression tests.

## File uploads and Excel
Treat uploaded spreadsheets as untrusted input. Validate file type, size, required columns, row count, field lengths, formats, duplicates and referential constraints. Do not execute macros or formulas as trusted code.

## Operational security
Monitor authentication failures, authorization failures, HTTP 4xx/5xx rates, readiness failures, database errors, resource exhaustion and dependency vulnerabilities.

## Incident response
1. Preserve relevant logs and timestamps.
2. Identify affected tenant(s) and data.
3. Contain the affected endpoint or credential.
4. Rotate compromised secrets.
5. Assess database and object-store impact.
6. Restore only from a verified clean backup when required.
7. Document root cause and corrective action.
8. Add a regression test for the failure mode.

## Security verification
Before production release, verify the complete login/2FA/RBAC flow against PostgreSQL and execute cross-tenant authorization tests with at least two isolated companies.