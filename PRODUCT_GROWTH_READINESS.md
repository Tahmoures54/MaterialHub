# MaterialHub Production & Growth Readiness

## Release goal
Move from a feature-rich application to a deployable product with a clear acquisition funnel.

## Delivered in this release
- Production `.env.example`; real `.env` removed from release.
- Production WSGI entrypoint.
- Liveness and readiness health endpoints.
- Role-aware workspace service moved to a package-safe top-level module.
- Defensive live KPI service.
- Landing page with clear positioning.
- Interactive demo page.
- Pricing / adoption page.
- Demo request contact page.
- Basic robots and sitemap assets.
- Updated gitignore for secrets and runtime artifacts.

## Product positioning
Material Operations Intelligence for Construction & EPC.

Core promise:
Know what you need. Know where it is. Know when it will arrive.

## Before public production launch
1. Configure PostgreSQL and run migrations.
2. Put secrets in the hosting provider's secret store.
3. Add HTTPS and a real domain.
4. Add error tracking and centralized logs.
5. Run the complete pytest + E2E suite in CI.
6. Configure database backups and restore drills.
7. Connect contact/demo requests to CRM/email.
8. Review authorization on every write endpoint.
9. Load-test the most-used dashboards and imports.
10. Seed a sanitized demo dataset.
