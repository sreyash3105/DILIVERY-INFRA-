# Sandbox User Guide (Step-by-Step)

Follow these steps to run a complete, end-to-end delivery simulation on the live platform:

### 1. Register a Driver (Bring a Courier Online)
Before we can deliver packages, we need a courier ready and waiting on the road.
1. Open the Driver Simulator page (your deployed frontend URL + `/driver-simulator`).
2. Under **Register New Driver** on the left panel, enter any name (e.g., `Courier Sam`) and a phone number, then click **Register Driver**.
3. **What happens behind the scenes**: The application registers the courier in our PostgreSQL database, marks their status as `ONLINE`, and registers their coordinates in a high-speed **Redis Geo-Spatial Index**.
4. **What you will see**: The map will focus on their location in Bengaluru, India (our sandbox coordinates) showing a small bicycle icon. The console log at the bottom will confirm: `[System] Registered Driver "Courier Sam" with ID: X`.

### 2. Retrieve / Rotate Your Developer API Key
To act as a merchant (tenant) pushing orders to the delivery system, you need a secret API access key.
1. Open the Developer Portal page (your deployed frontend URL + `/developers`).
2. You will see a pre-loaded default key (`test_api_key_123`). If you want to simulate credential rotation, click **Rotate API Credentials** to instantly update security keys in-flight.
3. Keep this page open. You will notice that the code examples at the bottom of the portal automatically update with your active API key and the correct target URL. Copy this custom cURL snippet to your clipboard.

### 3. Place a Delivery Request
Submit a new order from your merchant store to the delivery system.
* **Option A: Terminal (Using cURL)**
  Open your computer's terminal (PowerShell, Command Prompt, or Terminal) and paste the copied cURL command, then press **Enter**.
  ```bash
  curl -X POST "http://localhost:8000/deliveries" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: YOUR_API_KEY" \
    -d '{
      "pickup_lat": 12.9716,
      "pickup_lng": 77.5946,
      "dropoff_lat": 12.9816,
      "dropoff_lng": 77.6046
    }'
  ```
* **Option B: Swagger Interactive Docs**
  Go to the Interactive API Docs at `http://localhost:8000/docs`, click **Authorize** at the top right, paste your API Key, select the `POST /deliveries` endpoint, click **Try it out**, edit coordinates if desired, and click **Execute**.
* **What happens behind the scenes**: The API validates your key, enforces a sliding-window rate limit in Redis (60 req/min), registers the order in PostgreSQL as `CREATED`, searches the Redis GEO index for nearby couriers within 5km, and instantly routes an order offer to your online driver.
* **What you will see**: The API will return a success JSON response containing a numeric `id` (e.g., `12`). Note down this **Delivery ID**!

### 4. Accept the Offer & Launch Live Tracking
Act as the courier accepting the work and let the customer watch their delivery update live.
1. Go back to the **Driver Simulator** page. A flashing banner will appear showing a new **Delivery Offer Assigned!** with your order details.
2. Click the **Accept Delivery Offer** button. This locks the courier to the order, updating the status to `ASSIGNED` in PostgreSQL.
3. Copy the numeric **Delivery ID** shown in the simulator banner.
4. In a new tab, open the Customer Tracking Page (your deployed frontend URL + `/`) and enter your delivery ID to open the tracking panel, or go directly to `YOUR_FRONTEND_URL/track/{delivery_id}`.

### 5. Simulate Driving & Watch Live GPS Updates
Move the courier along the route and see the real-time location stream in action.
1. Position the **Driver Simulator** and the **Customer Tracking Page** tabs side-by-side.
2. In the simulator map, click anywhere along the route path to place the red destination target marker, then click **Send GPS Ping**.
3. **What happens behind the scenes**: The simulator sends the new coordinate heartbeats to the API. The API instantly buffers them in a **Redis Stream** and publishes them to a **Redis Pub/Sub** channel. All load-balanced instances intercept this message and instantly broadcast it down to tracking browsers via active **WebSockets**.
4. **Ingestion Gatekeeper**: If you spam the ping button without moving the red marker, the backend will skip the database write. This gatekeeper filters out updates unless the driver moves > 20 meters or 10 seconds pass, saving **88%** of PostgreSQL disk write actions under heavy load.
5. **What you will see**: The bicycle icon will move in real-time on the tracking page map (and the operator's Fleet Map page) without any manual page refreshes!

### 6. Mark the Order as Delivered
Complete the package hand-off.
1. On the **Driver Simulator** dropdown, select **`DELIVERED`** as the new status.
2. Click **Update Status**.
3. **What happens behind the scenes**: The backend's strict state machine validates the delivery status change. PostgreSQL marks the order complete, updates billing and monthly usage statistics for the merchant, unlocks the driver, and cleanly terminates tracking WebSocket connections.
4. **What you will see**: The simulator clears the active order, the customer tracking page confirms that the order has arrived safely, and the courier returns to the online pool ready for the next order.
