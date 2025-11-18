import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth endpoints
export const authAPI = {
  login: async (username, password) => {
    const response = await api.post('/auth/login', { username, password });
    return response.data;
  },
  register: async (username, password, email) => {
    const response = await api.post('/auth/register', { username, password, email });
    return response.data;
  },
  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

// Cities endpoints
export const citiesAPI = {
  getAll: async () => {
    const response = await api.get('/admin/cities');
    return response.data;
  },
  getOne: async (id) => {
    const response = await api.get(`/admin/cities/${id}`);
    return response.data;
  },
  create: async (data) => {
    const response = await api.post('/admin/cities', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await api.put(`/admin/cities/${id}`, data);
    return response.data;
  },
  delete: async (id) => {
    const response = await api.delete(`/admin/cities/${id}`);
    return response.data;
  },
};

// Addresses endpoints
export const addressesAPI = {
  getAll: async (params = {}) => {
    const response = await api.get('/admin/addresses', { params });
    return response.data;
  },
  getOne: async (id) => {
    const response = await api.get(`/admin/addresses/${id}`);
    return response.data;
  },
  create: async (data) => {
    const response = await api.post('/admin/addresses', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await api.put(`/admin/addresses/${id}`, data);
    return response.data;
  },
  delete: async (id) => {
    const response = await api.delete(`/admin/addresses/${id}`);
    return response.data;
  },
};

// Crowd Reports endpoints
export const reportsAPI = {
  getAll: async (params = {}) => {
    const response = await api.get('/admin/reports', { params });
    return response.data;
  },
  getOne: async (id) => {
    const response = await api.get(`/admin/reports/${id}`);
    return response.data;
  },
  delete: async (id) => {
    const response = await api.delete(`/admin/reports/${id}`);
    return response.data;
  },
  verify: async (id) => {
    const response = await api.post(`/admin/reports/${id}/verify`);
    return response.data;
  },
};

// Schedules endpoints
export const schedulesAPI = {
  getAll: async (params = {}) => {
    const response = await api.get('/admin/schedules', { params });
    return response.data;
  },
  getOne: async (id) => {
    const response = await api.get(`/admin/schedules/${id}`);
    return response.data;
  },
  create: async (data) => {
    const response = await api.post('/admin/schedules', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await api.put(`/admin/schedules/${id}`, data);
    return response.data;
  },
  delete: async (id) => {
    const response = await api.delete(`/admin/schedules/${id}`);
    return response.data;
  },
  bulkImport: async (data) => {
    const response = await api.post('/admin/schedules/bulk', data);
    return response.data;
  },
};

// Consensus endpoints
export const consensusAPI = {
  getAll: async (params = {}) => {
    const response = await api.get('/admin/consensus', { params });
    return response.data;
  },
  getStats: async () => {
    const response = await api.get('/admin/consensus/stats');
    return response.data;
  },
  recalculate: async (addressId) => {
    const response = await api.post(`/admin/consensus/${addressId}/recalculate`);
    return response.data;
  },
};

// Logs endpoints
export const logsAPI = {
  getAll: async (params = {}) => {
    const response = await api.get('/admin/logs', { params });
    return response.data;
  },
  getStats: async () => {
    const response = await api.get('/admin/logs/stats');
    return response.data;
  },
};

// Stats endpoints
export const statsAPI = {
  getDashboard: async () => {
    const response = await api.get('/stats');
    return response.data;
  },
  getMetrics: async (params = {}) => {
    const response = await api.get('/admin/metrics', { params });
    return response.data;
  },
};

// Analytics endpoints
export const analyticsAPI = {
  getHeatmap: async (params = {}) => {
    const response = await api.get('/analytics/heatmap', { params });
    return response.data;
  },
};

export default api;
