# TrashAlert Admin Dashboard

A full-featured React admin dashboard for managing TrashAlert's trash collection schedule system.

## Features

- **Authentication**: JWT-based login system with protected routes
- **Dashboard**: Overview with charts, statistics, and system metrics
- **Cities Management**: CRUD operations for city data
- **Addresses Management**: View addresses in list or map mode with Leaflet.js integration
- **Crowd Reports**: Review, verify, and manage user-submitted reports
- **Schedules Management**: Manage trash, recycling, and green waste collection schedules
- **Consensus Status**: View agreement levels and consensus data across addresses
- **Logs**: Advanced filtering and monitoring of API request logs

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Recharts** - Chart library for data visualization
- **Leaflet.js** - Interactive maps
- **Lucide React** - Icon library

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- TrashAlert API running (default: http://localhost:8000)

### Installation

```bash
# Install dependencies
npm install

# Create environment file
cp .env.example .env

# Edit .env and set your API URL
# VITE_API_BASE_URL=http://localhost:8000
```

### Development

```bash
# Start development server
npm run dev

# The dashboard will be available at http://localhost:5173
```

### Build for Production

```bash
# Build the application
npm run build

# Preview production build
npm run preview
```

## Authentication

**Note**: The authentication system requires backend API endpoints to be implemented:

- `POST /auth/login` - Login endpoint
- `GET /auth/me` - Get current user
- `POST /auth/register` - User registration (optional)

For development, you can bypass authentication by:
1. Modifying `src/context/AuthContext.jsx` to set a mock user
2. Or implementing a development login that sets a dummy token

## API Integration

The dashboard expects the following admin API endpoints:

### Cities
- `GET /admin/cities` - List all cities
- `POST /admin/cities` - Create city
- `PUT /admin/cities/:id` - Update city
- `DELETE /admin/cities/:id` - Delete city

### Addresses
- `GET /admin/addresses` - List addresses with filters
- `GET /admin/addresses/:id` - Get address details

### Reports
- `GET /admin/reports` - List crowd reports
- `POST /admin/reports/:id/verify` - Verify a report
- `DELETE /admin/reports/:id` - Delete report

### Schedules
- `GET /admin/schedules` - List schedules
- `POST /admin/schedules` - Create schedule
- `PUT /admin/schedules/:id` - Update schedule
- `DELETE /admin/schedules/:id` - Delete schedule

### Consensus
- `GET /admin/consensus` - Get consensus data
- `GET /admin/consensus/stats` - Get consensus statistics
- `POST /admin/consensus/:id/recalculate` - Recalculate consensus

### Logs
- `GET /admin/logs` - Get logs with filtering

### Stats
- `GET /stats` - Get dashboard statistics

## Project Structure

```
src/
├── components/
│   ├── Layout/
│   │   ├── DashboardLayout.jsx
│   │   ├── Header.jsx
│   │   └── Sidebar.jsx
│   └── ProtectedRoute.jsx
├── context/
│   └── AuthContext.jsx
├── pages/
│   ├── Addresses.jsx
│   ├── Cities.jsx
│   ├── Consensus.jsx
│   ├── CrowdReports.jsx
│   ├── Dashboard.jsx
│   ├── Logs.jsx
│   ├── Login.jsx
│   └── Schedules.jsx
├── services/
│   └── api.js
├── App.jsx
├── index.css
└── main.jsx
```

## Environment Variables

- `VITE_API_BASE_URL` - Base URL for the TrashAlert API (default: http://localhost:8000)

## Development Notes

### Mock Data

The dashboard includes fallback mock data for charts when the API doesn't return specific fields. This ensures the UI is functional during development.

### Authentication Bypass (Development Only)

To bypass authentication during development:

```javascript
// In src/context/AuthContext.jsx
const [user, setUser] = useState({ username: 'admin', id: 1 }); // Add mock user
```

### Leaflet CSS

Leaflet requires its CSS to be imported. This is already configured in the Addresses page.

## Contributing

1. Follow the existing code structure and naming conventions
2. Use Tailwind CSS for styling
3. Add proper error handling for API calls
4. Test with real API endpoints when available

## License

Part of the TrashAlert project.
