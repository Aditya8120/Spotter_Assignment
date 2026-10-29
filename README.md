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

### 2. Route Planning & Weather Integration Endpoint

- **Method**: `POST`
- **Path**: `/api/routes/`
- **Description**: Validates route request parameters, resolves locations (via Mapbox Geocoding if text), generates driving routes via Mapbox Directions API (`v5/mapbox/driving`), samples checkpoints at configurable intervals (10, 25, or 50 miles), and fetches hourly weather forecasts from Open-Meteo for each checkpoint's estimated arrival time.

#### Request Schema

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `origin` | String or Object | **Yes** | Starting location as a text query or coordinate pair. | `"Chicago, IL"` or `{"latitude": 41.8781, "longitude": -87.6298}` |
| `destination` | String or Object | **Yes** | Ending location as a text query or coordinate pair. | `"Dallas, TX"` or `{"latitude": 32.7767, "longitude": -96.7970}` |
| `departure_datetime` | String (ISO 8601) | **Yes** | Scheduled departure timestamp. | `"2026-10-30T08:00:00Z"` |
| `load_weight_lb` | Float | **Yes** | Truck cargo load weight in pounds (> 0). | `35000.0` |
| `checkpoint_interval_miles` | Integer | **No** | Sampling interval along route geometry (`10`, `25`, or `50` miles). Default is `25`. | `25` |

##### Supported Location Formats for `origin` and `destination`:
1. **Text Query**: `"Chicago, IL"` or `"123 Main St, Springfield"` (geocoded automatically via Mapbox Geocoding)
2. **Coordinate Object**: `{"latitude": 41.8781, "longitude": -87.6298}` (also accepts keys `lat` and `lon`/`lng`)
3. **Coordinate String**: `"41.8781, -87.6298"`
4. **Coordinate Array**: `[41.8781, -87.6298]`

#### Validation Rules & Error Responses

| Status Code | Code | Reason |
| :--- | :--- | :--- |
| `400 Bad Request` | `validation_error` | Missing required fields, non-positive `load_weight_lb`, invalid ISO datetime, out-of-range coordinates, invalid `checkpoint_interval_miles` (must be 10, 25, or 50), or identical origin/destination. |
| `400 Bad Request` | `geocoding_failed` | Location text query could not be resolved to valid geographic coordinates. |
| `404 Not Found` | `no_route_found` | No drivable route found between coordinates (e.g. islands or unnavigable terrain). |
| `429 Too Many Requests` | `rate_limit_exceeded` | Upstream Mapbox API rate limit reached. |
| `502 Bad Gateway` | `provider_auth_error` / `provider_connection_error` | Mapbox token rejected or network failure connecting to provider. |
| `503 Service Unavailable` | `provider_not_configured` | Server environment is missing `MAPBOX_ACCESS_TOKEN`. |
| `504 Gateway Timeout` | `provider_timeout` | Request to Mapbox timed out. |

---

### Weather Integration (Open-Meteo Forecast API)

The backend integrates with the **Open-Meteo Forecast API** (`https://api.open-meteo.com/v1/forecast`) using a modular weather engine (`OpenMeteoWeatherService`).

#### Key Features & Implementation Details:
- **No API Key Required**: Open-Meteo's standard forecast API operates openly without requiring API keys or exposing secrets.
- **Estimated Arrival Time Matching**: Weather forecasts are matched to each checkpoint using its **estimated arrival time** (calculated proportionally along the route from the departure timestamp), rather than simply using the origin departure time.
- **Nearest Hourly Forecast Slot**: The service parses UTC forecast timestamps and matches each checkpoint arrival to the closest hourly forecast slot.
- **Coordinate Deduplication**: Checkpoints with identical or nearby coordinates (within ~110m) are deduplicated before issuing requests, preventing unnecessary repeated API queries.
- **Resilient Degradation**: If the weather provider times out or experiences an outage, routes are still returned successfully with checkpoint `data_availability: "unavailable"`, ensuring user workflows are not blocked.

#### Weather Variables & Standardized Units

| Variable | API Parameter | Stored Field | Output Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Wind Speed** | `wind_speed_10m` | `wind_speed_mph` | `mph` | Wind speed at 10 meters above ground in miles per hour. |
| **Wind Gusts** | `wind_gusts_10m` | `wind_gust_mph` | `mph` | Peak wind gusts in miles per hour. |
| **Precipitation Rate** | `precipitation` | `precipitation_in_per_hour` | `in/h` | Liquid-equivalent precipitation intensity derived from 1-hour accumulation. |
| **Snowfall Rate** | `snowfall` | `snowfall_in_per_hour` | `in/h` | Snowfall depth intensity derived from 1-hour accumulation. |
| **Temperature** | `temperature_2m` | `temperature` | `°F` | Ambient air temperature at 2 meters above ground. |
| **Precipitation Probability** | `precipitation_probability` | `precipitation_probability` | `%` | Hourly probability of precipitation (0–100%). |
| **Weather Condition** | `weather_code` | `condition`, `weather_code` | text / int | Human-readable condition mapped from WMO 4677 standard codes. |
| **Data Availability** | N/A | `data_availability` | string | Status: `available`, `partial`, `out_of_forecast_horizon`, or `unavailable`. |

#### Forecast Limitations & Intensity Calculation Notice
> [!IMPORTANT]
> **Precipitation & Snowfall Intensity Rates**: Open-Meteo provides preceding 1-hour accumulated precipitation amounts (liquid equivalent in inches) and snowfall amounts (snow depth in inches). Average rates in `in/h` are calculated over this 1-hour discrete interval. They reflect 1-hour average accumulations rather than instantaneous radar reflectivity rates.
> **No Zero-Defaulting for Missing Data**: Missing or unobserved variables in provider responses are strictly preserved as `null` (`None`) and marked `partial`. The application **never** invents rates or silently replaces missing weather data with `0.0`.
> **Forecast Horizon Limits**: Forecast data is limited to the provider's forecast horizon (typically 7–14 days). Checkpoints with arrival dates beyond the available horizon are safely tagged with `data_availability: "out_of_forecast_horizon"`, setting weather variables to `null` with explicit limitation notes.

---

### Checkpoint Sampling

- **Configurable Intervals**: Routes can be sampled at `10`, `25`, or `50` miles (`checkpoint_interval_miles`).
- **Exact Unit Conversion**: Miles are converted to kilometers using the standard conversion factor: `1 mi = 1.609344 km` (`1609.344 meters`).
- **Endpoint Preservation**: Route order is strictly preserved. Sequence 1 always represents Departure (0.0 mi), intermediate checkpoints represent sampled intervals along the polyline, and the final sequence represents Arrival at the destination.
- **Duplicate Prevention**: Sampled checkpoints within 1.0 mile of the destination are omitted to prevent duplicate checkpoints at the endpoint.

---

#### Response Schema & Example

```json
{
  "status": "planned",
  "message": "Routes successfully calculated via Mapbox Directions API with weather forecasts from Open-Meteo. Note: Routes reflect standard driving directions and do not yet account for truck restrictions (height/weight limits) or road closures.",
  "request_summary": {
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": 35000.0,
    "checkpoint_interval_miles": 50
  },
  "routes": [
    {
      "route_id": "mapbox-route-1",
      "display_name": "Primary Route (via I-55 S, I-30 W)",
      "distance_km": 1488.5,
      "distance_miles": 924.6,
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
          "weather": {
            "timestamp": "2026-10-30T08:00:00Z",
            "forecast_timestamp": "2026-10-30T08:00:00+00:00",
            "data_availability": "available",
            "temperature": 42.0,
            "condition": "Overcast",
            "weather_code": 3,
            "wind_speed_mph": 14.0,
            "wind_gust_mph": 18.5,
            "precipitation_probability": 20.0,
            "precipitation_in_per_hour": 0.0,
            "snowfall_in_per_hour": 0.0,
            "precipitation_accumulation_in": 0.0,
            "snowfall_accumulation_in": 0.0,
            "units": {
              "temperature": "°F",
              "wind_speed": "mph",
              "wind_gust": "mph",
              "precipitation": "in/h",
              "snowfall": "in/h",
              "precipitation_probability": "%",
              "visibility": "miles"
            }
          },
          "risk_level": "unknown",
          "risk_summary": null
        },
        {
          "sequence": 2,
          "name": "Mile 50 (I-55 S)",
          "latitude": 41.3524,
          "longitude": -88.1942,
          "estimated_arrival": "2026-10-30T08:45:00Z",
          "distance_from_origin_km": 80.5,
          "distance_from_origin_miles": 50.0,
          "duration_from_origin_seconds": 2724,
          "weather": {
            "timestamp": "2026-10-30T08:45:00Z",
            "forecast_timestamp": "2026-10-30T09:00:00+00:00",
            "data_availability": "available",
            "temperature": 43.5,
            "condition": "Light drizzle",
            "weather_code": 51,
            "wind_speed_mph": 16.2,
            "wind_gust_mph": 22.0,
            "precipitation_probability": 45.0,
            "precipitation_in_per_hour": 0.04,
            "snowfall_in_per_hour": 0.0,
            "precipitation_accumulation_in": 0.04,
            "snowfall_accumulation_in": 0.0,
            "units": {
              "temperature": "°F",
              "wind_speed": "mph",
              "wind_gust": "mph",
              "precipitation": "in/h",
              "snowfall": "in/h",
              "precipitation_probability": "%",
              "visibility": "miles"
            }
          },
          "risk_level": "unknown",
          "risk_summary": null
        }
      ],
      "weather_summary": {
        "total_checkpoints": 20,
        "available_checkpoints": 20,
        "max_wind_speed_mph": 24.5,
        "max_precipitation_in_per_hour": 0.15,
        "max_snowfall_in_per_hour": 0.0,
        "conditions_observed": ["Light drizzle", "Overcast"],
        "provider": "Open-Meteo Forecast API",
        "limitations": "Hourly precipitation and snowfall represent 1-hour average rates derived from accumulated forecast amounts, not instantaneous radar rates. Missing values are preserved as null."
      },
---

### Weather Hazard Risk Scoring Engine

The backend implements a modular, deterministic risk-scoring engine (`WeatherRiskService`) that evaluates weather hazard severity at each checkpoint and calculates segment-level and route-level risk assessments based on vehicle characteristics (e.g. truck load weight in pounds).

#### 1. Hazard Threshold Definitions

| Hazard Level | Wind Speed (`mph`) | Precipitation Intensity (`in/h`) | Snowfall Intensity (`in/h`) | Numeric Score | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Low** | `< 25.0` | `< 0.10` | `< 0.50` | `10.0` | Negligible impact on heavy truck stability and braking. |
| **Moderate** | `25.0 – 34.0` | `0.10 – 0.25` | `0.50 – 1.00` | `35.0` | Noticeable crosswinds or reduced visibility; minor speed reduction advised. |
| **High** | `35.0 – 44.0` | `> 0.25 – 0.50` | `> 1.00 – 2.00` | `60.0` | High crosswinds or slick roads; elevated rollover/jackknife risk. |
| **Severe** | `45.0 – 54.0` | `> 0.50 – 1.00` | `> 2.00 – 3.00` | `80.0` | Severe weather hazard; dangerous driving conditions. |
| **No Travel** | `>= 55.0` | `> 1.00` | `> 3.00` | `100.0` | Extreme hazard; imminent rollover, whiteout, or hydroplaning. Travel unsafe. |
| **Unknown** | Missing / Null | Missing / Null | Missing / Null | `null` | Weather data unavailable; risk cannot be determined or certified. |

#### 2. Truck Load-Specific Elevation Rules

High winds exert severe aerodynamic tipping forces on commercial tractor-trailers, significantly exacerbated by cargo weight distribution:

1. **Universal No-Travel Rule**: Sustained wind speed **at or above 55 mph** enforces **No Travel** for every vehicle regardless of weight.
2. **Heavy Load Rule (> 30,000 lb)**: Wind from **45 to below 55 mph** is elevated to **No Travel** when cargo load weight exceeds **30,000 lb** (standard base category: *Severe*).
3. **Very Heavy Load Rule (> 40,000 lb)**: Wind from **35 to below 45 mph** is elevated to **Severe** when cargo load weight exceeds **40,000 lb** (standard base category: *High*).

#### 3. Multi-Hazard Governance & Missing-Data Safety

- **Most Severe Hazard Governs**: Wind, precipitation, and snowfall are evaluated independently. The highest individual hazard category determines the checkpoint's overall `risk_level`.
- **Component Preservation**: Detailed evaluations for all three hazards are preserved in `risk_components` (`wind`, `precipitation`, `snowfall`) along with the specific trigger reason and load-elevation flags.
- **Strict Missing-Data Safety Policy**: Missing weather measurements are strictly represented as `null`. Missing data is **never** treated as zero, and checkpoints with missing hazard observations are **never** certified as *Low* risk. Data quality is explicitly tracked as `available`, `partial`, or `unavailable`.

#### 4. Route Summary & Segment Distance Methodology

- **Segment Distance Attribution**: Each checkpoint represents the road segment centered around it:
  - Departure (Checkpoint 1) represents $0$ to midpoint with Checkpoint 2: $d_1 / 2$.
  - Intermediate Checkpoint $i$ represents midpoint $(i-1, i)$ to midpoint $(i, i+1)$: $(d_{i+1} - d_{i-1}) / 2$.
  - Arrival (Checkpoint $N$) represents midpoint $(N-1, N)$ to destination: $(d_N - d_{N-1}) / 2$.
  - *Mathematical Consistency*: The sum of all checkpoint segment distances equals the total route distance precisely without gaps or overlap.
- **Categorical Mileages**: Distance affected by each category is calculated explicitly (`low_risk_miles`, `moderate_risk_miles`, `high_risk_miles`, `severe_risk_miles`, `no_travel_miles`, `unknown_risk_miles`).
- **No-Travel Warnings**: Any route segment flagged as `no_travel` immediately triggers `no_travel_warning: true` and elevates the route `overall_risk_level` to `no_travel`.
- **Distance-Weighted Average Score**: Route `risk_score` is computed as the distance-weighted average over all scored segments: $\frac{\sum (\text{Segment Miles}_i \times \text{Score}_i)}{\sum \text{Segment Miles}_i}$.

---

#### Response Schema & Example

```json
{
  "status": "planned",
  "message": "Routes successfully calculated via Mapbox Directions API with weather forecasts from Open-Meteo and load-specific weather hazard risk assessments. Note: Routes reflect standard driving directions and do not yet account for truck height/weight limits or road closures.",
  "request_summary": {
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": 45000.0,
    "checkpoint_interval_miles": 50
  },
  "routes": [
    {
      "route_id": "mapbox-route-1",
      "display_name": "Primary Route (via I-55 S, I-30 W)",
      "distance_km": 1488.5,
      "distance_miles": 924.6,
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
          "weather": {
            "timestamp": "2026-10-30T08:00:00Z",
            "forecast_timestamp": "2026-10-30T08:00:00+00:00",
            "data_availability": "available",
            "temperature": 42.0,
            "condition": "Overcast",
            "weather_code": 3,
            "wind_speed_mph": 38.0,
            "wind_gust_mph": 44.0,
            "precipitation_probability": 20.0,
            "precipitation_in_per_hour": 0.0,
            "snowfall_in_per_hour": 0.0,
            "precipitation_accumulation_in": 0.0,
            "snowfall_accumulation_in": 0.0,
            "units": {
              "temperature": "°F",
              "wind_speed": "mph",
              "wind_gust": "mph",
              "precipitation": "in/h",
              "snowfall": "in/h",
              "precipitation_probability": "%",
              "visibility": "miles"
            }
          },
          "risk_level": "severe",
          "risk_score": 80.0,
          "risk_components": {
            "wind": {
              "hazard": "wind",
              "risk_level": "severe",
              "score": 80.0,
              "value": 38.0,
              "unit": "mph",
              "reason": "Wind speed (38.0 mph in 35-44 mph range) elevated to Severe for very heavy load (45,000 lb > 40,000 lb).",
              "is_elevated_by_load": true
            },
            "precipitation": {
              "hazard": "precipitation",
              "risk_level": "low",
              "score": 10.0,
              "value": 0.0,
              "unit": "in/h",
              "reason": "Low precipitation rate (0.00 in/h < 0.10 in/h)."
            },
            "snowfall": {
              "hazard": "snowfall",
              "risk_level": "low",
              "score": 10.0,
              "value": 0.0,
              "unit": "in/h",
              "reason": "Low snowfall rate (0.00 in/h < 0.50 in/h)."
            }
          },
          "risk_factors": [
            "Wind speed (38.0 mph in 35-44 mph range) elevated to Severe for very heavy load (45,000 lb > 40,000 lb)."
          ],
          "risk_summary": "SEVERE HAZARD: Wind speed (38.0 mph in 35-44 mph range) elevated to Severe for very heavy load (45,000 lb > 40,000 lb).",
          "data_quality": "available"
        }
      ],
      "weather_summary": {
        "total_checkpoints": 20,
        "available_checkpoints": 20,
        "max_wind_speed_mph": 38.0,
        "max_precipitation_in_per_hour": 0.15,
        "max_snowfall_in_per_hour": 0.0,
        "conditions_observed": ["Overcast"],
        "provider": "Open-Meteo Forecast API",
        "limitations": "Hourly precipitation and snowfall represent 1-hour average rates derived from accumulated forecast amounts, not instantaneous radar rates. Missing values are preserved as null."
      },
      "risk_assessment": {
        "overall_risk_level": "severe",
        "risk_score": 75.5,
        "risk_factors": [
          "Wind speed (38.0 mph in 35-44 mph range) elevated to Severe for very heavy load (45,000 lb > 40,000 lb)."
        ],
        "summary": "SEVERE RISK: Route encounters 75.0 severe weather miles for load weight of 45,000 lb. Extreme caution and reduced speeds required.",
        "total_distance_miles": 924.6,
        "low_risk_miles": 450.0,
        "moderate_risk_miles": 200.0,
        "high_risk_miles": 199.6,
        "severe_risk_miles": 75.0,
        "no_travel_miles": 0.0,
        "unknown_risk_miles": 0.0,
        "no_travel_segments_count": 0,
        "no_travel_warning": false,
        "data_quality": "available",
        "assumptions": [
          "Threshold evaluation: Wind speed (mph), precipitation intensity (in/h), and snowfall intensity (in/h) are evaluated independently; the most severe hazard governs the checkpoint risk level.",
          "Load-specific rules: Wind >= 55 mph enforces No Travel for all loads. Wind 45 to <55 mph enforces No Travel when load weight is > 30,000 lb. Wind 35 to <45 mph elevates to Severe when load weight is > 40,000 lb.",
          "Missing weather data: Checkpoints with missing weather measurements are explicitly marked with data quality 'partial' or 'unavailable'. Missing data is never treated as zero and is never assigned Low risk.",
          "Segment attribution: Each checkpoint represents the route segment centered on its location (half-distance to previous checkpoint plus half-distance to next checkpoint; endpoints cover half-distance to adjacent checkpoint). Segment miles sum precisely to total route distance.",
          "Numeric scoring: Categorical risks map to standard scores (Low: 10, Moderate: 35, High: 60, Severe: 80, No Travel: 100, Unknown: None). Route score is the distance-weighted average over scored segments."
        ]
      },
      "recommendation": {
        "rank": 1,
        "is_recommended": true,
        "status": "recommended",
        "explanation": "Recommended as safest route: avoids all severe and high-risk weather hazards, average risk score: 10.0, travel time: 14h 0m.",
        "eligibility": "eligible",
        "assessment_status": "complete",
        "ranking_metrics": {
          "severe_risk_miles": 0.0,
          "high_risk_miles": 0.0,
          "average_risk_score": 10.0,
          "duration_seconds": 50400,
          "duration_formatted": "14h 0m",
          "no_travel_miles": 0.0,
          "no_travel_segments_count": 0,
          "unknown_risk_miles": 0.0
        }
      }
    }
  ],
  "recommendation_summary": {
    "recommended_route_id": "mapbox-route-1",
    "all_routes_unsafe": false,
    "incomplete_data_warning": false,
    "total_options_evaluated": 2,
    "ranking_priority": [
      "1. Fewest miles classified as Severe",
      "2. Fewest miles classified as High",
      "3. Lowest average risk score",
      "4. Shortest travel time"
    ],
    "safety_policy": "Routes containing any No Travel segments are strictly ineligible for recommendation when safe alternatives exist. If every available route contains a No Travel segment, the engine flags that no route is considered safe and advises postponing departure.",
    "data_quality_policy": "Routes with incomplete or unavailable weather forecasts are never silently treated as safer than fully assessed routes. Unassessed segments are flagged, and incomplete routes cannot be recommended if safe, fully assessed routes are available.",
    "executive_summary": "Route 'Primary Route (via I-55 S, I-30 W)' is recommended as the safest route. Recommended as safest route: avoids all severe and high-risk weather hazards, average risk score: 10.0, travel time: 14h 0m."
  }
}
```

---

## Route Recommendation and Ranking Engine

The backend includes a dedicated, modular recommendation service (`RouteRecommendationService` in `backend/routing/services/recommendation.py`, implementing `BaseRecommendationEngine`). It evaluates all available route options and ranks them lexicographically by safety and efficiency.

### 1. Lexicographic Ranking Priority

Route options are ordered strictly using the following 4-stage lexicographic hierarchy:

| Priority | Criterion | Metric Field | Sort Order | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **1st** | Fewest miles classified as Severe | `severe_risk_miles` | Ascending (lower is better) | Primary priority: minimize exposure to dangerous storm, snow, and wind conditions. |
| **2nd** | Fewest miles classified as High | `high_risk_miles` | Ascending (lower is better) | Secondary priority: among routes with equal severe miles, minimize high-risk segments. |
| **3rd** | Lowest average risk score | `risk_score` | Ascending (lower is better) | Tertiary priority: among routes with equal severe and high miles, minimize overall route hazard exposure. |
| **4th** | Shortest travel time | `duration_seconds` | Ascending (faster is better) | Efficiency tie-breaker: among routes with identical weather risk profiles, pick the fastest path. |

> **Strict Lexicographic Guarantee**: Criteria are evaluated sequentially without weighted averaging, ensuring a lower-priority criterion (e.g. faster driving time or lower moderate risk) can **never** override a higher-priority safety criterion (e.g. avoiding severe weather).

### 2. Safety Constraint for No Travel Segments

- **Eligibility Segregation**: Any route encountering a **No Travel** segment (`no_travel_miles > 0` or `no_travel_segments_count > 0` or `no_travel_warning = True`) is classified as `eligibility: "no_travel_hazard"`.
- **Ineligibility When Safe Routes Exist**: A route containing No Travel conditions is strictly prohibited from being recommended (`is_recommended = false`, `status = "not_recommended"`) when any route without No Travel segments is available.
- **All-Unsafe Detection**: If **every** available route option contains a No Travel segment:
  - The top-level summary sets `all_routes_unsafe: true` and `recommended_route_id: null`.
  - Every route is flagged with `is_recommended: false` and `status: "not_recommended"`.
  - Routes are ordered among themselves by minimizing extreme danger exposure (`no_travel_miles`), then applying the 4 assignment criteria.
  - The executive summary issues a critical alert: *"NO SAFE ROUTE AVAILABLE: All route options encounter extreme weather with No Travel advisories. Driving is unsafe and prohibited under carrier safety standards."*

### 3. Incomplete & Missing Weather Data Governance

- **Prudent Safety Tiering**: Routes are partitioned into safety tiers:
  - **Tier 0 (Eligible)**: Fully assessed, 0 No Travel miles.
  - **Tier 1 (Incomplete)**: Partial or unavailable weather forecasts (`data_quality: "partial" | "unavailable"`), 0 No Travel miles.
  - **Tier 2 (Hazardous)**: Contains No Travel segments.
- **Never Treated as Safer**: Because Tier 0 routes sort ahead of Tier 1 routes, a route with missing weather forecasts is **never** silently treated as safer than a fully assessed route (e.g. missing sensors cannot masquerade as 0 severe miles to beat a complete assessment).
- **Assessment Status**: Each route includes `assessment_status: "complete" | "partial" | "unavailable"`. When all routes have incomplete forecasts, the fastest route is highlighted with an explicit warning caveat (`incomplete_data_warning: true`).

### 4. Deterministic Tie-Breaking

When all four criteria (severe miles, high miles, average risk score, duration) are strictly identical:
- Ordering is deterministically broken using route identifier (`route_id`) and sequence index.
- Multiple runs on the same input produce 100% reproducible rankings.

### 5. Recommendation Explanation Format

Each route receives a tailored human-readable explanation:
- **Recommended Route (Rank 1)**: Highlights why the route was chosen (e.g. *"Recommended as safest route: avoids all severe and high-risk weather hazards, average risk score: 10.0, travel time: 14h 0m"*).
- **Viable Alternatives (Rank 2+)**: Notes safety clearance and describes comparative trade-offs relative to Rank 1 (e.g. *"+15 min travel time vs Recommended Route"* or *"+4.5 mi high-risk weather"*).
- **No Travel Warnings**: Highlights segment counts and prohibited travel advisories (e.g. *"NOT RECOMMENDED (Rank 2): Route violates critical safety policy with 6.5 miles of No Travel conditions across 1 segment(s)"*).
- **Incomplete Data Warnings**: Warns of unassessed mileage where forecasts could not be verified.

---

#### Example Usage

**Valid Request with 25-Mile Sampling:**
```bash
curl -i -X POST http://127.0.0.1:8000/api/routes/ \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "departure_datetime": "2026-10-30T08:00:00Z",
    "load_weight_lb": 45000.0,
    "checkpoint_interval_miles": 25
  }'
```

---

## Automated Testing

Run the full automated test suite (79 tests) with zero external network dependencies or credentials:

```bash
cd backend
.venv/bin/python manage.py test
```

To run recommendation tests specifically:
```bash
.venv/bin/python manage.py test routing.tests.RouteRecommendationServiceTests
.venv/bin/python manage.py test routing.tests.RoutePlanningRecommendationIntegrationTests
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

- Frontend user interface (route input form, origin/destination geocoding, vehicle configuration)
- Interactive Mapbox GL JS map visualization with route alternatives and weather hazard overlays
- Weather risk heatmap layers and checkpoint inspection popups






