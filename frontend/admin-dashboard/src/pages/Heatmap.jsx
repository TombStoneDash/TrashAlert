import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import { analyticsAPI, statsAPI } from '../services/api';
import Header from '../components/Layout/Header';
import { Filter, Loader } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// HeatLayer component using Leaflet's built-in heatmap functionality
const HeatLayer = ({ points }) => {
  const map = useMap();

  useEffect(() => {
    if (!points || points.length === 0) return;

    // Remove existing heat layers
    map.eachLayer((layer) => {
      if (layer instanceof L.CircleMarker && layer.options.className === 'heat-point') {
        map.removeLayer(layer);
      }
    });

    // Add heat points as circle markers with varying opacity and radius
    points.forEach((point) => {
      const circle = L.circleMarker([point.lat, point.lon], {
        radius: 10 + (point.intensity * 20), // Larger circles for higher intensity
        fillColor: getHeatColor(point.intensity),
        color: 'transparent',
        fillOpacity: 0.4 + (point.intensity * 0.4), // More opaque for higher intensity
        className: 'heat-point',
      });

      // Add popup with details
      if (point.details) {
        circle.bindPopup(`
          <div class="text-sm">
            <p class="font-semibold">${point.details.address || 'N/A'}</p>
            <p class="text-gray-600">${point.details.city || ''}</p>
            <p class="mt-2">Intensity: ${(point.intensity * 100).toFixed(0)}%</p>
            ${point.count ? `<p>Count: ${point.count}</p>` : ''}
            ${point.details.agreement_ratio ? `<p>Agreement: ${(point.details.agreement_ratio * 100).toFixed(0)}%</p>` : ''}
            ${point.details.latest_report ? `<p>Latest: ${new Date(point.details.latest_report).toLocaleDateString()}</p>` : ''}
          </div>
        `);
      }

      circle.addTo(map);
    });

    return () => {
      map.eachLayer((layer) => {
        if (layer instanceof L.CircleMarker && layer.options.className === 'heat-point') {
          map.removeLayer(layer);
        }
      });
    };
  }, [points, map]);

  return null;
};

// Helper function to get color based on intensity
const getHeatColor = (intensity) => {
  if (intensity < 0.2) return '#3b82f6'; // Blue (low)
  if (intensity < 0.4) return '#10b981'; // Green
  if (intensity < 0.6) return '#fbbf24'; // Yellow
  if (intensity < 0.8) return '#f97316'; // Orange
  return '#ef4444'; // Red (high)
};

const Heatmap = () => {
  const [heatmapData, setHeatmapData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [cities, setCities] = useState([]);
  const [filters, setFilters] = useState({
    metric: 'report_density',
    city: '',
    limit: 1000,
  });

  useEffect(() => {
    fetchCities();
    fetchHeatmapData();
  }, []);

  const fetchCities = async () => {
    try {
      const stats = await statsAPI.getDashboard();
      setCities(stats.cities || []);
    } catch (err) {
      console.error('Failed to fetch cities:', err);
    }
  };

  const fetchHeatmapData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await analyticsAPI.getHeatmap(filters);
      setHeatmapData(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load heatmap data');
      console.error('Heatmap error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleApplyFilters = () => {
    fetchHeatmapData();
  };

  const getMetricDescription = (metric) => {
    const descriptions = {
      report_density: 'Shows areas with high concentration of crowdsourced reports',
      low_confidence: 'Shows areas with low consensus agreement (potential issues)',
      high_activity: 'Shows addresses with most recent reporting activity (last 30 days)',
    };
    return descriptions[metric] || '';
  };

  // Calculate center and zoom based on data
  const getMapCenter = () => {
    if (!heatmapData || heatmapData.points.length === 0) {
      return [32.7942, -115.5630]; // Default to Imperial County
    }
    const avgLat = heatmapData.points.reduce((sum, p) => sum + p.lat, 0) / heatmapData.points.length;
    const avgLon = heatmapData.points.reduce((sum, p) => sum + p.lon, 0) / heatmapData.points.length;
    return [avgLat, avgLon];
  };

  return (
    <div className="flex-1">
      <Header title="Heatmap Analytics" />

      <div className="p-8">
        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="text-gray-600" size={20} />
            <h2 className="text-lg font-semibold text-gray-800">Filters</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Metric Type
              </label>
              <select
                value={filters.metric}
                onChange={(e) => handleFilterChange('metric', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="report_density">High Report Zones</option>
                <option value="low_confidence">Low Confidence Areas</option>
                <option value="high_activity">Recent Activity</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {getMetricDescription(filters.metric)}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                City Filter
              </label>
              <select
                value={filters.city}
                onChange={(e) => handleFilterChange('city', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">All Cities</option>
                {cities.map((city) => (
                  <option key={city.city} value={city.city}>
                    {city.city} ({city.address_count})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Max Points
              </label>
              <select
                value={filters.limit}
                onChange={(e) => handleFilterChange('limit', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="500">500</option>
                <option value="1000">1000</option>
                <option value="2000">2000</option>
                <option value="5000">5000</option>
              </select>
            </div>
          </div>

          <div className="mt-4">
            <button
              onClick={handleApplyFilters}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loading ? 'Loading...' : 'Apply Filters'}
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Heat Intensity Legend</h3>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full" style={{ backgroundColor: '#3b82f6' }}></div>
              <span className="text-sm text-gray-600">Low (0-20%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full" style={{ backgroundColor: '#10b981' }}></div>
              <span className="text-sm text-gray-600">Medium (20-40%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full" style={{ backgroundColor: '#fbbf24' }}></div>
              <span className="text-sm text-gray-600">Moderate (40-60%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full" style={{ backgroundColor: '#f97316' }}></div>
              <span className="text-sm text-gray-600">High (60-80%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full" style={{ backgroundColor: '#ef4444' }}></div>
              <span className="text-sm text-gray-600">Very High (80-100%)</span>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Map */}
        <div className="bg-white rounded-lg shadow p-4">
          {loading ? (
            <div className="flex items-center justify-center h-96">
              <div className="text-center">
                <Loader className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" />
                <p className="text-gray-600">Loading heatmap data...</p>
              </div>
            </div>
          ) : heatmapData ? (
            <>
              <div className="mb-4 flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">
                    {filters.metric === 'report_density' && 'High Report Zones'}
                    {filters.metric === 'low_confidence' && 'Low Confidence Areas'}
                    {filters.metric === 'high_activity' && 'Recent Activity Heatmap'}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {heatmapData.total_points} data points
                    {filters.city && ` in ${filters.city}`}
                  </p>
                </div>
                <div className="text-sm text-gray-500">
                  Generated: {new Date(heatmapData.generated_at).toLocaleString()}
                </div>
              </div>

              <div style={{ height: '600px', width: '100%' }}>
                <MapContainer
                  center={getMapCenter()}
                  zoom={11}
                  style={{ height: '100%', width: '100%', borderRadius: '8px' }}
                >
                  <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  />
                  <HeatLayer points={heatmapData.points} />
                </MapContainer>
              </div>

              {heatmapData.total_points === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No data available for the selected filters
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-96 text-gray-500">
              Select filters and click "Apply Filters" to view heatmap
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Heatmap;
