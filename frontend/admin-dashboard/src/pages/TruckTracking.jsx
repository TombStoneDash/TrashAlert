import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import { Truck, RefreshCw, Navigation, Clock } from 'lucide-react';
import Header from '../components/Layout/Header';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default marker icon in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Create custom truck icon
const createTruckIcon = (status) => {
  const colors = {
    active: '#10b981',
    inactive: '#6b7280',
    maintenance: '#f59e0b'
  };

  const color = colors[status] || colors.active;

  return L.divIcon({
    className: 'custom-truck-marker',
    html: `
      <div style="
        background-color: ${color};
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 3px solid white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
      ">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"></path>
          <path d="M15 18H9"></path>
          <path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"></path>
          <circle cx="17" cy="18" r="2"></circle>
          <circle cx="7" cy="18" r="2"></circle>
        </svg>
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
};

const TruckTracking = () => {
  const [trucks, setTrucks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTruck, setSelectedTruck] = useState(null);
  const [truckTrail, setTruckTrail] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);

  const fetchTrucks = async () => {
    try {
      const response = await fetch('/api/gps/trucks');
      if (!response.ok) throw new Error('Failed to fetch trucks');
      const data = await response.json();
      setTrucks(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching trucks:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTruckTrail = async (truckId) => {
    try {
      const response = await fetch(`/api/gps/trucks/${truckId}/trail?limit=50`);
      if (!response.ok) throw new Error('Failed to fetch truck trail');
      const data = await response.json();
      setTruckTrail(data);
    } catch (err) {
      console.error('Error fetching truck trail:', err);
    }
  };

  useEffect(() => {
    fetchTrucks();

    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        fetchTrucks();
        if (selectedTruck) {
          fetchTruckTrail(selectedTruck.id);
        }
      }, 10000); // Refresh every 10 seconds
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh, selectedTruck]);

  const handleTruckClick = (truck) => {
    setSelectedTruck(truck);
    if (truck.id) {
      fetchTruckTrail(truck.id);
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'No data';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const trucksWithLocation = trucks.filter(t => t.latest_location);
  const defaultCenter = trucksWithLocation.length > 0 && trucksWithLocation[0].latest_location
    ? [trucksWithLocation[0].latest_location.lat, trucksWithLocation[0].latest_location.lon]
    : [37.7749, -122.4194]; // Default to San Francisco

  const trailCoordinates = truckTrail.map(loc => [loc.lat, loc.lon]);

  return (
    <div className="flex-1">
      <Header title="Truck GPS Tracking" />

      <div className="p-8">
        {/* Controls */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => fetchTrucks()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <RefreshCw size={20} />
              Refresh Now
            </button>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm text-gray-700">Auto-refresh (10s)</span>
            </label>
          </div>

          <div className="text-sm text-gray-600">
            Active Trucks: <span className="font-semibold">{trucksWithLocation.length}</span> / {trucks.length}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Truck List */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-800">Fleet Status</h3>
              </div>

              <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
                {loading ? (
                  <div className="p-4 text-center text-gray-500">Loading trucks...</div>
                ) : trucks.length === 0 ? (
                  <div className="p-4 text-center text-gray-500">No trucks found</div>
                ) : (
                  trucks.map((truck) => (
                    <div
                      key={truck.id}
                      onClick={() => handleTruckClick(truck)}
                      className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                        selectedTruck?.id === truck.id ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${
                            truck.status === 'active' ? 'bg-green-100' :
                            truck.status === 'maintenance' ? 'bg-yellow-100' :
                            'bg-gray-100'
                          }`}>
                            <Truck size={20} className={
                              truck.status === 'active' ? 'text-green-600' :
                              truck.status === 'maintenance' ? 'text-yellow-600' :
                              'text-gray-600'
                            } />
                          </div>
                          <div>
                            <div className="font-semibold text-gray-800">
                              Truck #{truck.truck_number}
                            </div>
                            <div className="text-xs text-gray-500">
                              {truck.license_plate || 'No plate'}
                            </div>
                            <div className="text-xs text-gray-500 capitalize">
                              {truck.vehicle_type || 'Trash'}
                            </div>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className={`inline-block px-2 py-1 text-xs rounded-full ${
                            truck.status === 'active' ? 'bg-green-100 text-green-800' :
                            truck.status === 'maintenance' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {truck.status}
                          </span>
                        </div>
                      </div>

                      {truck.latest_location && (
                        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-600">
                          <div className="flex items-center gap-1 mb-1">
                            <Navigation size={12} />
                            <span>
                              {truck.latest_location.speed_mph?.toFixed(1) || '0.0'} mph
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock size={12} />
                            <span>{formatTimestamp(truck.latest_location.timestamp)}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Map View */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: '600px' }}>
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-gray-500">Loading map...</div>
                </div>
              ) : trucksWithLocation.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Truck size={48} className="text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No active trucks with GPS data</p>
                  </div>
                </div>
              ) : (
                <MapContainer
                  center={defaultCenter}
                  zoom={13}
                  style={{ height: '100%', width: '100%' }}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />

                  {/* Truck Markers */}
                  {trucksWithLocation.map((truck) => (
                    <Marker
                      key={truck.id}
                      position={[truck.latest_location.lat, truck.latest_location.lon]}
                      icon={createTruckIcon(truck.status, truck.vehicle_type)}
                      eventHandlers={{
                        click: () => handleTruckClick(truck),
                      }}
                    >
                      <Popup>
                        <div className="p-2">
                          <h3 className="font-semibold text-gray-800 mb-2">
                            Truck #{truck.truck_number}
                          </h3>
                          <div className="text-sm space-y-1">
                            <p>
                              <strong>Status:</strong> {truck.status}
                            </p>
                            <p>
                              <strong>Type:</strong> {truck.vehicle_type || 'Trash'}
                            </p>
                            <p>
                              <strong>Speed:</strong> {truck.latest_location.speed_mph?.toFixed(1) || '0.0'} mph
                            </p>
                            <p>
                              <strong>Heading:</strong> {truck.latest_location.heading_degrees?.toFixed(0) || 'N/A'}°
                            </p>
                            <p>
                              <strong>Last Update:</strong>{' '}
                              {formatTimestamp(truck.latest_location.timestamp)}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              {truck.latest_location.lat.toFixed(6)}, {truck.latest_location.lon.toFixed(6)}
                            </p>
                          </div>
                        </div>
                      </Popup>
                    </Marker>
                  ))}

                  {/* Trail polyline for selected truck */}
                  {selectedTruck && trailCoordinates.length > 0 && (
                    <Polyline
                      positions={trailCoordinates}
                      color="#3b82f6"
                      weight={3}
                      opacity={0.7}
                    />
                  )}
                </MapContainer>
              )}
            </div>

            {/* Trail info */}
            {selectedTruck && truckTrail.length > 0 && (
              <div className="mt-4 bg-white rounded-lg shadow p-4">
                <h4 className="font-semibold text-gray-800 mb-2">
                  Trail for Truck #{selectedTruck.truck_number}
                </h4>
                <p className="text-sm text-gray-600">
                  Showing last {truckTrail.length} location points
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TruckTracking;
