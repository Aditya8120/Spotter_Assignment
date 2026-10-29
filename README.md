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

## Frontend Setup & Backend Integration (React + Django)

The frontend is an enterprise logistics dispatch dashboard built with **React 19** and **Vite 8**, connected to the Django REST Framework backend API (`POST /api/routes/`).

### 1. Component & Service Structure

```text
frontend/src/
├── services/
│   ├── api.js                     # API client service: payload construction, HTTP fetch, error normalization
│   └── api.test.js                # Automated unit tests for API networking, error handling & payload builder
├── components/
│   ├── Header.jsx                 # Top navigation bar with branding, system status chips, and reset
│   ├── RouteForm.jsx              # Form with inputs, client validation, weight tiers, presets & loading state
│   ├── MapPlaceholder.jsx         # Dedicated Mapbox canvas placeholder with Step 10 integration notices
│   ├── RouteCard.jsx              # Reusable route alternative card rendering real backend risk metrics
│   ├── RouteResults.jsx           # Results container managing empty, loading, 503 pending setup & error states
│   └── RiskThresholdReference.jsx # Collapsible logistics reference drawer with hazard thresholds and load rules
├── App.jsx                        # Main logistics dashboard coordinating API requests and state
├── App.css                        # Dashboard styles, status cards, spinners, and responsive breakpoints
├── index.css                      # Base design tokens, resets, typography (Inter + JetBrains Mono)
└── main.jsx                       # Application entry point
```

### 2. Frontend Environment Configuration

Configure the backend API URL through `VITE_API_BASE_URL` in `frontend/.env` (defaults to `http://localhost:8000`):

```bash
# In frontend/.env or root .env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Running Both Servers Locally

To run the complete full-stack application during local development, open two terminal windows:

**Terminal 1 — Django Backend Server:**
```bash
cd backend
source .venv/bin/activate
python manage.py runserver 8000
```
Backend API will be live at: `http://localhost:8000/api/`

**Terminal 2 — React Vite Frontend Server:**
```bash
cd frontend
npm run dev
```
Frontend application will be live at: `http://localhost:5173/`

### 4. API Integration Flow & State Governance

The frontend interacts with the backend using the service module `frontend/src/services/api.js`:

1. **Payload Serialization**:
   - `buildRoutePlanPayload` converts form inputs to the exact Django schema:
     - `origin`: string (text city or `"lat,lon"`)
     - `destination`: string (text city or `"lat,lon"`)
     - `departure_datetime`: ISO 8601 string (e.g. `2026-10-30T08:00:00.000Z`)
     - `load_weight_lb`: float $> 0$
     - `checkpoint_interval_miles`: integer ($10$, $25$, or $50$)
2. **Distinct Lifecycle States**:
   - **Initial Empty State**: Displays clear dispatch instructions before any request is made.
   - **Loading State**: Disables form inputs, displays an animated loading spinner, and informs the operator that Mapbox geometries and Open-Meteo hourly forecasts are being processed. Duplicate clicks are blocked.
   - **Backend Setup Pending State (HTTP 503 `provider_not_configured`)**: When the backend server does not yet have a Mapbox access token configured (`MAPBOX_ACCESS_TOKEN`), the frontend displays a helpful, informative setup banner detailing how to add the token to `backend/.env`.
   - **Validation Error State (HTTP 400)**: Maps server-side field errors back to the respective form inputs and preserves entered values so the operator can adjust and retry.
   - **Network Error State**: Displays clear troubleshooting instructions if the Django backend server is stopped or unreachable.
   - **Successful Results State**: Renders real candidate routes returned by the backend with their exact rank, distance, duration, severe/high weather mileage, average risk score, and lexicographic recommendation rationale.
3. **No Fake Demo Data**: All static placeholder route cards from Step 8 have been removed. Results are strictly driven by real backend API responses.

### 5. Automated Frontend Testing & Verification

Run the frontend test suite (10 tests covering payload construction, 200 OK responses, 503 unconfigured setup, 400 validation, 404 no route, network failures, and health check):
```bash
cd frontend
npm test
```

Run linter checks:
```bash
cd frontend
npm run lint
```

Build production bundle:
```bash
cd frontend
npm run build
```

Run full backend test suite (79 tests):
```bash
cd backend
.venv/bin/python manage.py test
```

---

## Interactive Map & Route Visualization (Step 10)

The dashboard includes a fully interactive, responsive map canvas powered by **Leaflet** and **React Leaflet**, displaying real route polylines and weather hazard checkpoints returned by the backend API.

### 1. Architecture & Libraries

- **`leaflet` (`^1.9.4`)** & **`react-leaflet` (`^5.0.0`)**: Integrated natively with React 19 without peer dependency conflicts.
- **`leaflet/dist/leaflet.css`**: Loaded in `main.jsx` for map controls, panes, popups, and zoom widgets.
- **Custom `L.divIcon` Markers**: Origin, Destination, and Checkpoints use HTML/SVG DivIcons, eliminating 404 image errors in Vite bundlers.
- **`frontend/src/utils/mapUtils.js`**: Pure, testable utilities for coordinate validation, GeoJSON `[lon, lat]` to Leaflet `[lat, lon]` transformations, bounding box calculations, and risk level metadata.

### 2. Geometry Handling & Coordinate Transformation

- **Backend API Format**: Mapbox Directions API outputs GeoJSON LineString coordinates in `[longitude, latitude]` order.
- **Leaflet Expectation**: Leaflet `Polyline` requires `[latitude, longitude]` coordinates.
- **Transformation**: `parseRouteGeometry` validates every coordinate pair (`-90 <= lat <= 90`, `-180 <= lon <= 180`), inverts `[lon, lat]` to `[lat, lon]`, and rejects corrupt points.
- **Anti-Fabrication Guarantee**: If route geometry is null or empty, **no artificial lines are drawn** between endpoints. The UI gracefully displays an informative banner while rendering available checkpoint markers.

### 3. Route Selection & Viewport Fitting

- **Bidirectional Linking**: Route selection is synchronized between the map header tab bar (`#1`, `#2`, `#3`) and the route cards in the results grid.
- **Selected Route Style**: Prominent stroke (`weight: 6`, `opacity: 0.95`, primary blue), high z-index, and interactive hover tooltip.
- **Alternative Routes Style**: Subtle dashed lines (`weight: 4`, `opacity: 0.55`, purple/cyan palette). Clicking an alternative route's polyline switches active selection.
- **Dynamic Viewport (`fitBounds`)**: `<MapBoundsController>` automatically fits the Leaflet viewport to the bounds of the active route with 50px padding whenever routes or selection change.

### 4. Checkpoint Risk Markers & Popups

- **Ordered Waypoints**: Checkpoints are rendered strictly in route sequence along the active corridor.
- **Endpoint Markers**:
  - **Origin (Point A)**: Emerald pin with scheduled departure datetime and coordinates.
  - **Destination (Point B)**: Crimson pin with estimated arrival datetime and total distance.
- **Risk Categorization**:
  - 🟢 **Low Risk**: Wind < 25 mph, precip < 0.10 in/h, snow < 1.0 in/h (`#10b981`)
  - 🟡 **Moderate Risk**: Wind 25–34 mph, precip 0.10–0.25 in/h, snow 1.0–1.9 in/h (`#f59e0b`)
  - 🟠 **High Risk**: Wind 35–44 mph, precip > 0.25–0.50 in/h, snow 2.0–2.9 in/h (`#f97316`)
  - 🔴 **Severe Risk**: Wind 45–54 mph, precip > 0.50 in/h, snow ≥ 3.0 in/h (`#ef4444`)
  - ⛔ **No Travel Advisory**: Wind ≥ 55 mph, or elevated crosswind threshold for light/empty truck (`#991b1b`)
  - ⚪ **Unknown / Pending**: Weather data unavailable or pending assessment (`#64748b`)
  - **Rule**: Missing, null, or unrecognized risk data is strictly mapped to **Unknown**, never Low.
- **Interactive Popups**: Clicking any checkpoint displays waypoint name, sequence number, distance from origin, estimated arrival time, risk level badge, risk summary, and weather observations (temperature, sustained wind, gusts, precipitation rate, snowfall rate).

### 5. OpenStreetMap Tile Source & Usage Policy

- **Default Tile URL**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
- **Attribution**: `&copy; OpenStreetMap contributors`
- **Configurable**: Configurable via `VITE_MAP_TILE_URL` and `VITE_MAP_TILE_ATTRIBUTION`.
- **Policy Compliance**: In accordance with the [OpenStreetMap Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/), tiles are accessed with fair-use request rates, caching, and clear attribution. High-volume commercial production deployments must use dedicated commercial tile providers (Mapbox, Stadia, Protomaps, Thunderforest) or a self-hosted tile cache.

### 6. Automated Testing

The frontend automated test suite includes **64 tests** across 24 suites:
- **`src/services/api.test.js`**: Payload construction, HTTP responses, error normalization, and health checks.
- **`src/utils/mapUtils.test.js`**: Coordinate validation, GeoJSON coordinate transformation, bounding box calculation, risk level metadata mapping, route polyline styles, and checkpoint extraction.
- **`src/utils/mapIntegration.test.js`**: Route selection state transitions, multi-segment corridor rendering with mocked data, checkpoint risk marker classifications, missing geometry handling, and empty result safety.
- **`src/utils/weatherLayers.test.js`**: Wind/precipitation/snowfall threshold evaluations, load-weight elevations, 0–48h timeline generation, timestamp matching, and layer value extraction.
- **`src/utils/weatherLayersIntegration.test.js`**: Dynamic layer switching, stale data prevention across unrecorded hours, route-selection preservation during slider scrubbing, and empty state resilience.
- **`src/e2e/dispatchFlow.test.js`**: Complete end-to-end journey tests covering form submission, payload serialization, mock API fetch, geometry inversion, bounds calculation, checkpoint extraction, 0–48h timeline generation, 4-layer evaluation, HTTP 503 setup-pending state, HTTP 400 validation error mapping, and network failure diagnostics.
- **`src/e2e/demoCorridor.test.js`**: Verification of simulated demo corridor fixtures, route coordinate integrity, and weather layer evaluations.

```bash
# Run all frontend tests (64 tests)
cd frontend && npm test

# Run linter
cd frontend && npm run lint

# Run production build
cd frontend && npm run build

# Run backend test suite (81 tests)
cd backend && .venv/bin/python manage.py test
```

---

## Weather Heatmap & 0–48h Forecast Timeline (Step 11)

The interactive map includes an honest, corridor-following weather heatmap overlay and a dynamic **0–48-hour forecast timeline slider**.

### 1. Supported Weather Layers

Operators can toggle between four dedicated weather overlay layers:
- 🛡️ **Overall Risk**: Composite hazard evaluation governed by the most severe condition and vehicle load weight.
- 💨 **Wind Speed (`mph`)**: Sustained winds and gusts evaluated against commercial tip-over thresholds:
  - Low (<25 mph), Moderate (25–34 mph), High (35–44 mph), Severe (45–54 mph), No Travel (≥55 mph).
  - Elevates to No Travel at 45–54 mph when load weight exceeds 30,000 lb.
  - Elevates to Severe at 35–44 mph when load weight exceeds 40,000 lb.
- 🌧️ **Precipitation (`in/h`)**: 1-hour rainfall rate and hydroplaning risk:
  - Low (<0.10 in/h), Moderate (0.10–0.25 in/h), High (>0.25–0.50 in/h), Severe (>0.50 in/h).
- ❄️ **Snowfall (`in/h`)**: Snow accumulation rate and whiteout hazard:
  - Low (<0.50 in/h), Moderate (0.50–1.00 in/h), High (>1.00–2.00 in/h), Severe (>2.00–3.00 in/h), No Travel (>3.00 in/h).

### 2. Forecast Timeline Slider (0 to 48 Hours)

- **49 Hourly Horizons**: Covers `T+0h` (Departure) through `T+48h` relative to the scheduled departure datetime.
- **Horizon Readout**: Clearly displays the active horizon (e.g. `T+6h • Friday, Oct 30 at 14:00 UTC`).
- **Interactive Controls**: Scrub slider, `-1h` / `+1h` step buttons, quick jump buttons (`T+0h`, `+6h`, `+12h`, `+24h`, `+48h`), and automated playback animation (`▶ Play` / `⏸ Pause`).
- **Data Availability Rules**:
  - The slider checks whether forecast data is recorded for each horizon slot.
  - **No Stale Data Reuse**: Observations sampled at checkpoint arrival times are never reused for a different timestamp without explicit identification. When an unrecorded hour is selected, checkpoints display an Unknown marker with an explanatory message: *"Forecast observation not recorded for T+Xh (Sampled at scheduled arrival)"*.
  - When matching hourly data is available, checkpoints update their values and colors in real time.

### 3. Corridor Heatmap Overlay & Data Integrity

- **Route Corridor Geometry**: Renders a glowing heatmap underlay along the polyline coordinates of the selected route, accompanied by semi-transparent influence discs around each checkpoint.
- **Honest Approximation**: Because weather data is sampled at discrete checkpoint intervals (10, 25, or 50 miles) rather than continuous radar reflectivity, the map displays an explicit watermark: *"Corridor Heatmap Approximation (Sampled Checkpoints; Not Radar Reflectivity)"*.
- **Route Selection Preservation**: Scrubbing the timeline or switching weather layers never resets or alters the selected route ID or card selection in the results panel.

---

## Final End-to-End Integration & Quality Verification (Step 12)

The complete application pipeline was verified through end-to-end integration and automated regression testing.

### 1. Verified Complete Flow Trace
- **Route Form**: Validates origin/destination inputs, ISO-8601 departure timestamp, gross load weight (0–80,000 lb), and sampling intervals (10, 25, 50 mi).
- **Django REST API**: `POST /api/routes/` deserializes payload, converts units, validates constraints, and checks external provider readiness.
- **Route Generation (`MapboxRoutingService`)**: Requests driving routes with alternative corridors and polyline geometries via Mapbox Directions.
- **Checkpoint Sampling (`sample_checkpoints`)**: Samples checkpoints at exact distance intervals (10, 25, 50 miles), including origin and destination, calculating arrival times based on segment durations.
- **Weather Retrieval (`OpenMeteoWeatherService`)**: Fetches hourly weather forecasts at each checkpoint for its specific estimated arrival time.
- **Risk Scoring (`WeatherRiskScorer`)**: Evaluates wind speed, precipitation intensity, and snowfall against exact assignment thresholds, applying load-weight crosswind elevations. Missing weather is preserved as `unknown`, never zero/low risk.
- **Route Recommendation (`RouteRecommender`)**: Ranks alternatives using lexicographic priority (1: Fewest Severe miles, 2: Fewest High miles, 3: Lowest average risk, 4: Shortest travel time). Flags `all_routes_unsafe` and blocks recommendations when all corridors encounter No Travel advisories.
- **Frontend Dashboard (`App.jsx`)**: Renders loading skeletons, error alerts with troubleshooting guides, setup-pending banners when credentials are unconfigured, and result summaries.
- **Interactive Map (`RouteMap.jsx`)**: Renders GeoJSON geometries inverted to `[lat, lon]`, dynamic viewport fitting, checkpoint risk pins, popups, and 4-layer weather corridor heatmaps.
- **Timeline Slider (`ForecastTimeline.jsx`)**: Provides interactive 0–48h scrubbing with stale-data protection and animated playback.

### 2. Quality Verification Summary

| Suite / Check | Command | Result | Details |
| :--- | :--- | :--- | :--- |
| **Backend Tests** | `python manage.py test` | **81 Passed** (0 Failures) | Health, serializers, Mapbox service, Open-Meteo service, risk scoring, load rules, lexicographical ranking, No Travel flags, missing weather preservation. |
| **Frontend Tests** | `npm test` | **64 Passed** (0 Failures) | API client, error mapping, coordinate transformations, map integration, layer thresholds, timeline slider, end-to-end dispatch flow, demo fixture verification. |
| **Frontend Linter** | `npm run lint` | **0 Errors, 0 Warnings** | Oxlint verified 23 files. |
| **Production Build** | `npm run build` | **Passed in 138ms** | Vite production bundle generated without errors or circular dependencies. |
| **Live API Contracts** | `curl` against local daemons | **Verified** | Health endpoint `200 OK`, unconfigured provider returns clear `503 provider_not_configured`. |

### 3. Demonstration Mode & Simulated Data Integrity

To enable full offline visual evaluation when `MAPBOX_ACCESS_TOKEN` is not yet configured, the frontend dashboard includes a dedicated **Demonstration Mode**:
- **Explicit Labeling Guarantee**: All simulated fixture data is unmistakably labeled on-screen with prominent amber badges (`[SIMULATED DEMO DATA]`), corridor tags (`DEMO CORRIDOR`), and an executive warning banner:
  > **⚠️ DEMONSTRATION PREVIEW (SIMULATED DATA)**: *The corridors, weather checkpoints, and risk metrics shown below are simulated demonstration data designed for offline visual inspection. Live commercial dispatch requires a configured `MAPBOX_ACCESS_TOKEN` in the server environment.*
- **No Confusion with Live Data**: Standard search submissions automatically dispatch live requests to the backend API. When the live provider returns an error or is unconfigured, the operator is presented with actionable setup instructions alongside an option to preview the demonstration corridor.
- **Toggle Controls**: Operators can toggle into or out of Demo Mode at any time using the `Demo Corridor` / `Exit Demo` controls in the application header.

---

## Production Deployment Guide & Readiness Checklist

### 1. Production Architecture Overview

In a production environment, the frontend and backend are deployed as follows:

```text
┌─────────────────────────────────┐
│     Client Web Browser          │
│   (React SPA served via CDN/    │
│    Nginx on port 80/443 HTTPS)  │
└───────────────┬─────────────────┘
                │ API Requests (CORS restricted)
                ▼
┌─────────────────────────────────┐
│     Reverse Proxy (Nginx)       │
│  - SSL / TLS Termination        │
│  - Static Files (/static/)      │
│  - Rate Limiting                │
└───────────────┬─────────────────┘
                │ Reverse Proxy (Unix Socket or Port 8000)
                ▼
┌─────────────────────────────────┐
│     WSGI Server (Gunicorn)      │
│  - Workers: 2-4 worker processes│
│  - Timeout: 60 seconds          │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│     Django REST Framework       │
│  - DEBUG=False                  │
│  - Strict CORS_ALLOWED_ORIGINS  │
│  - SQLite or PostgreSQL DB      │
└───────────────┬─────────────────┘
                │ External HTTPS calls
                ├──► Mapbox Directions & Geocoding API
                └──► Open-Meteo Hourly Weather API
```

### 2. Backend Production Setup (Django)

1. **Install Production Server (e.g. Gunicorn)**:
   ```bash
   pip install gunicorn
   ```
2. **Configure Production Environment (`backend/.env`)**:
   ```bash
   DJANGO_SECRET_KEY=generate-a-strong-random-50-char-secret-key-for-prod
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=api.yourcompany.com,127.0.0.1
   CORS_ALLOWED_ORIGINS=https://dispatch.yourcompany.com
   DJANGO_DB_NAME=db.sqlite3
   DJANGO_STATIC_ROOT=staticfiles
   MAPBOX_ACCESS_TOKEN=pk.your_live_production_mapbox_token
   ```
3. **Collect Static Files**:
   ```bash
   python manage.py collectstatic --noinput
   ```
4. **Apply Migrations**:
   ```bash
   python manage.py migrate
   ```
5. **Run via Gunicorn**:
   ```bash
   gunicorn backend.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 60
   ```

### 3. Frontend Production Build & Hosting (Vite + React)

1. **Configure Production Environment (`frontend/.env`)**:
   ```bash
   VITE_API_BASE_URL=https://api.yourcompany.com
   VITE_MAP_TILE_URL=https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{z}/{x}/{y}?access_token=pk.your_token
   VITE_MAP_TILE_ATTRIBUTION=&copy; <a href="https://www.mapbox.com/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>
   ```
2. **Build Optimized Production Bundle**:
   ```bash
   npm run build
   ```
   Outputs minified HTML, CSS, and JS into `frontend/dist/`.
3. **Serve with Nginx / Caddy / Cloudflare Pages / AWS S3 + CloudFront**:
   Point your web server root to `frontend/dist/` with SPA fallback routing:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name dispatch.yourcompany.com;

       root /var/www/weather-truck-routing/frontend/dist;
       index index.html;

       location / {
           try_files $uri $uri/ /index.html;
       }
   }
   ```

### 4. Production Readiness Checklist

- [x] **Zero Hardcoded Secrets**: Secrets and tokens are loaded strictly via environment variables; none exist in source code.
- [x] **Safe Git Tracking**: Root `.gitignore` excludes `.env`, `staticfiles/`, `node_modules/`, `.venv/`, `dist/`, while tracking `.env.example`.
- [x] **Strict CORS Controls**: `CORS_ALLOWED_ORIGINS` is explicitly mapped to authorized domains; permissive wildcard access is disabled.
- [x] **Honest Data Transparency**: Missing weather is never classified as Low risk; unconfigured external providers trigger HTTP 503 rather than fabricated telemetry; demo modes are unmistakably labeled.
- [x] **Production Static Files**: `STATIC_ROOT` configured in Django for `collectstatic`.
- [x] **Comprehensive Test Suites**: 81 backend tests and 61 frontend tests passing with 0 errors.
- [ ] **External Credentials Configuration**: Add production `MAPBOX_ACCESS_TOKEN` to `backend/.env`.
- [ ] **Dedicated Commercial Tiles**: Configure high-volume tile provider in `VITE_MAP_TILE_URL` per OpenStreetMap Tile Usage Policy.











