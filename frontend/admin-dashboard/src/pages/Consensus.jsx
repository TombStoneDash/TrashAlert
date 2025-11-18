import { useEffect, useState } from 'react';
import { consensusAPI } from '../services/api';
import Header from '../components/Layout/Header';
import { Search, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#10b981', '#f59e0b', '#ef4444', '#6b7280'];

const Consensus = () => {
  const [consensus, setConsensus] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchConsensus();
    fetchStats();
  }, []);

  const fetchConsensus = async () => {
    try {
      setLoading(true);
      const data = await consensusAPI.getAll();
      setConsensus(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load consensus data');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const data = await consensusAPI.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  const handleRecalculate = async (addressId) => {
    try {
      await consensusAPI.recalculate(addressId);
      fetchConsensus();
      fetchStats();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to recalculate consensus');
    }
  };

  const getAgreementColor = (level) => {
    if (level >= 80) return 'text-green-600 bg-green-100';
    if (level >= 60) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getAgreementIcon = (level) => {
    if (level >= 80) return <TrendingUp size={16} />;
    return <TrendingDown size={16} />;
  };

  const filteredConsensus = consensus.filter(
    (item) =>
      item.address?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.city?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Prepare chart data
  const agreementDistribution = [
    { name: 'High (80%+)', value: consensus.filter(c => c.agreement_level >= 80).length, color: '#10b981' },
    { name: 'Medium (60-79%)', value: consensus.filter(c => c.agreement_level >= 60 && c.agreement_level < 80).length, color: '#f59e0b' },
    { name: 'Low (<60%)', value: consensus.filter(c => c.agreement_level < 60).length, color: '#ef4444' },
  ];

  const reportDistribution = stats?.report_distribution || [
    { reports: '1', count: 120 },
    { reports: '2-3', count: 85 },
    { reports: '4-5', count: 45 },
    { reports: '6+', count: 28 },
  ];

  return (
    <div className="flex-1">
      <Header title="Consensus Status" />

      <div className="p-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <p className="text-sm font-medium text-gray-600">Total Addresses</p>
            <p className="text-3xl font-bold text-gray-900 mt-2">{consensus.length}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <p className="text-sm font-medium text-gray-600">High Agreement</p>
            <p className="text-3xl font-bold text-green-600 mt-2">
              {consensus.filter((c) => c.agreement_level >= 80).length}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <p className="text-sm font-medium text-gray-600">Medium Agreement</p>
            <p className="text-3xl font-bold text-yellow-600 mt-2">
              {consensus.filter((c) => c.agreement_level >= 60 && c.agreement_level < 80).length}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <p className="text-sm font-medium text-gray-600">Low Agreement</p>
            <p className="text-3xl font-bold text-red-600 mt-2">
              {consensus.filter((c) => c.agreement_level < 60).length}
            </p>
          </div>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              Agreement Level Distribution
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={agreementDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {agreementDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              Reports per Address
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={reportDistribution}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="reports" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#3b82f6" name="Addresses" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex justify-between items-center mb-6">
          <div className="relative flex-1 max-w-md">
            <Search
              className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
              size={20}
            />
            <input
              type="text"
              placeholder="Search consensus data..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent w-full"
            />
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Consensus Table */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading consensus data...</p>
            </div>
          </div>
        ) : (
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
                      Reports
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Agreement Level
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Consensus
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredConsensus.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="px-6 py-8 text-center text-gray-500">
                        No consensus data found
                      </td>
                    </tr>
                  ) : (
                    filteredConsensus.slice(0, 100).map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm font-medium text-gray-900">
                          {item.address}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {item.city}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {item.total_reports}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-3 py-1 inline-flex text-sm font-semibold rounded-full ${getAgreementColor(
                                item.agreement_level
                              )}`}
                            >
                              {item.agreement_level}%
                            </span>
                            {getAgreementIcon(item.agreement_level)}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          <div className="space-y-1">
                            {item.trash_day && <div>🗑️ {item.trash_day}</div>}
                            {item.recycling_day && <div>♻️ {item.recycling_day}</div>}
                            {item.green_day && <div>🌿 {item.green_day}</div>}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <button
                            onClick={() => handleRecalculate(item.id)}
                            className="text-blue-600 hover:text-blue-900"
                            title="Recalculate"
                          >
                            <RefreshCw size={18} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {filteredConsensus.length > 100 && (
              <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 text-sm text-gray-600">
                Showing first 100 of {filteredConsensus.length} addresses
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Consensus;
