import { useEffect, useState } from 'react';
import { addressesAPI } from '../services/api';
import Header from '../components/Layout/Header';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { Search, Map as MapIcon, List } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

const Addresses = () => {
  const [addresses, setAddresses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState('list');
  const [filters] = useState({
    city: '',
    source: '',
  });

  useEffect(() => {
    fetchAddresses();
  }, []);

  const fetchAddresses = async () => {
    try {
      setLoading(true);
      const data = await addressesAPI.getAll(filters);
      setAddresses(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load addresses');
    } finally {
      setLoading(false);
    }
  };

  const filteredAddresses = addresses.filter((addr) =>
    addr.normalized_address?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    addr.city?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getSourceBadge = (source) => {
    const badges = {
      OFFICIAL: { label: 'Official', color: 'bg-blue-100 text-blue-800' },
      CROWD_VERIFIED: { label: 'Verified', color: 'bg-green-100 text-green-800' },
      CROWD_UNVERIFIED: { label: 'Unverified', color: 'bg-yellow-100 text-yellow-800' },
      UNKNOWN: { label: 'Unknown', color: 'bg-gray-100 text-gray-800' },
    };
    return badges[source] || badges.UNKNOWN;
  };

  return (
    <div className="flex-1">
      <Header title="Addresses" />

      <div className="p-8">
        {/* Toolbar */}
        <div className="flex justify-between items-center mb-6 gap-4">
          <div className="flex items-center gap-4 flex-1">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <input
                type="text"
                placeholder="Search addresses..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent w-full"
              />
            </div>

            <div className="flex items-center gap-2 bg-white border border-gray-300 rounded-lg p-1">
              <button
                onClick={() => setViewMode('list')}
                className={`px-3 py-1 rounded ${
                  viewMode === 'list' ? 'bg-blue-600 text-white' : 'text-gray-600'
                }`}
              >
                <List size={20} />
              </button>
              <button
                onClick={() => setViewMode('map')}
                className={`px-3 py-1 rounded ${
                  viewMode === 'map' ? 'bg-blue-600 text-white' : 'text-gray-600'
                }`}
              >
                <MapIcon size={20} />
              </button>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading addresses...</p>
            </div>
          </div>
        ) : viewMode === 'list' ? (
          /* List View */
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Address
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      City
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Trash Day
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Recycling
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Green Waste
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Source
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredAddresses.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="px-6 py-8 text-center text-gray-500">
                        No addresses found
                      </td>
                    </tr>
                  ) : (
                    filteredAddresses.slice(0, 100).map((address) => {
                      const badge = getSourceBadge(address.source);
                      return (
                        <tr key={address.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 text-sm font-medium text-gray-900">
                            {address.normalized_address}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {address.city}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {address.trash_day || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {address.recycling_day || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {address.green_day || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${badge.color}`}>
                              {badge.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
            {filteredAddresses.length > 100 && (
              <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 text-sm text-gray-600">
                Showing first 100 of {filteredAddresses.length} addresses
              </div>
            )}
          </div>
        ) : (
          /* Map View */
          <div className="bg-white rounded-lg shadow p-4">
            <div style={{ height: '600px', width: '100%' }}>
              <MapContainer
                center={[32.7942, -115.5630]}
                zoom={11}
                style={{ height: '100%', width: '100%', borderRadius: '8px' }}
              >
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                {filteredAddresses
                  .filter((addr) => addr.lat && addr.lon)
                  .slice(0, 200)
                  .map((address) => (
                    <Marker key={address.id} position={[address.lat, address.lon]}>
                      <Popup>
                        <div>
                          <p className="font-semibold">{address.normalized_address}</p>
                          <p className="text-sm text-gray-600">{address.city}</p>
                          <div className="mt-2 text-xs">
                            <p>Trash: {address.trash_day || '-'}</p>
                            <p>Recycling: {address.recycling_day || '-'}</p>
                            <p>Green: {address.green_day || '-'}</p>
                          </div>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
              </MapContainer>
            </div>
            {filteredAddresses.filter((a) => a.lat && a.lon).length > 200 && (
              <p className="text-sm text-gray-600 mt-4">
                Showing first 200 markers of {filteredAddresses.filter((a) => a.lat && a.lon).length} addresses with coordinates
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Addresses;
