# MaterialHub

MaterialHub is a Flask-based web application for managing material requisitions, purchase orders, quality control, deliveries, warehouse operations, supplier marketplace, and tenders.

## Features

- Role-based access (Project Manager, Engineering, Purchase, Quality, Delivery, Warehouse, Supplier)
- Material Requisition workflow with approvals
- Purchase Orders linked to requisitions
- Quality Control inspections
- Delivery tracking
- Warehouse inventory management
- Supplier Material Marketplace
- Tender & Bid system
- Two-factor authentication (TOTP)
- Basic inventory & delivery risk analysis

## Project Structure

```
MaterialHub/
├── blueprints/          # Blueprint modules
├── config/              # Configuration
├── data/                # Static data (country codes)
├── forms/               # WTForms
├── static/              # CSS, JS, images
├── templates/           # Jinja2 templates
├── instance/            # Runtime data (not in git)
├── ai_analysis.py       # Simple rule-based analysis
├── app.py               # Application factory
├── models.py            # SQLAlchemy models
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Quick Start (Local Development)

1. **Clone the repository**
   ```bash
   git clone https://github.com/Tahmoures54/MaterialHub.git
   cd MaterialHub
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate          # Linux / macOS
   # venv\Scripts\activate           # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set a strong SECRET_KEY
   ```

5. **Run the application**
   ```bash
   python app.py
   ```
   Open http://127.0.0.1:5000

## Docker (Recommended for Production-like Environment)

```bash
cp .env.example .env
# Set SECRET_KEY in .env

docker-compose up --build
```

The app will be available at http://localhost:5000  
PostgreSQL runs on port 5432.

## Environment Variables

| Variable       | Required | Description                              |
|----------------|----------|------------------------------------------|
| SECRET_KEY     | Yes      | Flask secret key                         |
| DATABASE_URL   | No       | PostgreSQL URL (falls back to SQLite)    |
| FLASK_ENV      | No       | `development` or `production`            |
| LOG_LEVEL      | No       | Logging level (default: INFO)            |
| ADMIN_EMAIL    | No       | Email that becomes admin on registration |

## Database Migration (Flask-Migrate)

```bash
flask db init          # only once
flask db migrate -m "Initial migration"
flask db upgrade
```

## Security Notes

- Never commit `.env` or recovery codes.
- Always use a strong random `SECRET_KEY` in production.
- Prefer PostgreSQL over SQLite for any real deployment.
- TOTP (2FA) is required for login.

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Open a Pull Request

## License

Proprietary / All rights reserved (update as needed).
