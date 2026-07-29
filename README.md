# MaterialHub

MaterialHub is a Flask-based web application for managing material requisitions, purchase orders, quality control, deliveries, and warehouse operations.

## Project Structure

```
MaterialHub/
├── blueprints/          # Blueprint modules for different app sections
├── config/              # Configuration settings
├── data/                # Static data (e.g., country codes)
├── forms/               # WTForms for input validation
├── static/              # Static files (CSS, JS, images)
├── templates/           # HTML templates
├── instance/            # SQLite database
├── ai_analysis.py       # AI analysis logic
├── app.py               # Main application entry point
├── errors.py            # Error handling
├── models.py            # SQLAlchemy models
├── utils.py             # Utility functions
├── requirements.txt     # Python dependencies
```

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd MaterialHub
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scriptsctivate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**:
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your-secret-key
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

   The app will be available at `http://0.0.0.0:5000`.

## Dependencies

- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- Flask-Bcrypt
- Flask-CORS
- Flask-WTF
- python-dotenv
- pyotp
- qrcode
- Pillow
- phonenumbers

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m 'Add your feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.
