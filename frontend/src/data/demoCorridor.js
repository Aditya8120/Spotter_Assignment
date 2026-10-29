/**
 * Demonstration sample corridor data for offline visual inspection and evaluation.
 *
 * CRITICAL TRANSPARENCY NOTICE:
 * This data is SIMULATED demonstration data representing a Chicago, IL -> Dallas, TX corridor.
 * It is used exclusively in Demo Mode when external API credentials (such as MAPBOX_ACCESS_TOKEN)
 * are not configured, or when an operator explicitly requests a demonstration preview.
 * It must NEVER be presented as live road observations or real-time meteorological telemetry.
 */

export const DEMO_CORRIDOR_PLAN = {
  status: 'planned',
  is_demo_data: true,
  message: 'DEMONSTRATION MODE: Simulated corridor and mock weather forecasts (Not live road data).',
  request_summary: {
    origin: { type: 'text', query: 'Chicago, IL' },
    destination: { type: 'text', query: 'Dallas, TX' },
    departure_datetime: '2026-10-30T08:00:00Z',
    load_weight_lb: 45000.0,
    checkpoint_interval_miles: 25,
  },
  recommendation_summary: {
    recommended_route_id: 'demo_route_primary',
    all_routes_unsafe: false,
    total_options_evaluated: 2,
    executive_summary:
      'Route #1 (Primary via I-55 S / I-30 W) is recommended: 0.0 Severe miles, 0.0 High miles, lowest average risk score (14.2).',
    ranking_priority: [
      '1. Fewest miles classified as Severe',
      '2. Fewest miles classified as High',
      '3. Lowest average risk score',
      '4. Shortest travel time',
    ],
  },
  routes: [
    {
      route_id: 'demo_route_primary',
      display_name: 'Primary via I-55 S & I-30 W',
      rank: 1,
      distance_miles: 924.5,
      distance_km: 1487.8,
      duration_seconds: 51300,
      duration_formatted: '14 hr 15 min',
      recommendation: {
        is_recommended: true,
        status: 'recommended',
        explanation: 'Safest corridor with calm weather and optimal duration. Zero Severe or High risk miles.',
      },
      risk_assessment: {
        overall_risk_level: 'low',
        risk_score: 14.2,
        severe_risk_miles: 0.0,
        high_risk_miles: 0.0,
        moderate_risk_miles: 45.0,
        low_risk_miles: 879.5,
        no_travel_miles: 0.0,
        no_travel_warning: false,
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [-87.6298, 41.8781], // Chicago, IL
          [-88.9056, 40.4842], // Bloomington, IL
          [-89.6501, 39.7817], // Springfield, IL
          [-90.1994, 38.6270], // St. Louis, MO
          [-91.2496, 36.9856], // Rolla / Poplar Bluff, MO
          [-92.2896, 34.7465], // Little Rock, AR
          [-94.0477, 33.4251], // Texarkana, TX
          [-96.7970, 32.7767], // Dallas, TX
        ],
      },
      checkpoints: [
        {
          sequence: 1,
          name: 'Departure: Chicago, IL',
          latitude: 41.8781,
          longitude: -87.6298,
          estimated_arrival: '2026-10-30T08:00:00Z',
          distance_from_origin_miles: 0.0,
          risk_level: 'low',
          risk_score: 10.0,
          weather: {
            timestamp: '2026-10-30T08:00:00Z',
            data_availability: 'available',
            temperature: 42.0,
            wind_speed_mph: 14.0,
            wind_gust_mph: 18.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 2,
          name: 'Waypoint 2: Bloomington, IL',
          latitude: 40.4842,
          longitude: -88.9056,
          estimated_arrival: '2026-10-30T10:15:00Z',
          distance_from_origin_miles: 135.0,
          risk_level: 'low',
          risk_score: 12.0,
          weather: {
            timestamp: '2026-10-30T10:15:00Z',
            data_availability: 'available',
            temperature: 46.0,
            wind_speed_mph: 18.0,
            wind_gust_mph: 22.0,
            precipitation_rate_in_per_hour: 0.02,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 3,
          name: 'Waypoint 3: Springfield, IL',
          latitude: 39.7817,
          longitude: -89.6501,
          estimated_arrival: '2026-10-30T11:45:00Z',
          distance_from_origin_miles: 202.0,
          risk_level: 'moderate',
          risk_score: 32.0,
          weather: {
            timestamp: '2026-10-30T11:45:00Z',
            data_availability: 'available',
            temperature: 49.0,
            wind_speed_mph: 28.0,
            wind_gust_mph: 34.0,
            precipitation_rate_in_per_hour: 0.12,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 4,
          name: 'Waypoint 4: St. Louis, MO',
          latitude: 38.6270,
          longitude: -90.1994,
          estimated_arrival: '2026-10-30T13:30:00Z',
          distance_from_origin_miles: 298.0,
          risk_level: 'low',
          risk_score: 15.0,
          weather: {
            timestamp: '2026-10-30T13:30:00Z',
            data_availability: 'available',
            temperature: 54.0,
            wind_speed_mph: 16.0,
            wind_gust_mph: 20.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 5,
          name: 'Waypoint 5: Little Rock, AR',
          latitude: 34.7465,
          longitude: -92.2896,
          estimated_arrival: '2026-10-30T18:00:00Z',
          distance_from_origin_miles: 645.0,
          risk_level: 'low',
          risk_score: 11.0,
          weather: {
            timestamp: '2026-10-30T18:00:00Z',
            data_availability: 'available',
            temperature: 62.0,
            wind_speed_mph: 12.0,
            wind_gust_mph: 15.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 6,
          name: 'Waypoint 6: Texarkana, TX',
          latitude: 33.4251,
          longitude: -94.0477,
          estimated_arrival: '2026-10-30T20:15:00Z',
          distance_from_origin_miles: 785.0,
          risk_level: 'low',
          risk_score: 10.0,
          weather: {
            timestamp: '2026-10-30T20:15:00Z',
            data_availability: 'available',
            temperature: 66.0,
            wind_speed_mph: 9.0,
            wind_gust_mph: 12.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 7,
          name: 'Arrival: Dallas, TX',
          latitude: 32.7767,
          longitude: -96.7970,
          estimated_arrival: '2026-10-30T22:15:00Z',
          distance_from_origin_miles: 924.5,
          risk_level: 'low',
          risk_score: 8.0,
          weather: {
            timestamp: '2026-10-30T22:15:00Z',
            data_availability: 'available',
            temperature: 68.0,
            wind_speed_mph: 8.0,
            wind_gust_mph: 10.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
      ],
    },
    {
      route_id: 'demo_route_alternative',
      display_name: 'Alternative via I-57 S & I-40 W',
      rank: 2,
      distance_miles: 958.2,
      distance_km: 1542.1,
      duration_seconds: 53700,
      duration_formatted: '14 hr 55 min',
      recommendation: {
        is_recommended: false,
        status: 'viable_alternative',
        explanation: 'Viable alternative, but encounters 38.0 High risk miles and higher wind gusts through Missouri.',
      },
      risk_assessment: {
        overall_risk_level: 'high',
        risk_score: 36.8,
        severe_risk_miles: 0.0,
        high_risk_miles: 38.0,
        moderate_risk_miles: 110.0,
        low_risk_miles: 810.2,
        no_travel_miles: 0.0,
        no_travel_warning: false,
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [-87.6298, 41.8781], // Chicago, IL
          [-87.8500, 41.1200], // Kankakee, IL
          [-88.2434, 40.1164], // Champaign, IL
          [-88.9500, 38.3000], // Mt. Vernon, IL
          [-89.9711, 35.1495], // Memphis, TN
          [-92.2896, 34.7465], // Little Rock, AR
          [-96.7970, 32.7767], // Dallas, TX
        ],
      },
      checkpoints: [
        {
          sequence: 1,
          name: 'Departure: Chicago, IL',
          latitude: 41.8781,
          longitude: -87.6298,
          estimated_arrival: '2026-10-30T08:00:00Z',
          distance_from_origin_miles: 0.0,
          risk_level: 'low',
          risk_score: 10.0,
          weather: {
            timestamp: '2026-10-30T08:00:00Z',
            data_availability: 'available',
            temperature: 42.0,
            wind_speed_mph: 14.0,
            wind_gust_mph: 18.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 2,
          name: 'Waypoint 2: Champaign, IL',
          latitude: 40.1164,
          longitude: -88.2434,
          estimated_arrival: '2026-10-30T10:30:00Z',
          distance_from_origin_miles: 135.0,
          risk_level: 'moderate',
          risk_score: 28.0,
          weather: {
            timestamp: '2026-10-30T10:30:00Z',
            data_availability: 'available',
            temperature: 45.0,
            wind_speed_mph: 26.0,
            wind_gust_mph: 32.0,
            precipitation_rate_in_per_hour: 0.08,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 3,
          name: 'Waypoint 3: Mt. Vernon, IL',
          latitude: 38.3000,
          longitude: -88.9500,
          estimated_arrival: '2026-10-30T12:45:00Z',
          distance_from_origin_miles: 260.0,
          risk_level: 'high',
          risk_score: 48.0,
          weather: {
            timestamp: '2026-10-30T12:45:00Z',
            data_availability: 'available',
            temperature: 49.0,
            wind_speed_mph: 38.0,
            wind_gust_mph: 45.0,
            precipitation_rate_in_per_hour: 0.28,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 4,
          name: 'Waypoint 4: Memphis, TN',
          latitude: 35.1495,
          longitude: -89.9711,
          estimated_arrival: '2026-10-30T16:00:00Z',
          distance_from_origin_miles: 520.0,
          risk_level: 'moderate',
          risk_score: 30.0,
          weather: {
            timestamp: '2026-10-30T16:00:00Z',
            data_availability: 'available',
            temperature: 58.0,
            wind_speed_mph: 24.0,
            wind_gust_mph: 30.0,
            precipitation_rate_in_per_hour: 0.10,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
        {
          sequence: 5,
          name: 'Arrival: Dallas, TX',
          latitude: 32.7767,
          longitude: -96.7970,
          estimated_arrival: '2026-10-30T22:55:00Z',
          distance_from_origin_miles: 958.2,
          risk_level: 'low',
          risk_score: 8.0,
          weather: {
            timestamp: '2026-10-30T22:55:00Z',
            data_availability: 'available',
            temperature: 68.0,
            wind_speed_mph: 8.0,
            wind_gust_mph: 10.0,
            precipitation_rate_in_per_hour: 0.0,
            snowfall_rate_in_per_hour: 0.0,
          },
        },
      ],
    },
  ],
}
