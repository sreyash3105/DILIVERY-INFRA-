import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import { ArrowLeft, Play, Send } from 'lucide-react';
import { driverIcon } from '../utils/leafletIcons';

const Simulator: React.FC = () => {
  // App Configs
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem('dep_server_url') || import.meta.env.VITE_API_URL || 'http://localhost:8000');
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('dep_api_key') || 'test_api_key_123');

  // Simulator State
  const [driverId, setDriverId] = useState<number | ''>('');
  const [driver, setDriver] = useState<any>(null);
  const [markerPos, setMarkerPos] = useState<{ lat: number; lng: number }>({ lat: 12.9716, lng: 77.5946 });
  const [newDriverName, setNewDriverName] = useState('');
  const [newDriverPhone, setNewDriverPhone] = useState('');
  // UI Status
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [activeOffer, setActiveOffer] = useState<any>(null);
  const [manualOrderId, setManualOrderId] = useState<number | ''>('');

  React.useEffect(() => {
    if (!driver) {
      setActiveOffer(null);
      return;
    }

    const checkOffers = async () => {
      try {
        const res = await fetch(`${serverUrl}/drivers/${driver.id}/offers`);
        if (res.ok) {
          const offer = await res.json();
          if (offer && offer.id) {
            setActiveOffer(offer);
            setManualOrderId(offer.id);
          } else {
            setActiveOffer(null);
          }
        }
      } catch (err) {}
    };

    checkOffers();
    const interval = setInterval(checkOffers, 4000);
    return () => clearInterval(interval);
  }, [driver, serverUrl]);

  // Hook to handle map click events to place driver target marker
  const MapEvents = () => {
    useMapEvents({
      click(e: any) {
        setMarkerPos({ lat: e.latlng.lat, lng: e.latlng.lng });
        setLog((prev) => [
          `[Simulator] Marker moved to: ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}. Click "Send GPS Ping" to broadcast.`,
          ...prev
        ]);
      }
    });
    return null;
  };

  // 1. Register a new driver
  const handleRegisterDriver = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDriverName || !newDriverPhone) return;

    try {
      setError(null);
      const res = await fetch(`${serverUrl}/drivers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newDriverName, phone: newDriverPhone })
      });
      if (!res.ok) throw new Error('Registration failed');
      const data = await res.json();
      setDriver(data);
      setDriverId(data.id);
      if (data.current_lat && data.current_lng) {
        setMarkerPos({ lat: data.current_lat, lng: data.current_lng });
      }
      setLog((prev) => [`[System] Registered Driver "${data.name}" with ID: ${data.id}`, ...prev]);
      setNewDriverName('');
      setNewDriverPhone('');
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    }
  };

  // 2. Load Driver
  const handleLoadDriver = async () => {
    if (!driverId) return;
    try {
      setError(null);
      const res = await fetch(`${serverUrl}/drivers/${driverId}`);
      if (!res.ok) throw new Error('Driver not found');
      const data = await res.json();
      setDriver(data);
      if (data.current_lat && data.current_lng) {
        setMarkerPos({ lat: data.current_lat, lng: data.current_lng });
      }
      setLog((prev) => [`[System] Loaded Driver Profile ID: ${data.id} (${data.name})`, ...prev]);
    } catch (err: any) {
      setError(err.message || 'Driver profile load failed');
    }
  };

  // 3. Send manual location heartbeat
  const handleSendLocation = async () => {
    if (!driver) return;
    try {
      setError(null);
      const res = await fetch(`${serverUrl}/drivers/${driver.id}/location`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: markerPos.lat, longitude: markerPos.lng })
      });
      if (!res.ok) throw new Error('Failed to update location');
      
      setLog((prev) => [
        `[Broadcast] Posted GPS telemetry: [${markerPos.lat.toFixed(5)}, ${markerPos.lng.toFixed(5)}] for Driver #${driver.id}`,
        ...prev
      ]);
    } catch (err: any) {
      setError(err.message || 'Failed to update location');
    }
  };

  // 4. Toggle Availability
  const handleToggleAvailability = async (val: boolean) => {
    if (!driver) return;
    try {
      setError(null);
      const res = await fetch(`${serverUrl}/drivers/${driver.id}/availability`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_available: val })
      });
      if (!res.ok) throw new Error('Failed to update availability status');
      
      setDriver((prev: any) => ({ ...prev, is_available: val }));
      setLog((prev) => [`[System] Availability toggled: ${val ? 'AVAILABLE (GEO Search Active)' : 'OFFLINE'}`, ...prev]);
    } catch (err: any) {
      setError(err.message || 'Availability toggle failed');
    }
  };

  // 5. Manual Order Status Actions
  const handleManualStatusChange = async (status: string) => {
    if (!manualOrderId) return;
    try {
      setError(null);
      const res = await fetch(`${serverUrl}/deliveries/${manualOrderId}/status`, {
        method: 'PATCH',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-Key': apiKey 
        },
        body: JSON.stringify({ 
          status,
          driver_id: driver?.id
        })
      });
      if (!res.ok) throw new Error(`Transition to ${status} failed`);
      const data = await res.json();
      setLog((prev) => [`[Order #${data.id}] Status transitioned to: ${data.status}`, ...prev]);
      
      if (status === 'DELIVERED') {
        setManualOrderId('');
      }
      if (driver) {
        refreshDriverProfile(driver.id);
      }
    } catch (err: any) {
      setError(err.message || 'Transition update failed');
    }
  };

  const refreshDriverProfile = async (id: number) => {
    try {
      const res = await fetch(`${serverUrl}/drivers/${id}`);
      if (res.ok) {
        const data = await res.json();
        setDriver(data);
      }
    } catch (err) {}
  };

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
              <Play className="w-4 h-4 text-indigo-650" />
              <span className="font-semibold text-sm text-gray-900">Driver GPS & Dispatch Simulator</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-grow max-w-7xl mx-auto w-full px-6 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Control Panel */}
        <div className="lg:col-span-1 space-y-6">
          {/* Server Config */}
          <div className="premium-card space-y-3">
            <h2 className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Connection Settings</h2>
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
              <label className="premium-label mb-0.5">Tenant Auth Token</label>
              <input 
                type="password" 
                value={apiKey} 
                onChange={(e) => setApiKey(e.target.value)} 
                className="premium-input font-mono"
              />
            </div>
          </div>

          {/* Load / Create Driver */}
          <div className="premium-card space-y-4">
            <h2 className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Driver Access Control</h2>
            
            {/* Load existing */}
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="ID"
                value={driverId}
                onChange={(e) => setDriverId(e.target.value ? Number(e.target.value) : '')}
                className="premium-input text-center font-mono w-16"
              />
              <button
                onClick={handleLoadDriver}
                className="btn-premium-secondary flex-grow text-xs py-1.5 font-semibold"
              >
                Load Driver Profile
              </button>
            </div>

            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-[#ECEAE5]"></div>
              <span className="flex-shrink mx-3 text-[9px] text-gray-400 font-bold uppercase tracking-wider">or Register New</span>
              <div className="flex-grow border-t border-[#ECEAE5]"></div>
            </div>

            {/* Create new */}
            <form onSubmit={handleRegisterDriver} className="space-y-2.5">
              <input
                type="text"
                placeholder="Driver Name"
                value={newDriverName}
                onChange={(e) => setNewDriverName(e.target.value)}
                className="premium-input"
              />
              <input
                type="text"
                placeholder="Driver Phone Number"
                value={newDriverPhone}
                onChange={(e) => setNewDriverPhone(e.target.value)}
                className="premium-input font-mono"
              />
              <button
                type="submit"
                className="btn-premium-primary w-full py-2 font-semibold text-xs"
              >
                Register Driver
              </button>
            </form>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="badge-premium badge-rose normal-case block w-full text-center py-2.5 rounded-xl text-xs font-medium">
              {error}
            </div>
          )}

          {/* Active Driver Actions */}
          {driver && (
            <div className="premium-card space-y-4">
              <div className="flex justify-between items-center pb-2.5 border-b border-[#ECEAE5]">
                <div>
                  <h3 className="font-semibold text-gray-900 text-xs">{driver.name}</h3>
                  <p className="text-[9px] text-gray-500 font-semibold font-mono">Driver ID: #{driver.id}</p>
                </div>
                <div className={`badge-premium ${
                  driver.status === 'ONLINE' ? 'badge-emerald' : 'badge-gray'
                }`}>
                  {driver.status}
                </div>
              </div>

              {/* Active Offer Alert Banner */}
              {activeOffer && (
                <div className="p-3.5 bg-indigo-50 border border-indigo-200 rounded-lg space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-[9px] font-bold text-indigo-750 uppercase tracking-wider">Order Offer Assigned!</span>
                    <span className="text-[9px] font-mono bg-indigo-150 text-indigo-850 px-1.5 py-0.5 rounded font-bold">#{activeOffer.id}</span>
                  </div>
                  <p className="text-[9px] text-gray-550 leading-normal font-mono">
                    Pickup: {activeOffer.pickup_lat.toFixed(4)}, {activeOffer.pickup_lng.toFixed(4)}<br />
                    Dropoff: {activeOffer.dropoff_lat.toFixed(4)}, {activeOffer.dropoff_lng.toFixed(4)}
                  </p>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button
                      onClick={async () => {
                        try {
                          setError(null);
                           const res = await fetch(`${serverUrl}/deliveries/${activeOffer.id}/accept`, {
                            method: 'POST',
                            headers: { 
                              'Content-Type': 'application/json',
                              'X-API-Key': apiKey 
                            }
                          });
                          if (!res.ok) throw new Error('Accept offer failed');
                          const data = await res.json();
                          setLog((prev) => [`[Order #${data.id}] Offer ACCEPTED by driver`, ...prev]);
                          setActiveOffer(null);
                          refreshDriverProfile(driver.id);
                        } catch (err: any) {
                          setError(err.message || 'Accept failed');
                        }
                      }}
                      className="btn-premium-primary py-1.5 font-semibold text-xs"
                    >
                      Accept
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          setError(null);
                          const res = await fetch(`${serverUrl}/deliveries/${activeOffer.id}/reject`, {
                            method: 'POST',
                            headers: { 
                              'Content-Type': 'application/json',
                              'X-API-Key': apiKey 
                            }
                          });
                          if (!res.ok) throw new Error('Reject offer failed');
                          const data = await res.json();
                          setLog((prev) => [`[Order #${data.id}] Offer REJECTED by driver`, ...prev]);
                          setActiveOffer(null);
                          refreshDriverProfile(driver.id);
                        } catch (err: any) {
                          setError(err.message || 'Reject failed');
                        }
                      }}
                      className="btn-premium-danger py-1.5 font-semibold text-xs"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              )}

              {/* Toggles */}
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500 font-medium">Availability state (GEO Index):</span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={driver.is_available} 
                    onChange={(e) => handleToggleAvailability(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-8 h-4 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-indigo-600"></div>
                </label>
              </div>

              {/* Coordinates info */}
              <div className="bg-[#FAF8F5] p-3.5 border border-[#ECEAE5] rounded-xl space-y-2">
                <span className="text-[9px] text-gray-500 uppercase font-bold tracking-wider">Mock GPS Pin Target</span>
                <div className="flex justify-between items-center text-[10px] font-mono text-gray-500">
                  <span>Lat: {markerPos.lat.toFixed(6)}</span>
                  <span>Lng: {markerPos.lng.toFixed(6)}</span>
                </div>
                <button
                  onClick={handleSendLocation}
                  className="btn-premium-primary w-full mt-1.5 flex items-center justify-center space-x-2 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Send GPS Ping Update</span>
                </button>
              </div>

              {/* Manual Order Controls */}
              <div className="border-t border-[#ECEAE5] pt-4 space-y-3">
                <h3 className="text-[10px] font-bold uppercase tracking-wider text-gray-500">Dispatch Pipeline Overrides</h3>
                <div className="flex gap-2">
                  <input
                    type="number"
                    placeholder="Order ID"
                    value={manualOrderId}
                    onChange={(e) => setManualOrderId(e.target.value ? Number(e.target.value) : '')}
                    className="premium-input text-center font-mono w-16"
                  />
                  <button
                    onClick={() => handleManualStatusChange('ASSIGNED')}
                    className="btn-premium-secondary py-1.5 px-3 text-[10px] font-semibold flex-grow cursor-pointer"
                  >
                    Force Assign
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => handleManualStatusChange('PICKED_UP')}
                    className="btn-premium-secondary py-1.5 text-[10px] font-semibold cursor-pointer"
                  >
                    Pick Up
                  </button>
                  <button
                    onClick={() => handleManualStatusChange('IN_TRANSIT')}
                    className="btn-premium-secondary py-1.5 text-[10px] font-semibold cursor-pointer"
                  >
                    In Transit
                  </button>
                  <button
                    onClick={() => handleManualStatusChange('DELIVERED')}
                    className="btn-premium-primary py-1.5 text-[10px] font-semibold cursor-pointer"
                  >
                    Deliver
                  </button>
                </div>
              </div>

            </div>
          )}
        </div>

        {/* Right Side: Map & Logger */}
        <div className="lg:col-span-2 flex flex-col space-y-6">
          <div className="h-[480px] relative rounded-xl overflow-hidden border border-[#ECEAE5] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
            <div className="absolute top-3 left-12 z-20 bg-white/95 border border-[#ECEAE5] px-3 py-1.5 rounded-lg text-[9px] font-semibold uppercase tracking-wide text-gray-500 shadow-md">
              🖱️ Click map to place the driver target destination pin
            </div>
            
            <MapContainer center={[12.9716, 77.5946]} zoom={13} className="w-full h-full">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
              />
              <MapEvents />
              <Marker position={[markerPos.lat, markerPos.lng]} icon={driverIcon} />
            </MapContainer>
          </div>

          {/* Simulator logs */}
          <div className="premium-card flex flex-col h-[230px]">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 pb-2 border-b border-[#ECEAE5] mb-3">Simulator Console Output</h2>
            <div className="flex-grow overflow-y-auto terminal-panel p-3 space-y-2">
              {log.length === 0 ? (
                <div className="text-gray-500 text-center py-12 italic font-mono text-[10px]">Waiting for simulation events...</div>
              ) : (
                log.map((entry, index) => {
                  let logColor = 'text-gray-400';
                  if (entry.includes('[Broadcast]')) {
                    logColor = 'text-emerald-400';
                  } else if (entry.includes('[System]')) {
                    logColor = 'text-indigo-400 font-semibold';
                  } else if (entry.includes('transitioned')) {
                    logColor = 'text-amber-400';
                  }
                  return (
                    <div key={index} className="terminal-line">
                      <span className="terminal-timestamp">[{new Date().toLocaleTimeString()}]</span>
                      <span className={logColor}>{entry.replace(/^\[.*?\]\s*/, '')}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Simulator;
