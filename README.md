# MaterialHub

**MaterialHub** is a Flask-based web application for managing the full material supply chain in engineering and industrial projects.

It covers material requisitions, purchase orders, quality control, deliveries, warehouse operations, supplier marketplace, and tenders — with role-based access and two-factor authentication (TOTP).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-v1.1.0-success)

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
- Rule-based inventory & delivery risk analysis  
- Docker + PostgreSQL ready  
- Basic test suite (pytest)

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

### 5. Run (Development)

```bash
python app.py
```

Open → [http://127.0.0.1:5000](http://127.0.0.1:5000)

### 6. Run Tests

```bash
pytest -v
```

---

## Docker (Recommended for production-like environment)

```bash
cp .env.example .env
# Set a strong SECRET_KEY in .env

docker-compose up --build
```

- App: http://localhost:5000  
- PostgreSQL: port 5432

The Docker setup uses Gunicorn + PostgreSQL with health checks.

---

## Environment Variables

| Variable     | Required | Description                                      |
|--------------|----------|--------------------------------------------------|
| SECRET_KEY   | **Yes**  | Flask secret key (must be strong & random)       |
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
├── tests/               # Pytest suite
├── ai_analysis.py       # Rule-based analysis helpers
├── app.py               # Application factory
├── wsgi.py              # Production WSGI entrypoint
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
flask db init          # only first time
flask db migrate -m "Your message"
flask db upgrade
```

For production always prefer PostgreSQL via `DATABASE_URL`.

---

## Security Notes

- **Never** commit `.env`, recovery codes, or private keys.
- Always use a strong random `SECRET_KEY` in production.
- Prefer PostgreSQL for any real deployment.
- TOTP (2FA) is required for login.
- Session cookies are HttpOnly + SameSite=Lax (Secure in production).

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

**MaterialHub v1.1.0** — Improved security, Docker, tests and analysis helpers.
