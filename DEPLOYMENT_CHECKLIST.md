# Production Deployment Checklist

- [ ] Copy `.env.example` to `.env` only on the server.
- [ ] Generate a new production SECRET_KEY.
- [ ] Set a real PostgreSQL DATABASE_URL.
- [ ] Set POSTGRES_PASSWORD outside source control.
- [ ] Run database migrations before starting web workers.
- [ ] Put HTTPS in front of Gunicorn.
- [ ] Configure `/health/live` and `/health/ready`.
- [ ] Configure automated PostgreSQL backups.
- [ ] Test restore from backup.
- [ ] Enable centralized logs and error tracking.
- [ ] Run `pytest -q`.
- [ ] Run browser E2E tests against staging.
- [ ] Verify role isolation with test accounts.
- [ ] Seed a sanitized demo project.
- [ ] Connect `/contact` to the real sales/CRM workflow.
- [ ] Verify email delivery.
- [ ] Verify rate limiting and CSRF.
- [ ] Verify all production secrets are absent from the release archive.
