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
│   │   ├── services/       # Modular services (Mapbox provider, weather, risk scoring)
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
| `MAPBOX_ACCESS_TOKEN` | *(none)* | Mapbox public/secret token for Directions & Geocoding APIs. |

### Mapbox Account & Token Setup

1. Sign up for a free Mapbox account at [mapbox.com](https://www.mapbox.com/).
2. Navigate to your Mapbox Account Dashboard and copy your default public token (starts with `pk.`).
3. Add the token to your local `.env` file:
   ```bash
   MAPBOX_ACCESS_TOKEN=pk.your_actual_token_here
   ```
4. Never commit `.env` or share this token publicly. Automated tests use mocked HTTP responses and do not require a real token.


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
- **Description**: Validates route request parameters, resolves locations (via Mapbox Geocoding if text), and obtains real driving routes via the Mapbox Directions API (`v5/mapbox/driving`).

#### Request Schema

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `origin` | String or Object | **Yes** | Starting location as a text query or coordinate pair. | `"Chicago, IL"` or `{"latitude": 41.8781, "longitude": -87.6298}` |
| `destination` | String or Object | **Yes** | Ending location as a text query or coordinate pair. | `"Dallas, TX"` or `{"latitude": 32.7767, "longitude": -96.7970}` |
| `departure_datetime` | String (ISO 8601) | **Yes** | Scheduled departure timestamp. | `"2026-10-30T08:00:00Z"` |
| `load_weight_lb` | Float | **Yes** | Truck cargo load weight in pounds (> 0). | `35000.0` |

##### Supported Location Formats for `origin` and `destination`:
1. **Text Query**: `"Chicago, IL"` or `"123 Main St, Springfield"` (geocoded automatically via Mapbox Geocoding)
2. **Coordinate Object**: `{"latitude": 41.8781, "longitude": -87.6298}` (also accepts keys `lat` and `lon`/`lng`)
3. **Coordinate String**: `"41.8781, -87.6298"`
4. **Coordinate Array**: `[41.8781, -87.6298]`

#### Validation Rules & Error Responses

| Status Code | Code | Reason |
| :--- | :--- | :--- |
| `400 Bad Request` | `validation_error` | Missing required fields, non-positive `load_weight_lb`, invalid ISO datetime, out-of-range coordinates, or identical origin/destination. |
| `400 Bad Request` | `geocoding_failed` | Location text query could not be resolved to valid geographic coordinates. |
| `404 Not Found` | `no_route_found` | No drivable route found between coordinates (e.g. islands or unnavigable terrain). |
| `429 Too Many Requests` | `rate_limit_exceeded` | Upstream Mapbox API rate limit reached. |
| `502 Bad Gateway` | `provider_auth_error` / `provider_connection_error` | Mapbox token rejected or network failure connecting to provider. |
| `503 Service Unavailable` | `provider_not_configured` | Server environment is missing `MAPBOX_ACCESS_TOKEN`. |
| `504 Gateway Timeout` | `provider_timeout` | Request to Mapbox timed out. |

#### Response Schema & Units

- **Distance**: Represented in kilometers (`distance_km`) and miles (`distance_miles`).
- **Duration**: Represented in integer seconds (`duration_seconds`) and formatted display string (`duration_formatted`, e.g. `"14h 20m"`).
- **Geometry**: GeoJSON `LineString` with coordinate pairs `[[longitude, latitude], ...]`.
- **Alternatives**: Requests alternatives where supported, returning up to three distinct routes when provided. Does not fabricate extra alternatives if fewer are returned.

```json
{
  "status": "planned",
  "message": "Routes successfully calculated via Mapbox Directions API. Note: Routes reflect standard driving directions and do not yet account for truck restrictions (height/weight limits), weather hazards, or road closures.",
  "request_summary": {
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": 35000.0
  },
  "routes": [
    {
      "route_id": "mapbox-route-1",
      "display_name": "Primary Route (via I-55 S, I-30 W)",
      "distance_km": 1488.5,
      "distance_miles": 924.9,
      "duration_seconds": 50400,
      "duration_formatted": "14h 0m",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-87.6298, 41.8781],
          [-90.1994, 38.6270],
          [-96.7970, 32.7767]
        ]
      },
      "checkpoints": [
        {
          "sequence": 1,
          "name": "Departure: Chicago, IL",
          "latitude": 41.8781,
          "longitude": -87.6298,
          "estimated_arrival": "2026-10-30T08:00:00Z",
          "distance_from_origin_km": 0.0,
          "distance_from_origin_miles": 0.0,
          "duration_from_origin_seconds": 0,
          "weather": null,
          "risk_level": "unknown",
          "risk_summary": null
        },
        {
          "sequence": 2,
          "name": "Arrival: Dallas, TX",
          "latitude": 32.7767,
          "longitude": -96.7970,
          "estimated_arrival": "2026-10-30T22:00:00Z",
          "distance_from_origin_km": 1488.5,
          "distance_from_origin_miles": 924.9,
          "duration_from_origin_seconds": 50400,
          "weather": null,
          "risk_level": "unknown",
          "risk_summary": null
        }
      ],
      "weather_summary": {},
      "risk_assessment": {
        "overall_risk_level": "unknown",
        "risk_score": null,
        "risk_factors": [],
        "summary": "Weather hazard risk scoring is not yet integrated."
      },
      "recommendation": {
        "is_recommended": true,
        "status": "recommended",
        "explanation": "Primary route recommended by Mapbox based on shortest duration and road classification. Note: Reflects standard passenger driving profile; truck height/weight limits and weather conditions are not yet accounted for."
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

#### Provider Limitations & Road Routing Notice
> [!IMPORTANT]
> **Passenger Car Routing Only**: Routes are currently retrieved using the Mapbox `driving` profile. They **do not** account for commercial truck restrictions, including bridge weight limits, low clearances, truck-prohibited parkways, hazardous cargo restrictions, or road closures.
> **Weather Integration Pending**: Checkpoint weather observations and weather risk scoring are modular stubs under `backend/routing/services/` awaiting subsequent implementation steps.



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

