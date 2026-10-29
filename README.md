# Weather-Aware Truck Routing

A full-stack application for weather-aware truck routing featuring a Django REST Framework backend and a React + Vite frontend.

---

## Project Structure

```text
├── .env.example            # Root environment variable template
├── .gitignore              # Root gitignore for environments, caches & builds
├── README.md               # Setup and development guide
├── backend/                # Django REST API
│   ├── .env.example        # Backend environment variable template
│   ├── .venv/              # Python virtual environment (ignored by git)
│   ├── backend/            # Django project configuration (settings.py, urls.py)
│   ├── routing/            # Django app (health check endpoint, tests, views)
│   ├── db.sqlite3          # Local SQLite database (ignored by git)
│   ├── manage.py           # Django CLI
│   └── requirements.txt    # Python dependencies (Django, DRF, CORS, dotenv)
└── frontend/               # React + Vite application
    ├── src/                # React source code
    ├── package.json        # Frontend dependencies and scripts
    └── vite.config.js      # Vite build configuration
```

---

## Prerequisites

- **Python**: 3.9+ (Installed: Python 3.9.6)
- **Node.js**: v18+ or v20+ (Installed: v26.10.0)
- **npm**: v9+ (Installed: 11.19.1)
- **Git**: 2.x

---

## Environment Configuration

Create a local `.env` file from the provided `.env.example` template:

```bash
# From the root directory or inside backend/
cp .env.example .env
```

The supported environment variables and their default development values:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | *(insecure dev fallback)* | Secret key for Django cryptographic signing. **Replace in production.** |
| `DJANGO_DEBUG` | `True` | Enables debug mode for local development. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma-separated list of allowed hostnames. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed for cross-origin frontend requests. |
| `DJANGO_DB_NAME` | `db.sqlite3` | SQLite database file name located under `backend/`. |

---

## Backend Setup (Django & DRF)

### 1. Navigate to the backend directory
```bash
cd backend
```

### 2. Activate the virtual environment
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```
- **Windows (Command Prompt / PowerShell)**:
  ```cmd
  .venv\Scripts\activate
  ```

> *Note: If creating a fresh virtual environment from scratch, run `python3 -m venv .venv` first.*

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run database migrations
Apply database schema migrations (creates local SQLite database):
```bash
python manage.py migrate
```

### 5. Start the Django development server
```bash
python manage.py runserver
```
The backend API will be available at: `http://127.0.0.1:8000/`

### 6. Verify Health Check Endpoint
Test the API endpoint using `curl` or open in your browser:
```bash
curl -i http://127.0.0.1:8000/api/health/
```
Expected response:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ok"}
```

Test with CORS origin header to verify frontend access:
```bash
curl -i -H "Origin: http://localhost:5173" http://127.0.0.1:8000/api/health/
```
Expected response headers include:
```http
access-control-allow-origin: http://localhost:5173
access-control-allow-credentials: true
```

### 7. Run Backend Tests
Run the Django test suite covering the health endpoint, JSON response, and CORS rules:
```bash
python manage.py test
```

---

## Frontend Setup (React + Vite)

### 1. Navigate to the frontend directory
```bash
cd frontend
```

### 2. Install dependencies
```bash
npm install
```

### 3. Start the Vite development server
```bash
npm run dev
```
The frontend application will be available at: `http://localhost:5173/`

### 4. Build for production (optional)
```bash
npm run build
```

---

## Next Steps

- Weather data integration (Open-Meteo or NWS / weather API provider)
- Routing and waypoint optimization engine
- Interactive map UI and route visualization

