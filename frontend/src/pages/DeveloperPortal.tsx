import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Code, Key, BookOpen, Activity, Terminal, Copy, Check, Eye, EyeOff, RefreshCw } from 'lucide-react';

const DeveloperPortal: React.FC = () => {
  const [serverUrl, setServerUrl] = useState(() => localStorage.getItem('dep_server_url') || import.meta.env.VITE_API_URL || 'http://localhost:8000');
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('dep_api_key') || 'test_api_key_123');

  const [usageData, setUsageData] = useState<any>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const fetchUsage = async () => {
    try {
      const res = await fetch(`${serverUrl}/analytics/tenant`, {
        headers: { 'X-API-Key': apiKey }
      });
      if (res.ok) {
        const data = await res.json();
        setUsageData(data);
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchUsage();
    const interval = setInterval(fetchUsage, 6000);
    return () => clearInterval(interval);
  }, [serverUrl, apiKey]);

  // Save configs
  useEffect(() => {
    localStorage.setItem('dep_server_url', serverUrl);
    localStorage.setItem('dep_api_key', apiKey);
  }, [serverUrl, apiKey]);

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const handleRotateKey = async () => {
    if (!window.confirm("Are you sure you want to rotate your API key? Your old key will stop working immediately.")) {
      return;
    }
    setRotating(true);
    try {
      const res = await fetch(`${serverUrl}/analytics/tenant/rotate-key`, {
        method: 'POST',
        headers: { 'X-API-Key': apiKey }
      });
      if (res.ok) {
        const data = await res.json();
        setApiKey(data.api_key);
        alert("API key successfully rotated!");
      } else {
        const err = await res.json();
        alert(`Failed to rotate API key: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert("Network error: Failed to rotate API key.");
    } finally {
      setRotating(false);
    }
  };

  const curlExample = `curl -X POST "${serverUrl}/deliveries" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${apiKey}" \\
  -d '{
    "pickup_lat": 12.9716,
    "pickup_lng": 77.5946,
    "dropoff_lat": 12.9816,
    "dropoff_lng": 77.6046
  }'`;

  return (
    <div className="premium-app font-sans">
      {/* Header */}
      <header className="premium-header">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link to="/" className="btn-premium-secondary p-2 rounded-xl text-gray-500 hover:text-gray-800 transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex items-center space-x-2">
              <Code className="w-5 h-5 text-indigo-650" />
              <span className="font-semibold text-base text-gray-905">Developer Portal & API Docs</span>
            </div>
          </div>
        </div>
      </header>

      {/* Content Layout */}
      <div className="flex-grow max-w-7xl mx-auto w-full px-6 py-8 grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left Config Panel */}
        <div className="lg:col-span-1 space-y-6">
          <div className="premium-card space-y-4">
            <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5]">
              <Key className="w-4 h-4 text-indigo-650" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">API Settings</h2>
            </div>
            
            <div className="space-y-3">
              <div>
                <label className="premium-label block mb-1.5">Gateway Endpoint</label>
                <input 
                  type="text" 
                  value={serverUrl} 
                  onChange={(e) => setServerUrl(e.target.value)} 
                  className="premium-input font-mono"
                />
              </div>
              <div>
                <label className="premium-label block mb-1.5">X-API-Key</label>
                <div className="relative flex items-center">
                  <input 
                    type={showKey ? "text" : "password"}
                    value={apiKey} 
                    onChange={(e) => setApiKey(e.target.value)} 
                    className="premium-input font-mono tracking-wide pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 text-gray-400 hover:text-gray-600 focus:outline-none cursor-pointer transition-colors"
                  >
                    {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
              <div className="pt-2">
                <button
                  onClick={handleRotateKey}
                  disabled={rotating}
                  className="btn-premium-secondary w-full py-2.5 font-semibold text-xs flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${rotating ? 'animate-spin text-amber-600' : ''}`} />
                  <span>{rotating ? 'Rotating Key...' : 'Rotate API Credentials'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Usage Metering stats */}
          <div className="premium-card space-y-4">
            <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5]">
              <Activity className="w-4 h-4 text-indigo-650" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Quota Usage</h2>
            </div>

            {usageData ? (
              <div className="space-y-4 text-xs">
                <div>
                  <span className="text-gray-500 block font-medium">Billing Tier Plan</span>
                  <span className="font-semibold text-indigo-650 text-sm">{usageData.plan_name}</span>
                </div>
                <div>
                  <span className="text-gray-500 block font-medium">Rate Limit Capacity</span>
                  <span className="font-mono text-gray-900">{usageData.rate_limit_per_minute} req/min</span>
                </div>
                <div>
                  <span className="text-gray-500 block font-medium">Monthly API Requests</span>
                  <div className="flex justify-between font-bold text-gray-900 mt-0.5">
                    <span>{usageData.monthly_usage}</span>
                    <span className="text-gray-500">/ {usageData.monthly_quota}</span>
                  </div>
                </div>
                <div className="w-full bg-[#FAF8F5] rounded-full h-2 border border-[#ECEAE5] overflow-hidden">
                  <div 
                    className="h-full bg-indigo-600 rounded-full transition-all"
                    style={{ width: `${Math.min(100, (usageData.monthly_usage / usageData.monthly_quota) * 100)}%` }}
                  ></div>
                </div>
                <div>
                  <span className="text-gray-500 block font-medium">Quota Remaining</span>
                  <span className="font-semibold text-emerald-600">
                    {Math.max(0, usageData.monthly_quota - usageData.monthly_usage)} requests
                  </span>
                </div>
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                <span className="text-gray-400 italic font-normal block leading-relaxed">Enter a valid tenant X-API-Key to view live billing usage statistics.</span>
                <div className="pt-2 border-t border-[#ECEAE5] space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Default Quota:</span>
                    <span className="font-bold">10,000 / mo</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Rate Limit:</span>
                    <span className="font-bold">60 req/min</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Section: Quick Start & Docs References */}
        <div className="lg:col-span-3 space-y-6">
          
          {/* Quick Start Card */}
          <div className="premium-card space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-indigo-650" />
                <h2 className="text-sm font-semibold text-gray-900">Quick Start (Curl Example)</h2>
              </div>
              <button 
                onClick={() => handleCopy(curlExample, 'curl')}
                className="btn-premium-secondary text-xs px-2.5 py-1 flex items-center space-x-1.5 cursor-pointer"
              >
                {copiedText === 'curl' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedText === 'curl' ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>
            
            <p className="text-xs text-gray-500 leading-relaxed font-normal">
              Use this command to create and auto-dispatch a delivery instantly from any terminal. It sends the request to the API Gateway load balancer, which resolves the tenant credentials and initializes driver assignment.
            </p>
            
            <pre className="terminal-panel p-3.5 overflow-x-auto whitespace-pre leading-relaxed">
              {curlExample}
            </pre>
          </div>

          {/* Reference Docs List */}
          <div className="premium-card space-y-5">
            <div className="flex items-center space-x-2 pb-2 border-b border-[#ECEAE5]">
              <BookOpen className="w-4 h-4 text-indigo-650" />
              <h2 className="text-sm font-semibold text-gray-900">Endpoint API Specifications</h2>
            </div>

            {/* Spec 1: Create Delivery */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="badge-premium badge-emerald font-bold">POST</span>
                  <span className="font-mono text-xs font-semibold text-gray-900">/deliveries</span>
                </div>
                <span className="text-[10px] text-gray-500 font-medium">Create New Dispatch Order</span>
              </div>
              <p className="text-xs text-gray-500 font-normal">
                Initializes a delivery item by providing pickup and dropoff geolocation decimal degree coordinates.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider block">JSON Request Body</span>
                  <pre className="terminal-panel p-2.5 text-[9px]">
{`{
  "pickup_lat": 12.9716,
  "pickup_lng": 77.5946,
  "dropoff_lat": 12.9816,
  "dropoff_lng": 77.6046
}`}
                  </pre>
                </div>
                <div className="space-y-1">
                  <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider block">JSON Response Payload</span>
                  <pre className="terminal-panel p-2.5 text-[9px]">
{`{
  "id": 102,
  "status": "CREATED",
  "pickup_lat": 12.9716,
  "pickup_lng": 77.5946,
  "driver_id": null
}`}
                  </pre>
                </div>
              </div>
            </div>

            {/* Spec 2: Track Delivery */}
            <div className="space-y-2 pt-4 border-t border-[#ECEAE5]">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="badge-premium badge-indigo font-bold">GET</span>
                  <span className="font-mono text-xs font-semibold text-gray-900">/deliveries/{"{id}"}</span>
                </div>
                <span className="text-[10px] text-gray-500 font-medium">Retrieve Order Status</span>
              </div>
              <p className="text-xs text-gray-500 font-normal">
                Fetches active variables and assignment conditions for a single specific order entry.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider block">Path Variables</span>
                  <pre className="terminal-panel p-2.5 text-[9px] h-[74px] flex items-center pl-4">
{`delivery_id: integer (ID of the order)`}
                  </pre>
                </div>
                <div className="space-y-1">
                  <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider block">JSON Response Payload</span>
                  <pre className="terminal-panel p-2.5 text-[9px]">
{`{
  "id": 102,
  "status": "IN_TRANSIT",
  "driver_id": 8,
  "dropoff_lat": 12.9816,
  "dropoff_lng": 77.6046
}`}
                  </pre>
                </div>
              </div>
            </div>

            {/* Spec 3: Assign Driver */}
            <div className="space-y-2 pt-4 border-t border-[#ECEAE5]">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="badge-premium badge-emerald font-bold">POST</span>
                  <span className="font-mono text-xs font-semibold text-gray-900">/deliveries/assign-driver</span>
                </div>
                <span className="text-[10px] text-gray-500 font-medium">Trigger Auto-Assignment</span>
              </div>
              <p className="text-xs text-gray-500 font-normal">
                Fires the matching state engine, locating the closest online available driver inside Redis using a geo radius lookup.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider block">JSON Request Body</span>
                  <pre className="terminal-panel p-2.5 text-[9px]">
{`{
  "order_id": 102
}`}
                  </pre>
                </div>
                <div className="space-y-1">
                  <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider block">JSON Response Payload</span>
                  <pre className="terminal-panel p-2.5 text-[9px]">
{`{
  "id": 102,
  "status": "DRIVER_PENDING",
  "driver_id": 8,
  "pickup_lat": 12.9716
}`}
                  </pre>
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
};

export default DeveloperPortal;
