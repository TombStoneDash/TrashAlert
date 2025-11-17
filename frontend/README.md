# TrashAlert Frontend

A simple, single-page web UI for testing the TrashAlert trash and recycling collection lookup API.

## Features

- Clean, modern interface with gradient design
- Address input field with real-time API lookup
- Color-coded result cards for different collection types:
  - 🗑️ Trash Collection (Green border)
  - ♻️ Recycling Collection (Blue border)
  - 🌿 Green Waste Collection (Lime border)
- Configurable API endpoint URL (saved to localStorage)
- Debug panel showing raw JSON responses
- Responsive design that works on mobile and desktop
- Error handling with user-friendly messages
- Loading states with animated spinner

## Setup Instructions

### Prerequisites

- Python 3.7+ (for running the backend API)
- A modern web browser (Chrome, Firefox, Safari, Edge)

### Running the Backend API

Before using the frontend, you need to start the backend API server.

1. Navigate to the project root directory:
   ```bash
   cd /path/to/TrashAlert
   ```

2. Install backend dependencies (if not already installed):
   ```bash
   pip install fastapi uvicorn
   # Add any other dependencies your API needs
   ```

3. Start the API server:
   ```bash
   # If you have a main.py or api.py file:
   uvicorn main:app --reload --port 8000

   # Or if your API is in a different file:
   uvicorn your_api_file:app --reload --port 8000
   ```

4. Verify the API is running by visiting:
   ```
   http://localhost:8000/docs
   ```
   (FastAPI automatically provides interactive API documentation)

### Running the Frontend

The frontend is a simple static HTML page with no build step required. You have several options:

#### Option 1: Python HTTP Server (Recommended)

From the `frontend/` directory:

```bash
cd frontend
python -m http.server 8080
```

Then open your browser to:
```
http://localhost:8080
```

#### Option 2: Python 3 HTTP Server (Alternative)

```bash
cd frontend
python3 -m http.server 8080
```

#### Option 3: Direct File Access

Simply open the `index.html` file directly in your browser:

```bash
# On Linux/Mac:
open frontend/index.html

# Or just drag and drop the file into your browser
```

**Note:** When using direct file access, you may encounter CORS issues when calling the API. Using a local server (Options 1 or 2) is recommended.

#### Option 4: VS Code Live Server

If you're using Visual Studio Code:

1. Install the "Live Server" extension
2. Right-click on `index.html`
3. Select "Open with Live Server"

## Usage

1. **Start the Backend API** (see above)
2. **Start the Frontend** (see above)
3. **Open the Frontend** in your browser
4. **Configure the API URL** (if different from `http://localhost:8000/lookup`)
   - The default is `http://localhost:8000/lookup`
   - You can change this in the "API Endpoint" field
   - The URL is saved to your browser's localStorage
5. **Enter an Address** in the search box
   - Example: `123 Main St, Brawley`
   - Example: `2158 Main St`
6. **Click "Look Up"** to fetch collection schedule
7. **View Results** in the color-coded cards
8. **Check Debug Panel** (click to expand) to see the raw JSON response

## API Contract

The frontend expects the API to respond with the following JSON structure:

### Request

```
GET /lookup?address=123+Main+St,+Brawley
```

### Response (Success)

```json
{
  "address": "123 Main St, Brawley",
  "zone": "Zone A",
  "trash_day": "Monday",
  "recycling_day": "Wednesday",
  "green_waste_day": "Friday"
}
```

### Response (Error)

```json
{
  "error": "Address not found",
  "detail": "The specified address could not be matched to any known location"
}
```

## Customization

### Changing the Default API URL

Edit `index.html` and find this line:

```javascript
value="http://localhost:8000/lookup"
```

Change it to your desired default API URL.

### Styling

All CSS is embedded in the `<style>` tag in `index.html`. You can modify:
- Colors (search for color codes like `#667eea`)
- Spacing (search for `padding`, `margin`)
- Card layout (search for `.result-card`)
- Fonts (search for `font-family`)

## Troubleshooting

### CORS Errors

If you see CORS errors in the browser console:

1. Make sure you're running the frontend through a local server (not opening the file directly)
2. Add CORS middleware to your FastAPI backend:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### API Not Responding

1. Check that the backend is running: `http://localhost:8000/docs`
2. Verify the API URL in the frontend matches your backend
3. Check the browser console for error messages
4. Check the Debug Panel for the actual error response

### No Results Showing

1. Open the Debug Panel to see the raw API response
2. Verify the API is returning the expected JSON structure
3. Check the browser console for JavaScript errors

## Development

The frontend is built with vanilla JavaScript (no frameworks or build tools) for maximum simplicity. All code is in a single `index.html` file:

- **HTML**: Structure and form elements
- **CSS**: Embedded in `<style>` tag, uses CSS Grid and Flexbox
- **JavaScript**: Embedded in `<script>` tag, handles API calls and DOM updates

To make changes, simply edit `index.html` and refresh your browser.

## Browser Compatibility

Tested and working on:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

Uses modern JavaScript features like:
- `async/await`
- `fetch` API
- `URLSearchParams`
- ES6+ syntax

## License

Same as the main TrashAlert project.
