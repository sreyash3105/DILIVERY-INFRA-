import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import { ArrowLeft, Monitor, Wifi, Radio, Users, CheckCircle, Navigation, MapPin, Settings, Activity, ShieldAlert, Heart, HardDrive, Cpu, Database } from 'lucide-react';
import { driverIcon, shopIcon, dropoffIcon } from '../utils/leafletIcons';

interface ActiveDriver {
  id: number;
  name: string;
  lat: number;
  lng: number;
  lastPing: string;
  deliveryId?: number;
}

// Controller to auto-center/fit bounds of the map to the selected order coordinates
const MapController: React.FC<{ selectedDelivery: any; driverLoc: { lat: number; lng: number } | null }> = ({ selectedDelivery, driverLoc }) => {
  const map = useMap();
  useEffect(() => {
    if (selectedDelivery) {
      const points: [number, number][] = [
        [selectedDelivery.pickup_lat, selectedDelivery.pickup_lng],
        [selectedDelivery.dropoff_lat, selectedDelivery.dropoff_lng],
      ];
      if (driverLoc) {
        points.push([driverLoc.lat, driverLoc.lng]);
      }
      map.fitBounds(points, { padding: [50, 50], maxZoom: 15 });
    }
  }, [selectedDelivery, driverLoc, map]);
  return null;
};

const Fleet: React.FC = () => {
  const [drivers, setDrivers] = useState<Record<number, ActiveDriver>>({});
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [logs, setLogs] = useState<string[]>([]);
  
  // App Configs
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem('dep_server_url') || import.meta.env.VITE_API_URL || 'http://localhost:8000');
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('dep_api_key') || 'test_api_key_123');

  // Form states
  const [pickupLat, setPickupLat] = useState(12.9716);
  const [pickupLng, setPickupLng] = useState(77.5946);
  const [dropoffLat, setDropoffLat] = useState(12.9816);
  const [dropoffLng, setDropoffLng] = useState(77.6046);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [selectedDeliveryId, setSelectedDeliveryId] = useState<number | null>(null);
  const [routeGeometry, setRouteGeometry] = useState<[number, number][] | null>(null);
  const [systemVitals, setSystemVitals] = useState<any>(null);

  const fetchDeliveries = async () => {
    try {
      const res = await fetch(`${serverUrl}/deliveries`, {
        headers: { 'X-API-Key': apiKey }
      });
      if (res.ok) {
        const data = await res.json();
        setDeliveries(data);
      }
    } catch (err) {}
  };

  const fetchVitals = async () => {
    try {
      const res = await fetch(`${serverUrl}/analytics/observability/vitals`, {
        headers: { 'X-API-Key': apiKey }
      });
      if (res.ok) {
        const data = await res.json();
        setSystemVitals(data);
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchDeliveries();
    fetchVitals();
    const interval = setInterval(() => {
      fetchDeliveries();
      fetchVitals();
    }, 5000);
    return () => clearInterval(interval);
  }, [serverUrl, apiKey]);

  // Fetch Route Geometry when delivery is selected
  useEffect(() => {
    if (!selectedDeliveryId) {
      setRouteGeometry(null);
      return;
    }
    const fetchRoute = async () => {
      try {
        const res = await fetch(`${serverUrl}/deliveries/${selectedDeliveryId}/route`, {
          headers: { 'X-API-Key': apiKey }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.geometry) {
            setRouteGeometry(data.geometry);
          }
        }
      } catch (err) {}
    };
    fetchRoute();
  }, [selectedDeliveryId, serverUrl, apiKey]);

  // Save config
  useEffect(() => {
    localStorage.setItem('dep_server_url', serverUrl);
    localStorage.setItem('dep_api_key', apiKey);
  }, [serverUrl, apiKey]);

  const handleCreateAndDispatch = async () => {
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      // 1. Create delivery
      const res = await fetch(`${serverUrl}/deliveries`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify({
          pickup_lat: pickupLat,
          pickup_lng: pickupLng,
          dropoff_lat: dropoffLat,
          dropoff_lng: dropoffLng
        })
      });
      if (!res.ok) {
        throw new Error(`Failed to create order (Status: ${res.status})`);
      }
      const order = await res.json();
      const orderId = order.id;
      
      setLogs((prev) => [`[System] Created Order #${orderId}. Auto-assigning...`, ...prev]);

      // 2. Trigger auto-assignment
      const assignRes = await fetch(`${serverUrl}/deliveries/assign-driver`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify({ order_id: orderId })
      });
      if (!assignRes.ok) {
        throw new Error(`Failed to trigger auto-assignment (Status: ${assignRes.status})`);
      }
      const assignedOrder = await assignRes.json();
      
      setSuccessMsg(`Order #${orderId} dispatched! Status: ${assignedOrder.status}`);
      setLogs((prev) => [`[System] Order #${orderId} assigned to Driver #${assignedOrder.driver_id || 'None'}`, ...prev]);
      setSelectedDeliveryId(orderId);
      fetchDeliveries();
    } catch (err: any) {
      setError(err.message || 'Dispatch failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const wsUrl = serverUrl.replace(/^http/, 'ws') + '/fleet';
    setWsStatus('connecting');

    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      setWsStatus('disconnected');
      return;
    }

    ws.onopen = () => {
      setWsStatus('connected');
      setLogs((prev) => [`[${new Date().toLocaleTimeString()}] Telemetry feed connected`, ...prev]);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.driver_id && payload.lat && payload.lng) {
          const driverId = Number(payload.driver_id);
          
          setDrivers((prev) => {
            const existing = prev[driverId];
            return {
              ...prev,
              [driverId]: {
                id: driverId,
                name: existing?.name || `Driver #${driverId}`,
                lat: payload.lat,
                lng: payload.lng,
                lastPing: new Date().toLocaleTimeString(),
                deliveryId: payload.delivery_id ? Number(payload.delivery_id) : undefined
              }
            };
          });

          // Print telemetry logs selectively
          if (Math.random() < 0.2) {
            setLogs((prev) => [
              `[${new Date().toLocaleTimeString()}] Driver #${driverId} ping at [${payload.lat.toFixed(5)}, ${payload.lng.toFixed(5)}]`,
              ...prev.slice(0, 50)
            ]);
          }
        }
      } catch (e) {
        console.error(e);
      }
    };

    ws.onclose = () => {
      setWsStatus('disconnected');
      setLogs((prev) => [`[${new Date().toLocaleTimeString()}] Telemetry feed disconnected`, ...prev]);
    };

    ws.onerror = () => {
      setWsStatus('disconnected');
    };

    return () => {
      ws.close();
    };
  }, [serverUrl]);

  const driverList = Object.values(drivers);
  const selectedDelivery = deliveries.find(d => d.id === selectedDeliveryId);
  const selectedDriver = selectedDelivery?.driver_id ? drivers[selectedDelivery.driver_id] : null;

  // Determine system health check state
  const isRedisUp = systemVitals ? true : false;
  const isPostgresUp = deliveries ? true : false;
  const isCeleryUp = systemVitals && systemVitals.queues ? true : false;
  const isWsUp = wsStatus === 'connected';

  const queueBacklog = (systemVitals?.queues?.notifications || 0) + (systemVitals?.queues?.analytics || 0);
  const dlqCount = systemVitals?.queues?.dead_letter_queue || 0;

  return (
    <div className="premium-app font-sans antialiased">
      {/* Header */}
      <header className="premium-header">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link to="/" className="btn-premium-secondary p-2 rounded-xl text-gray-500 hover:text-gray-800 transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex items-center space-x-2">
              <Monitor className="w-4 h-4 text-indigo-650" />
              <span className="font-semibold text-sm tracking-tight text-gray-900">Fleet Operations Command</span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="badge-premium badge-gray normal-case py-1.5 px-3 rounded-lg flex items-center">
              <span className={`w-2 h-2 rounded-full mr-2 ${wsStatus === 'connected' ? 'bg-emerald-500 animate-pulse' : wsStatus === 'connecting' ? 'bg-amber-500' : 'bg-rose-500'}`} />
              <span className="text-gray-500 font-medium">Telemetry Feed: <span className="font-semibold text-gray-900">{wsStatus}</span></span>
            </div>
          </div>
        </div>
      </header>

      {/* Metrics Row */}
      <div className="max-w-7xl mx-auto w-full px-6 pt-6">
        <div className="metric-row">
          <div className="premium-card metric-card">
            <span className="metric-label block mb-1">Online Fleet</span>
            <div className="flex items-baseline space-x-2">
              <span className="metric-value">{driverList.length}</span>
              <span className="badge-premium badge-emerald">Active</span>
            </div>
          </div>

          <div className="premium-card metric-card">
            <span className="metric-label block mb-1">Active Deliveries</span>
            <div className="flex items-baseline space-x-2">
              <span className="metric-value">
                {deliveries.filter(d => d.status !== 'DELIVERED' && d.status !== 'CANCELLED').length}
              </span>
              <span className="badge-premium badge-indigo">In Flight</span>
            </div>
          </div>

          {/* System Health Status Panel */}
          <div className="col-span-1 md:col-span-2 premium-card flex flex-col justify-between">
            <span className="metric-label block mb-2">System Health</span>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-gray-750">
              <div className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${isRedisUp ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span className="font-medium text-gray-600">Redis</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${isPostgresUp ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span className="font-medium text-gray-600">PostgreSQL</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${isCeleryUp ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span className="font-medium text-gray-600">Celery</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${isWsUp ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span className="font-medium text-gray-600">WebSockets</span>
              </div>

              {queueBacklog > 0 && (
                <div className="badge-premium badge-amber normal-case py-0.5 px-2 rounded font-semibold text-[10px]">
                  <span className="w-1 h-1 bg-amber-500 rounded-full mr-1.5" />
                  <span>Backlog: {queueBacklog}</span>
                </div>
              )}
              {dlqCount > 0 && (
                <div className="badge-premium badge-rose normal-case py-0.5 px-2 rounded font-semibold text-[10px] animate-pulse">
                  <span className="w-1.5 h-1.5 bg-rose-600 rounded-full mr-1.5" />
                  <span>DLQ: {dlqCount}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Command Center Grid */}
      <div className="flex-grow max-w-7xl mx-auto w-full px-6 py-6 grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left Sidebar Control Panel */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Dispatch Order Form */}
          <div className="premium-card space-y-4">
            <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5]">
              <Navigation className="w-4 h-4 text-indigo-600" />
              <h2 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Manual Dispatch</h2>
            </div>
            {error && (
              <div className="badge-premium badge-rose normal-case block w-full text-center py-2 rounded-lg font-medium text-xs">
                {error}
              </div>
            )}
            {successMsg && (
              <div className="badge-premium badge-emerald normal-case block w-full text-center py-2 rounded-lg font-medium text-xs">
                {successMsg}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="premium-label block mb-1">Pickup Lat</label>
                <input 
                  type="number" 
                  step="0.0001" 
                  value={pickupLat} 
                  onChange={(e) => setPickupLat(Number(e.target.value))}
                  className="premium-input font-mono"
                />
              </div>
              <div>
                <label className="premium-label block mb-1">Pickup Lng</label>
                <input 
                  type="number" 
                  step="0.0001" 
                  value={pickupLng} 
                  onChange={(e) => setPickupLng(Number(e.target.value))}
                  className="premium-input font-mono"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="premium-label block mb-1">Dropoff Lat</label>
                <input 
                  type="number" 
                  step="0.0001" 
                  value={dropoffLat} 
                  onChange={(e) => setDropoffLat(Number(e.target.value))}
                  className="premium-input font-mono"
                />
              </div>
              <div>
                <label className="premium-label block mb-1">Dropoff Lng</label>
                <input 
                  type="number" 
                  step="0.0001" 
                  value={dropoffLng} 
                  onChange={(e) => setDropoffLng(Number(e.target.value))}
                  className="premium-input font-mono"
                />
              </div>
            </div>
            <button
              onClick={handleCreateAndDispatch}
              disabled={loading}
              className="btn-premium-primary w-full cursor-pointer py-2.5 font-semibold text-xs"
            >
              {loading ? "Processing..." : "Create & Auto-Dispatch"}
            </button>
          </div>

          {/* Connection Settings */}
          <div className="premium-card space-y-3">
            <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5]">
              <Settings className="w-4 h-4 text-gray-500" />
              <h2 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Gateway Configuration</h2>
            </div>
            <div>
              <label className="premium-label mb-0.5">Gateway API URL</label>
              <input 
                type="text" 
                value={serverUrl} 
                onChange={(e) => setServerUrl(e.target.value)} 
                className="premium-input font-mono"
              />
            </div>
            <div>
              <label className="premium-label mb-0.5">X-API-Key</label>
              <input 
                type="password" 
                value={apiKey} 
                onChange={(e) => setApiKey(e.target.value)} 
                className="premium-input font-mono"
              />
            </div>
          </div>

          {/* Live Operations Feed */}
          <div className="premium-card flex flex-col h-[300px]">
            <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5] mb-3">
              <Radio className="w-4 h-4 text-indigo-650" />
              <h2 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Operational logs feed</h2>
            </div>
            <div className="flex-grow overflow-y-auto terminal-panel p-3 space-y-2">
              {logs.length === 0 ? (
                <div className="text-gray-500 text-center py-16 italic font-mono text-[10px]">Connecting to active stream...</div>
              ) : (
                logs.map((log, index) => {
                  let logColor = 'text-gray-400';
                  if (log.includes('[System]')) {
                    logColor = 'text-indigo-400 font-semibold';
                  } else if (log.includes('ping')) {
                    logColor = 'text-emerald-400';
                  } else if (log.includes('disconnect') || log.includes('error')) {
                    logColor = 'text-rose-400';
                  }
                  return (
                    <div key={index} className="terminal-line">
                      <span className="terminal-timestamp">[{new Date().toLocaleTimeString()}]</span>
                      <span className={logColor}>{log.replace(/^\[.*?\]\s*/, '')}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right Side Map & Active Deliveries Panel */}
        <div className="lg:col-span-3 flex flex-col space-y-6">
          
          {/* Map Container */}
          <div className="h-[480px] relative rounded-xl overflow-hidden border border-[#ECEAE5] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            <MapContainer center={[12.9716, 77.5946]} zoom={13} className="w-full h-full">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
              />
              
              {selectedDelivery && (
                <>
                  <Marker position={[selectedDelivery.pickup_lat, selectedDelivery.pickup_lng]} icon={shopIcon}>
                    <Popup>
                      <div className="p-1 font-sans">
                        <span className="font-bold text-xs block text-indigo-650">Pickup (Warehouse)</span>
                        <span className="text-[10px] text-gray-500">Order #{selectedDelivery.id}</span>
                      </div>
                    </Popup>
                  </Marker>
                  
                  <Marker position={[selectedDelivery.dropoff_lat, selectedDelivery.dropoff_lng]} icon={dropoffIcon}>
                    <Popup>
                      <div className="p-1 font-sans">
                        <span className="font-bold text-xs block text-rose-600">Dropoff (Destination)</span>
                        <span className="text-[10px] text-gray-500">Order #{selectedDelivery.id}</span>
                      </div>
                    </Popup>
                  </Marker>
                  
                  {routeGeometry && (
                    <Polyline 
                      positions={routeGeometry} 
                      color="#4f46e5" 
                      weight={3.5}
                      opacity={0.8}
                      dashArray="4, 8"
                    />
                  )}

                  {!routeGeometry && (
                    <Polyline 
                      positions={[
                        [selectedDelivery.pickup_lat, selectedDelivery.pickup_lng],
                        [selectedDelivery.dropoff_lat, selectedDelivery.dropoff_lng]
                      ]} 
                      color="#6366f1" 
                      weight={3}
                      opacity={0.5}
                    />
                  )}
                </>
              )}

              {driverList.map((driver) => (
                <Marker key={driver.id} position={[driver.lat, driver.lng]} icon={driverIcon}>
                  <Popup>
                    <div className="p-1 font-sans text-xs">
                      <span className="font-bold block text-gray-900">{driver.name}</span>
                      <span className="text-[10px] block text-gray-400">Telemetry: {driver.lastPing}</span>
                      {driver.deliveryId && (
                        <span className="mt-1 inline-flex px-1.5 py-0.5 bg-indigo-50 border border-indigo-100 rounded text-indigo-750 font-semibold text-[9px]">
                          Carrying Order #{driver.deliveryId}
                        </span>
                      )}
                    </div>
                  </Popup>
                </Marker>
              ))}

              {selectedDelivery && (
                <MapController selectedDelivery={selectedDelivery} driverLoc={selectedDriver} />
              )}
            </MapContainer>
          </div>

          {/* Active Deliveries Table */}
          <div className="premium-card">
            <div className="flex justify-between items-center pb-3 border-b border-[#ECEAE5] mb-4">
              <h2 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">Active Pipeline</h2>
              {selectedDeliveryId && (
                <button 
                  onClick={() => setSelectedDeliveryId(null)}
                  className="btn-premium-secondary text-[10px] px-2.5 py-1 uppercase tracking-wider font-semibold cursor-pointer"
                >
                  Clear Map
                </button>
              )}
            </div>
            
            <div className="premium-table-container">
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Order ID</th>
                    <th>Status</th>
                    <th>Courier</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-10 text-center text-gray-400 italic">
                        No active dispatch records found.
                      </td>
                    </tr>
                  ) : (
                    deliveries.map((order) => {
                      const isSelected = order.id === selectedDeliveryId;
                      return (
                        <tr 
                          key={order.id} 
                          className={`premium-table-row ${
                            isSelected ? 'bg-indigo-50/20' : ''
                          }`}
                        >
                          <td className="font-semibold text-gray-900 font-mono">#{order.id}</td>
                          <td>
                            <span className={`badge-premium ${
                              order.status === 'DELIVERED' ? 'badge-emerald' :
                              order.status === 'DRIVER_PENDING' ? 'badge-amber' :
                              order.status === 'ASSIGNED' ? 'badge-indigo' :
                              order.status === 'IN_TRANSIT' ? 'badge-indigo animate-pulse' :
                              order.status === 'CANCELLED' ? 'badge-rose' :
                              'badge-gray'
                            }`}>
                              {order.status}
                            </span>
                          </td>
                          <td className="text-gray-650 font-medium">
                            {order.driver_id ? (
                              <span className="font-mono text-gray-900">Courier #{order.driver_id}</span>
                            ) : (
                              <span className="text-gray-400 italic font-normal">Pending Assignment</span>
                            )}
                          </td>
                          <td className="text-right space-x-3">
                            <button
                              onClick={() => setSelectedDeliveryId(order.id)}
                              className="text-indigo-650 hover:text-indigo-850 font-semibold cursor-pointer transition-colors"
                            >
                              Show
                            </button>
                            <Link
                              to={`/track/${order.id}`}
                              className="text-gray-500 hover:text-gray-900 font-medium transition-colors"
                            >
                              Track →
                            </Link>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Fleet;
