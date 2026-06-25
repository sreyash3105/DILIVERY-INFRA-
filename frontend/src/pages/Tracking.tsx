import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import { ArrowLeft, Clock, MapPin, Wifi, AlertTriangle, RefreshCw, Navigation, Compass } from 'lucide-react';
import { driverIcon, shopIcon, dropoffIcon } from '../utils/leafletIcons';

// Sub-component to recenter and fit map bounds to pickup, dropoff and driver coordinates
const MapController: React.FC<{ order: any; driverLoc: { lat: number; lng: number } | null }> = ({ order, driverLoc }) => {
  const map = useMap();
  useEffect(() => {
    if (order) {
      const points: [number, number][] = [
        [order.pickup_lat, order.pickup_lng],
        [order.dropoff_lat, order.dropoff_lng]
      ];
      if (driverLoc) {
        points.push([driverLoc.lat, driverLoc.lng]);
      }
      map.fitBounds(points, { padding: [50, 50], maxZoom: 15 });
    }
  }, [order, driverLoc, map]);
  return null;
};

const Tracking: React.FC = () => {
  const { deliveryId } = useParams<{ deliveryId: string }>();
  const [order, setOrder] = useState<any>(null);
  const [driverLoc, setDriverLoc] = useState<{ lat: number; lng: number } | null>(null);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  const [etaData, setEtaData] = useState<{ eta_minutes: number; distance_meters: number } | null>(null);
  const [transitions, setTransitions] = useState<any[]>([]);
  const [routeGeometry, setRouteGeometry] = useState<[number, number][] | null>(null);

  // App Configs
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem('dep_server_url') || import.meta.env.VITE_API_URL || 'http://localhost:8000');
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('dep_api_key') || 'test_api_key_123');

  // Save configs
  useEffect(() => {
    localStorage.setItem('dep_server_url', serverUrl);
    localStorage.setItem('dep_api_key', apiKey);
  }, [serverUrl, apiKey]);

  // Fetch transitions
  const fetchTransitions = async () => {
    if (!deliveryId) return;
    try {
      const res = await fetch(`${serverUrl}/deliveries/${deliveryId}/transitions`, {
        headers: { 'X-API-Key': apiKey }
      });
      if (res.ok) {
        const data = await res.json();
        setTransitions(data);
      }
    } catch (err) {}
  };

  // Fetch ETA / distance details
  const fetchEta = async () => {
    if (!deliveryId) return;
    try {
      const res = await fetch(`${serverUrl}/deliveries/${deliveryId}/eta`, {
        headers: { 'X-API-Key': apiKey }
      });
      if (res.ok) {
        const data = await res.json();
        setEtaData({
          eta_minutes: data.eta_minutes,
          distance_meters: data.distance_meters
        });
      } else {
        setEtaData(null);
      }
    } catch (err) {
      setEtaData(null);
    }
  };

  // Fetch route geometry
  const fetchRoute = async () => {
    if (!deliveryId) return;
    try {
      const res = await fetch(`${serverUrl}/deliveries/${deliveryId}/route`, {
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

  // 1. Fetch initial order details
  const fetchOrder = async () => {
    try {
      setError(null);
      const res = await fetch(`${serverUrl}/deliveries/${deliveryId}`, {
        headers: { 'X-API-Key': apiKey }
      });
      if (!res.ok) {
        throw new Error(`Failed to load order info (Status: ${res.status})`);
      }
      const data = await res.json();
      setOrder(data);
      
      // If driver is already assigned and has location, set it
      if (data.driver_id) {
        const driverRes = await fetch(`${serverUrl}/drivers/${data.driver_id}`);
        if (driverRes.ok) {
          const driverData = await driverRes.json();
          if (driverData.current_lat && driverData.current_lng) {
            setDriverLoc({ lat: driverData.current_lat, lng: driverData.current_lng });
          }
        }
      }
    } catch (err: any) {
      setError(err.message || 'Error occurred');
    }
  };

  const syncAllData = () => {
    fetchOrder();
    fetchTransitions();
    fetchEta();
    fetchRoute();
  };

  useEffect(() => {
    if (deliveryId) {
      syncAllData();
    }
  }, [deliveryId, serverUrl, apiKey]);

  // Periodic polling for ETA and transitions
  useEffect(() => {
    if (!deliveryId) return;
    const interval = setInterval(() => {
      fetchEta();
      fetchTransitions();
    }, 6000);
    return () => clearInterval(interval);
  }, [deliveryId, serverUrl, apiKey]);

  // 2. Establish WebSocket tracking subscription
  useEffect(() => {
    if (!deliveryId) return;

    const wsUrl = serverUrl.replace(/^http/, 'ws') + `/track/${deliveryId}`;
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
      setLogs((prev) => [`[${new Date().toLocaleTimeString()}] Subscribed to telemetry updates`, ...prev]);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.lat && payload.lng) {
          setDriverLoc({ lat: payload.lat, lng: payload.lng });
          // Fetch route geometry and ETA again on driver moves
          fetchRoute();
          fetchEta();
        }
        if (payload.status) {
          setOrder(prev => prev ? { ...prev, status: payload.status } : null);
          fetchTransitions();
        }
        setLogs((prev) => [
          `[${new Date().toLocaleTimeString()}] Broadcast: ${JSON.stringify(payload)}`,
          ...prev.slice(0, 30)
        ]);
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
  }, [deliveryId, serverUrl]);

  const mapCenter: [number, number] = order 
    ? [order.pickup_lat, order.pickup_lng] 
    : [12.9716, 77.5946];

  // Helper to format timestamps for transitions
  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
      return '';
    }
  };

  // Combine standard statuses to construct a complete timeline
  const statuses = [
    { key: 'CREATED', label: 'Created' },
    { key: 'DRIVER_PENDING', label: 'Finding Driver' },
    { key: 'ASSIGNED', label: 'Driver Assigned' },
    { key: 'PICKED_UP', label: 'Picked Up' },
    { key: 'IN_TRANSIT', label: 'In Transit' },
    { key: 'DELIVERED', label: 'Delivered' }
  ];

  return (
    <div className="premium-app font-sans antialiased">
      {/* Top Header */}
      <header className="premium-header">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link to="/fleet" className="btn-premium-secondary p-2 rounded-xl text-gray-500 hover:text-gray-800 transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <span className="font-semibold text-sm text-gray-900">Tracking Order #{deliveryId}</span>
          </div>

          <div className="flex items-center space-x-3">
            <div className="badge-premium badge-gray normal-case py-1.5 px-3 rounded-lg flex items-center font-normal">
              <span className={`w-2 h-2 rounded-full mr-2 ${wsStatus === 'connected' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-gray-500 font-medium">Live Link</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <div className="flex-grow max-w-7xl mx-auto w-full px-6 py-6 flex flex-col space-y-6">
        
        {/* ETA & Distance Card overlay */}
        {etaData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 premium-card">
            <div className="flex items-center space-x-4">
              <div className="p-2.5 bg-indigo-50 text-indigo-650 rounded-lg border border-indigo-100">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <span className="metric-label block mb-0.5">Estimated Arrival</span>
                <span className="metric-value">{Math.ceil(etaData.eta_minutes)} mins</span>
              </div>
            </div>

            <div className="flex items-center space-x-4 border-t sm:border-t-0 sm:border-l border-[#ECEAE5] pt-4 sm:pt-0 sm:pl-6">
              <div className="p-2.5 bg-indigo-50 text-indigo-650 rounded-lg border border-indigo-100">
                <Compass className="w-5 h-5" />
              </div>
              <div>
                <span className="metric-label block mb-0.5">Distance Remaining</span>
                <span className="metric-value">{(etaData.distance_meters / 1000).toFixed(1)} km</span>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-grow items-stretch">
          
          {/* Left Column: Activity Timeline, Driver, Config */}
          <div className="space-y-6 lg:col-span-1 flex flex-col justify-start">
            
            {/* Real-time Activity Feed Timeline */}
            <div className="premium-card flex flex-col">
              <h2 className="text-xs font-semibold text-gray-900 uppercase tracking-wider pb-2 border-b border-[#ECEAE5] mb-4">Activity Timeline</h2>
              
              <div className="pr-1">
                {order ? (
                  <div className="stepper-container pl-1">
                    <div className="stepper-track" />
                    {statuses.map((step, idx) => {
                      const transitionRecord = transitions.find(t => t.to_status === step.key);
                      const isCompleted = !!transitionRecord || order.status === step.key;
                      const isCurrent = order.status === step.key;
                      
                      return (
                        <div key={step.key} className={`stepper-item ${isCurrent ? 'active' : ''} ${isCompleted && !isCurrent ? 'completed' : ''}`}>
                          <div className="stepper-indicator">
                            {isCurrent ? '●' : isCompleted ? '✓' : '○'}
                          </div>
                          
                          <div className="stepper-content">
                            <span className="stepper-title">{step.label}</span>
                            {transitionRecord && (
                              <span className="stepper-desc font-mono">
                                {formatTime(transitionRecord.created_at)}
                              </span>
                            )}
                            {isCurrent && !transitionRecord && (
                              <span className="stepper-desc text-indigo-600 font-semibold animate-pulse">
                                Active Now
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-400 italic">
                    Synchronizing status logs...
                  </div>
                )}
              </div>
            </div>

            {/* Compact Driver Details Card */}
            {order && order.driver_id && (
              <div className="premium-card space-y-3">
                <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5]">
                  <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                  <h2 className="text-[10px] font-bold text-gray-900 uppercase tracking-wider">Courier Information</h2>
                </div>
                <div className="text-xs space-y-1.5 text-gray-750">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Courier ID:</span>
                    <span className="font-mono font-semibold text-gray-900">#{order.driver_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Vehicle Type:</span>
                    <span className="font-semibold text-gray-900">Eco Electric Motorcycle</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Courier Status:</span>
                    <span className="badge-premium badge-emerald">ONLINE</span>
                  </div>
                </div>
              </div>
            )}

            {/* Credentials / Sync Panel */}
            <div className="premium-card">
              <div className="flex justify-between items-center pb-2 border-b border-[#ECEAE5] mb-3">
                <h2 className="text-[10px] font-bold text-gray-900 uppercase tracking-wider">Configuration Reference</h2>
                <button 
                  onClick={syncAllData}
                  className="p-1 hover:bg-[#FAF8F5] rounded border border-transparent hover:border-[#ECEAE5] text-gray-500 hover:text-gray-905 transition-all cursor-pointer animate-none"
                  title="Synchronize data"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="space-y-2 text-xs">
                <div>
                  <label className="premium-label mb-0.5">Gateway Endpoint</label>
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
            </div>

            {error && (
              <div className="badge-premium badge-rose normal-case block w-full text-center py-2.5 rounded-xl text-xs">
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Right Column: Map Container */}
          <div className="lg:col-span-2 h-[500px] lg:h-auto min-h-[500px] relative rounded-xl overflow-hidden border border-[#ECEAE5] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.02)] flex flex-col">
            <div className="flex-grow relative">
              <MapContainer center={mapCenter} zoom={14} className="w-full h-full">
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                  url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                />
                
                {order && (
                  <>
                    <Marker position={[order.pickup_lat, order.pickup_lng]} icon={shopIcon}>
                      <Popup>
                        <div className="font-sans text-xs">
                          <p className="font-bold text-indigo-650">Pickup Merchant</p>
                        </div>
                      </Popup>
                    </Marker>

                    <Marker position={[order.dropoff_lat, order.dropoff_lng]} icon={dropoffIcon}>
                      <Popup>
                        <div className="font-sans text-xs">
                          <p className="font-bold text-rose-600">Delivery Address</p>
                        </div>
                      </Popup>
                    </Marker>
                  </>
                )}

                {driverLoc && (
                  <Marker position={[driverLoc.lat, driverLoc.lng]} icon={driverIcon}>
                    <Popup>
                      <div className="font-sans text-xs">
                        <p className="font-bold text-emerald-600">Courier Active</p>
                        <p className="text-[10px] text-gray-500">Loc: {driverLoc.lat.toFixed(5)}, {driverLoc.lng.toFixed(5)}</p>
                      </div>
                    </Popup>
                  </Marker>
                )}

                {routeGeometry && (
                  <Polyline 
                    positions={routeGeometry} 
                    color="#4f46e5" 
                    weight={3.5}
                    opacity={0.8}
                    dashArray="4, 8"
                  />
                )}

                {!routeGeometry && order && (
                  <Polyline 
                    positions={[
                      [order.pickup_lat, order.pickup_lng],
                      [order.dropoff_lat, order.dropoff_lng]
                    ]} 
                    color="#6366f1" 
                    weight={3}
                    opacity={0.5}
                  />
                )}

                {order && (
                  <MapController order={order} driverLoc={driverLoc} />
                )}
              </MapContainer>
            </div>
            
            {/* Live WebSocket Telemetry Footer */}
            <div className="bg-[#FAF8F5] border-t border-[#ECEAE5] p-3 text-[10px] font-mono flex items-center justify-between text-gray-500">
              <div className="flex items-center space-x-1.5">
                <Wifi className="w-3.5 h-3.5 text-indigo-650" />
                <span>WebSocket telemetry: <span className="font-semibold text-gray-900">{wsStatus}</span></span>
              </div>
              <span className="text-[9px] uppercase tracking-wider font-semibold text-gray-400">Real-time pipeline logs active</span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default Tracking;
