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
│   ├── routing/            # Django app for routing & weather awareness
│   │   ├── services/       # Modular engine stubs (routing, weather, risk scoring)
│   │   ├── serializers.py  # Request & response validation serializers
│   │   ├── views.py        # API views (health check, route planning)
│   │   ├── urls.py         # App URL routing
│   │   └── tests.py        # Automated test suite
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
Run the Django test suite covering the health endpoint, route validation, error handling, CORS rules, and response schema contracts:
```bash
python manage.py test
```

---

## API Reference

### 1. Health Check Endpoint

- **Method**: `GET`
- **Path**: `/api/health/`
- **Description**: Returns the server operational status.
- **Response**:
  ```json
  {"status": "ok"}
  ```

---

### 2. Route Planning Endpoint

- **Method**: `POST`
- **Path**: `/api/routes/`
- **Description**: Validates route request parameters and returns a structured placeholder response until routing and weather services are integrated.

#### Request Schema

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `origin` | String or Object | **Yes** | Starting location as a text query or coordinate pair. | `"Chicago, IL"` or `{"latitude": 41.8781, "longitude": -87.6298}` |
| `destination` | String or Object | **Yes** | Ending location as a text query or coordinate pair. | `"Dallas, TX"` or `{"latitude": 32.7767, "longitude": -96.7970}` |
| `departure_datetime` | String (ISO 8601) | **Yes** | Scheduled departure timestamp. | `"2026-10-30T08:00:00Z"` |
| `load_weight_lb` | Float | **Yes** | Truck cargo load weight in pounds (> 0). | `35000.0` |

##### Supported Location Formats for `origin` and `destination`:
1. **Text Query**: `"Chicago, IL"` or `"123 Main St, Springfield"`
2. **Coordinate Object**: `{"latitude": 41.8781, "longitude": -87.6298}` (also accepts keys `lat` and `lon`/`lng`)
3. **Coordinate String**: `"41.8781, -87.6298"`
4. **Coordinate Array**: `[41.8781, -87.6298]`

#### Validation Rules & HTTP 400 Responses

- **Missing Location**: Returns `400 Bad Request` if `origin` or `destination` is absent, `null`, or blank.
- **Invalid Coordinates**: Returns `400 Bad Request` if latitude is not between `[-90, 90]` or longitude is not between `[-180, 180]`.
- **Invalid Date/Time**: Returns `400 Bad Request` if `departure_datetime` is missing, `null`, or not a valid ISO 8601 string.
- **Non-Positive Load Weight**: Returns `400 Bad Request` if `load_weight_lb` is `<= 0`, non-numeric, or missing.
- **Identical Locations**: Returns `400 Bad Request` if origin and destination resolve to the same location.

#### Response Schema

The response is designed to return up to three candidate route options with structured checkpoints, weather, and risk assessments:

```json
{
  "status": "not_implemented",
  "message": "Route planning request validated successfully. Routing engine, weather data integration, and hazard risk scoring are pending in future steps.",
  "request_summary": {
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": 35000.0
  },
  "routes": [
    {
      "route_id": "route-primary-id",
      "display_name": "Route Display Name",
      "distance_miles": 925.4,
      "duration_seconds": 51600,
      "duration_formatted": "14h 20m",
      "checkpoints": [
        {
          "sequence": 1,
          "name": "Waypoint Name",
          "latitude": 41.8781,
          "longitude": -87.6298,
          "estimated_arrival": "2026-10-30T08:00:00Z",
          "distance_from_origin_miles": 0.0,
          "duration_from_origin_seconds": 0,
          "weather": {
            "temperature": 45.0,
            "condition": "Clear",
            "wind_speed_mph": 12.0,
            "wind_gust_mph": 18.0,
            "precipitation_probability": 10.0,
            "visibility_miles": 10.0,
            "units": {
              "temperature": "°F",
              "wind_speed": "mph",
              "precipitation": "%",
              "visibility": "miles"
            }
          },
          "risk_level": "low",
          "risk_summary": "Safe conditions."
        }
      ],
      "weather_summary": {},
      "risk_assessment": {
        "overall_risk_level": "low",
        "risk_score": 15.0,
        "risk_factors": [],
        "summary": "Favorable route conditions."
      },
      "recommendation": {
        "is_recommended": true,
        "status": "recommended",
        "explanation": "Safest route with minimal weather risks."
      }
    }
  ]
}
```

#### Example Usage

**Valid Request:**
```bash
curl -i -X POST http://127.0.0.1:8000/api/routes/ \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": 35000.0
  }'
```

**Invalid Request (Validation Error):**
```bash
curl -i -X POST http://127.0.0.1:8000/api/routes/ \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Chicago, IL",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": -50
  }'
```
Response (`400 Bad Request`):
```json
{
  "destination": ["Destination location is required."],
  "load_weight_lb": ["Load weight must be a positive number greater than 0 pounds."]
}
```

#### Current Limitations
- **Route Calculation**: Third-party routing providers (e.g. OSRM, OpenRouteService) are not yet integrated. The endpoint returns `status: "not_implemented"` with an empty `routes: []` array.
- **Weather & Risk Engine**: Weather provider (Open-Meteo) and truck risk scoring engines are organized as modular service stubs under `backend/routing/services/` for subsequent implementation steps.


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

