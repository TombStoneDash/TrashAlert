---
sidebar_position: 4
title: Code Examples
slug: /api/examples
---

# Code Examples

Practical examples showing how to use the TrashAlert API in different programming languages.

## Table of Contents

1. [cURL](#curl) - Command line examples
2. [JavaScript](#javascript) - Browser and Node.js
3. [Python](#python) - Common HTTP library
4. [Java](#java) - Android and server applications

---

## cURL

### Lookup Address

```bash
# Simple lookup by address
curl "https://api.trashalert.com/v1/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"

# With pretty JSON output
curl -s "https://api.trashalert.com/v1/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA" | jq .

# By coordinates
curl "https://api.trashalert.com/v1/lookup?lat=32.7971&lon=-115.2645"

# With city filter
curl "https://api.trashalert.com/v1/lookup?address=Main%20St&city_id=CA_EL_CENTRO"
```

### Submit Report

```bash
# Submit a simple trash day report
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED"
  }'

# Submit complete report with all pickup days
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyApp/1.0" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WEDNESDAY",
    "recycling_day": "FRIDAY",
    "green_day": "WEDNESDAY",
    "user_hash": "user_abc123"
  }' | jq .
```

### Interpret Address

```bash
# Simple address
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "1122 Palmview Ave, El Centro, CA"
  }' | jq .

# Informal address text
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "my address is on main street in el centro near the post office"
  }' | jq .
```

### Get Statistics

```bash
# Get system stats
curl https://api.trashalert.com/v1/stats | jq .

# Just city breakdown
curl https://api.trashalert.com/v1/stats | jq '.cities'

# Pretty-print specific metrics
curl -s https://api.trashalert.com/v1/stats | jq '{
  total_addresses: .total_addresses,
  verified_percent: (.verified_consensus / .total_consensus * 100 | round)
}'
```

---

## JavaScript

### Basic Fetch Wrapper

```javascript
class TrashAlertAPI {
  constructor(baseUrl = 'https://api.trashalert.com/v1') {
    this.baseUrl = baseUrl;
    this.userHash = this.getOrCreateUserHash();
  }

  getOrCreateUserHash() {
    let hash = localStorage.getItem('trashalert_user_hash');
    if (!hash) {
      hash = this.generateRandomHash();
      localStorage.setItem('trashalert_user_hash', hash);
    }
    return hash;
  }

  generateRandomHash() {
    return Math.random().toString(36).substring(2, 15) +
           Math.random().toString(36).substring(2, 15);
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'TrashAlertApp/1.0',
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || `API Error: ${response.status}`);
    }

    return await response.json();
  }

  // Lookup endpoints
  lookup(address, cityId = null) {
    const params = new URLSearchParams({ address });
    if (cityId) params.append('city_id', cityId);
    return this.request(`/lookup?${params}`);
  }

  lookupByCoordinates(lat, lon) {
    const params = new URLSearchParams({ lat, lon });
    return this.request(`/lookup?${params}`);
  }

  // Report endpoint
  submitReport(address, trashDay, recyclingDay = null, greenDay = null) {
    const body = {
      address,
      trash_day: trashDay,
      user_hash: this.userHash
    };

    if (recyclingDay) body.recycling_day = recyclingDay;
    if (greenDay) body.green_day = greenDay;

    return this.request('/report', {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  // Interpret endpoint
  interpretAddress(text, useGeocoding = true) {
    return this.request('/interpret-address', {
      method: 'POST',
      body: JSON.stringify({
        text,
        use_geocoding: useGeocoding
      })
    });
  }

  // Stats endpoint
  getStats() {
    return this.request('/stats');
  }
}
```

### Usage Examples

```javascript
const api = new TrashAlertAPI();

// Lookup by address
async function lookupAndDisplay(address) {
  try {
    const result = await api.lookup(address);

    if (result.data_source === 'UNKNOWN') {
      console.log('Address not found');
      return;
    }

    console.log(`Address: ${result.matched_address}`);
    console.log(`Trash Day: ${result.trash_day_of_week}`);
    console.log(`Recycling: ${result.recycling_day_of_week}`);
    console.log(`Data Source: ${result.data_source}`);

    if (result.consensus_reports_count) {
      console.log(`Reports: ${result.consensus_reports_count}`);
      console.log(`Agreement: ${(result.consensus_agreement_ratio * 100).toFixed(0)}%`);
    }
  } catch (error) {
    console.error('Lookup failed:', error);
  }
}

// Submit report
async function submitTrashDayReport(address, day) {
  try {
    const result = await api.submitReport(address, day);

    console.log(`Report submitted for ${result.normalized_address}`);
    console.log(`Consensus Day: ${result.consensus.trash_day}`);
    console.log(`Reports: ${result.consensus.reports_count}`);
  } catch (error) {
    console.error('Report failed:', error);

    if (error.message.includes('429')) {
      alert('Too many reports. Please wait before submitting more.');
    }
  }
}

// Lookup nearby addresses
async function findAddressNearby(lat, lon) {
  try {
    const result = await api.lookupByCoordinates(lat, lon);

    if (result.data_source === 'UNKNOWN') {
      console.log('No address found at these coordinates');
      return;
    }

    console.log(`Found: ${result.matched_address}`);
    console.log(`Distance: ~${Math.round(Math.random() * 50)}m`);
  } catch (error) {
    console.error('Coordinate lookup failed:', error);
  }
}

// Get system stats
async function displaySystemStatus() {
  try {
    const stats = await api.getStats();

    const coverage = (stats.total_consensus / stats.total_addresses * 100).toFixed(1);
    const verification = (stats.verified_consensus / stats.total_consensus * 100).toFixed(1);

    console.log(`System Status:`);
    console.log(`- ${stats.total_addresses} addresses tracked`);
    console.log(`- ${stats.total_reports} community reports`);
    console.log(`- ${coverage}% coverage`);
    console.log(`- ${verification}% verified`);
  } catch (error) {
    console.error('Stats fetch failed:', error);
  }
}

// Interpret freeform address
async function parseUserInput(userText) {
  try {
    const result = await api.interpretAddress(userText);

    if (!result.success) {
      console.log('Could not understand address');
      return null;
    }

    console.log(`Understood: ${result.normalized_address}`);
    console.log(`Confidence: ${(result.confidence * 100).toFixed(0)}%`);
    console.log(`Method: ${result.interpretation_method}`);

    return result.normalized_address;
  } catch (error) {
    console.error('Interpretation failed:', error);
  }
}
```

### React Component Example

```jsx
import React, { useState } from 'react';
import { TrashAlertAPI } from './api';

function TrashScheduleLookup() {
  const [address, setAddress] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const api = new TrashAlertAPI();

  const handleLookup = async (e) => {
    e.preventDefault();
    if (!address) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.lookup(address);

      if (data.data_source === 'UNKNOWN') {
        setError('Address not found in database');
        setResult(null);
      } else {
        setResult(data);
      }
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleReport = async () => {
    if (!result) return;

    const day = window.prompt('What day is trash pickup?', 'WED');
    if (!day) return;

    try {
      const response = await api.submitReport(result.matched_address, day);
      alert(`Report submitted! Consensus: ${response.consensus.trash_day}`);
    } catch (err) {
      alert(`Report failed: ${err.message}`);
    }
  };

  return (
    <div className="lookup-widget">
      <h2>Find Your Trash Day</h2>

      <form onSubmit={handleLookup}>
        <input
          type="text"
          placeholder="Enter your address..."
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <h3>{result.matched_address}</h3>

          <div className="schedule">
            <p>
              <strong>Trash:</strong> {result.trash_day_of_week || 'N/A'}
            </p>
            <p>
              <strong>Recycling:</strong> {result.recycling_day_of_week || 'N/A'}
            </p>
            <p>
              <strong>Green Waste:</strong> {result.green_waste_day_of_week || 'N/A'}
            </p>
          </div>

          <p className="source">
            Data: {result.data_source}
            {result.consensus_reports_count && (
              ` (${result.consensus_reports_count} reports, ${
                (result.consensus_agreement_ratio * 100).toFixed(0)
              }% agreement)`
            )}
          </p>

          <button onClick={handleReport} className="report-btn">
            Report Your Schedule
          </button>
        </div>
      )}
    </div>
  );
}

export default TrashScheduleLookup;
```

---

## Python

### Complete Python Client

```python
import requests
import hashlib
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode

class TrashAlertClient:
    """TrashAlert API client for Python."""

    def __init__(self, base_url: str = 'https://api.trashalert.com/v1'):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TrashAlertPythonClient/1.0',
            'Content-Type': 'application/json'
        })
        self.user_hash = self._get_user_hash()

    def _get_user_hash(self) -> str:
        """Generate a stable user hash."""
        import uuid
        device_id = str(uuid.getnode())
        return hashlib.sha256(device_id.encode()).hexdigest()[:32]

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """Make an API request."""
        url = f'{self.base_url}{endpoint}'

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=timeout
            )

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded") from e
            elif e.response.status_code == 404:
                raise NotFoundError("Not found") from e
            else:
                raise APIError(f"API Error: {e.response.status_code}") from e

    def lookup(
        self,
        address: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Lookup trash schedule."""
        params = {}

        if address:
            params['address'] = address
        if lat is not None and lon is not None:
            params['lat'] = lat
            params['lon'] = lon
        if city_id:
            params['city_id'] = city_id

        if not params:
            raise ValueError("Provide either address or lat/lon coordinates")

        return self._request('GET', '/lookup', params=params)

    def submit_report(
        self,
        address: str,
        trash_day: Optional[str] = None,
        recycling_day: Optional[str] = None,
        green_day: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a crowdsourced report."""
        if not any([trash_day, recycling_day, green_day]):
            raise ValueError("At least one pickup day must be provided")

        body = {
            'address': address,
            'user_hash': self.user_hash
        }

        if trash_day:
            body['trash_day'] = trash_day.upper()
        if recycling_day:
            body['recycling_day'] = recycling_day.upper()
        if green_day:
            body['green_day'] = green_day.upper()

        return self._request('POST', '/report', json=body)

    def interpret_address(
        self,
        text: str,
        use_geocoding: bool = True
    ) -> Dict[str, Any]:
        """Interpret freeform address text."""
        body = {
            'text': text,
            'use_geocoding': use_geocoding
        }

        return self._request('POST', '/interpret-address', json=body)

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        return self._request('GET', '/stats')


# Custom exceptions
class TrashAlertError(Exception):
    """Base exception."""
    pass


class RateLimitError(TrashAlertError):
    """Rate limit exceeded."""
    pass


class NotFoundError(TrashAlertError):
    """Resource not found."""
    pass


class APIError(TrashAlertError):
    """General API error."""
    pass
```

### Usage Examples

```python
from trashalert import TrashAlertClient, RateLimitError

client = TrashAlertClient()

# Lookup address
result = client.lookup('1122 Palmview Ave, El Centro, CA')

if result['data_source'] == 'UNKNOWN':
    print('Address not found')
else:
    print(f"Trash Day: {result['trash_day_of_week']}")
    print(f"Source: {result['data_source']}")

    if result.get('consensus_reports_count'):
        print(f"Based on {result['consensus_reports_count']} reports")

# Submit a report
try:
    response = client.submit_report(
        address='1122 Palmview Ave, El Centro, CA',
        trash_day='WED',
        recycling_day='FRI'
    )

    print(f"Report submitted!")
    print(f"Consensus: {response['consensus']}")
except RateLimitError:
    print("Rate limited, please try again later")

# Interpret freeform text
result = client.interpret_address(
    'my address is on main street in el centro'
)

if result['success']:
    print(f"Interpreted: {result['normalized_address']}")
    print(f"Confidence: {result['confidence']:.0%}")
else:
    print("Could not interpret address")

# Get stats
stats = client.get_stats()
print(f"Coverage: {stats['total_addresses']} addresses")
print(f"Verification: {stats['verified_consensus']} verified")
```

---

## Java

### Simple HTTP Client

```java
import okhttp3.*;
import com.google.gson.*;
import java.io.IOException;

public class TrashAlertClient {
    private static final String BASE_URL = "https://api.trashalert.com/v1";
    private final OkHttpClient httpClient;
    private final Gson gson;

    public TrashAlertClient() {
        this.httpClient = new OkHttpClient();
        this.gson = new Gson();
    }

    public JsonObject lookup(String address) throws IOException {
        String url = BASE_URL + "/lookup?address=" +
            URLEncoder.encode(address, "UTF-8");

        Request request = new Request.Builder()
            .url(url)
            .addHeader("User-Agent", "TrashAlertAndroid/1.0")
            .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("API error: " + response.code());
            }

            return JsonParser.parseString(response.body().string())
                .getAsJsonObject();
        }
    }

    public JsonObject submitReport(
        String address,
        String trashDay
    ) throws IOException {
        JsonObject body = new JsonObject();
        body.addProperty("address", address);
        body.addProperty("trash_day", trashDay.toUpperCase());
        body.addProperty("user_hash", generateUserHash());

        Request request = new Request.Builder()
            .url(BASE_URL + "/report")
            .post(RequestBody.create(
                body.toString(),
                MediaType.get("application/json")
            ))
            .addHeader("User-Agent", "TrashAlertAndroid/1.0")
            .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("API error: " + response.code());
            }

            return JsonParser.parseString(response.body().string())
                .getAsJsonObject();
        }
    }

    private String generateUserHash() {
        // Generate stable hash based on device ID
        return android.provider.Settings.Secure
            .getString(context.getContentResolver(), "android_id")
            .substring(0, 16);
    }
}
```

### Android Fragment Example

```java
public class TrashScheduleFragment extends Fragment {
    private TrashAlertClient apiClient;
    private EditText addressInput;
    private TextView resultView;

    @Override
    public View onCreateView(
        LayoutInflater inflater,
        ViewGroup container,
        Bundle savedInstanceState
    ) {
        View view = inflater.inflate(
            R.layout.fragment_trash_schedule,
            container,
            false
        );

        apiClient = new TrashAlertClient();
        addressInput = view.findViewById(R.id.address_input);
        resultView = view.findViewById(R.id.result_text);

        view.findViewById(R.id.search_button).setOnClickListener(
            v -> performLookup()
        );

        return view;
    }

    private void performLookup() {
        String address = addressInput.getText().toString();
        if (address.isEmpty()) return;

        resultView.setText("Searching...");

        new Thread(() -> {
            try {
                JsonObject result = apiClient.lookup(address);

                String text;
                if (result.get("data_source").getAsString()
                    .equals("UNKNOWN")) {
                    text = "Address not found";
                } else {
                    text = String.format(
                        "Trash Day: %s\nRecycling: %s",
                        result.get("trash_day_of_week").getAsString(),
                        result.get("recycling_day_of_week").getAsString()
                    );
                }

                resultView.post(() -> resultView.setText(text));
            } catch (IOException e) {
                resultView.post(() ->
                    resultView.setText("Error: " + e.getMessage())
                );
            }
        }).start();
    }
}
```

---

## Error Handling

### Common Patterns

**JavaScript:**
```javascript
try {
  const result = await api.lookup(address);
} catch (error) {
  if (error.message.includes('429')) {
    // Rate limit: exponential backoff
    await delay(Math.pow(2, retryCount) * 1000);
  } else if (error.message.includes('404')) {
    // Not found: ask user to try again
    alert('Address not found');
  } else {
    // Other error: show generic message
    alert('An error occurred. Please try again.');
  }
}
```

**Python:**
```python
try:
    result = client.lookup(address)
except RateLimitError:
    time.sleep(exponential_backoff_time)
    # Retry
except NotFoundError:
    print("Address not found")
except APIError as e:
    print(f"Error: {e}")
```

---

