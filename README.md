# MaterialHub

**MaterialHub** is a Flask-based web application for managing the full material supply chain in engineering and industrial projects.

It covers material requisitions, purchase orders, quality control, deliveries, warehouse operations, supplier marketplace, and tenders — with role-based access and two-factor authentication.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-v1.0.0-success)

---

## Features

- **Role-based access control**  
  Project Manager · Engineering · Purchase · Quality · Delivery · Warehouse · Supplier

- **Material Requisition** workflow with approvals  
- **Purchase Orders** linked to requisitions  
- **Quality Control** inspections  
- **Delivery** tracking  
- **Warehouse** inventory management  
- **Supplier Material Marketplace**  
- **Tender & Bid** system  
- **Two-factor authentication** (TOTP / Microsoft Authenticator)  
- Basic inventory & delivery risk analysis  

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Tahmoures54/MaterialHub.git
cd MaterialHub
```

### 2. Virtual Environment

```bash
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment

```bash
cp .env.example .env
```

Edit `.env` and set a strong `SECRET_KEY`:

```env
SECRET_KEY=your-very-long-random-secret-key
FLASK_ENV=development
```

Generate a secure key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Run

```bash
python app.py
```

Open → [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Docker (Recommended)

```bash
cp .env.example .env
# Set SECRET_KEY in .env

docker-compose up --build
```

- App: http://localhost:5000  
- PostgreSQL: port 5432

---

## Environment Variables

| Variable     | Required | Description                                      |
|--------------|----------|--------------------------------------------------|
| SECRET_KEY   | **Yes**  | Flask secret key                                 |
| DATABASE_URL | No       | PostgreSQL URL (defaults to SQLite)              |
| FLASK_ENV    | No       | `development` or `production`                    |
| LOG_LEVEL    | No       | `DEBUG` / `INFO` / `WARNING` / `ERROR`           |
| ADMIN_EMAIL  | No       | Email that becomes admin on registration         |

---

## Project Structure

```
MaterialHub/
├── blueprints/          # Feature modules
├── config/              # App configuration
├── data/                # Static data (country codes)
├── forms/               # WTForms
├── static/              # CSS, JS, images
├── templates/           # Jinja2 templates
├── ai_analysis.py       # Rule-based analysis helpers
├── app.py               # Application factory
├── models.py            # SQLAlchemy models
├── extensions.py        # Flask extensions
├── utils.py             # Shared helpers
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Database Migrations

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

---

## Security Notes

- Never commit `.env` or recovery codes.
- Always use a strong random `SECRET_KEY` in production.
- Prefer PostgreSQL for any real deployment.
- TOTP (2FA) is required for login.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository  
2. Create a feature branch (`git checkout -b feature/your-feature`)  
3. Commit your changes  
4. Open a Pull Request  

---

**MaterialHub v1.0.0** — Ready for use and further development.

## Documentation & Template Architecture

The UI templates are now organized by business domain instead of a single flat folder:

- `templates/auth/` — authentication and account pages
- `templates/dashboard/` — home, control center and role dashboards
- `templates/procurement/` — requisitions, marketplace, RFQ/tender, quotes and purchase orders
- `templates/warehouse/` — inventory, delivery and warehouse execution
- `templates/quality/` — quality control
- `templates/intelligence/` — traceability, Excel import and material intelligence
- `templates/reports/` — reporting pages
- `templates/admin/` — administration
- `templates/help/` — Help Center, User Guide, Getting Started and About
- `templates/legal/` — privacy and terms
- `templates/support/` — support contact
- `templates/errors/` — 404/500 pages

### In-app documentation
- `/help` — Help Center
- `/getting-started` — quick onboarding
- `/user-guide` — complete operating guide
- `/about` — product overview

The same documentation is also available in `docs_USER_GUIDE.md` and `PRODUCT_OVERVIEW.md`.
