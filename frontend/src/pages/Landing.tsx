import React from 'react';
import { Link } from 'react-router-dom';
import { Navigation, ShieldAlert, Monitor, Radio, Server, Code } from 'lucide-react';

const Landing: React.FC = () => {
  return (
    <div className="premium-app">
      {/* Header */}
      <header className="premium-header">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center shadow-md">
              <Navigation className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-lg tracking-tight text-[#1F2937]">
              Delivery Infrastructure Platform API
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              Cluster online
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-16 flex-grow flex flex-col justify-center items-center">
        <div className="text-center max-w-3xl mb-14">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-[#1F2937] leading-tight">
            Real-Time Logistics{' '}
            <span className="text-red-600">
              Infrastructure
            </span>
          </h1>
          <p className="text-gray-600 text-base md:text-lg">
            A production-ready distributed tracking pipeline using FastAPI, PostgreSQL, WebSockets, and Redis. Monitor operations, track deliveries, and simulate driver movements interactively.
          </p>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 w-full">
          {/* Card 1: Driver Simulator */}
          <div className="premium-card premium-card-interactive flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5">
                <Radio className="w-5 h-5 text-indigo-600" />
              </div>
              <h2 className="text-base font-semibold text-[#1F2937] mb-2">
                Driver Simulator
              </h2>
              <p className="text-gray-500 text-xs leading-relaxed mb-6">
                Accept proposed orders, manually update coordinates, and stream live GPS heartbeats to the Redis GEO index.
              </p>
            </div>
            <Link
              to="/driver-simulator"
              className="btn-premium-primary w-full text-xs"
            >
              Launch Simulator
            </Link>
          </div>

          {/* Card 2: Fleet Dashboard */}
          <div className="premium-card premium-card-interactive flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5">
                <Monitor className="w-5 h-5 text-indigo-600" />
              </div>
              <h2 className="text-base font-semibold text-[#1F2937] mb-2">
                Fleet Operations
              </h2>
              <p className="text-gray-500 text-xs leading-relaxed mb-6">
                Real-time operational dashboard visualizing live couriers, active order details, routing polyline overlays, and cluster vitals.
              </p>
            </div>
            <Link
              to="/fleet"
              className="btn-premium-primary w-full text-xs"
            >
              Open Dashboard
            </Link>
          </div>

          {/* Card 3: Delivery Tracking */}
          <div className="premium-card premium-card-interactive flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5">
                <ShieldAlert className="w-5 h-5 text-indigo-600" />
              </div>
              <h2 className="text-base font-semibold text-[#1F2937] mb-2">
                Customer Tracking
              </h2>
              <p className="text-gray-500 text-xs leading-relaxed mb-6">
                Verify customer live view routing. Connects directly to delivery-specific Redis Pub/Sub channels to draw instant live movements.
              </p>
            </div>
            <div className="flex gap-2">
              <input
                id="deliveryIdInput"
                type="number"
                placeholder="ID"
                className="premium-input text-center font-mono w-16"
              />
              <button
                onClick={() => {
                  const input = document.getElementById('deliveryIdInput') as HTMLInputElement;
                  if (input && input.value) {
                    window.location.href = `/track/${input.value}`;
                  }
                }}
                className="btn-premium-secondary flex-grow text-xs py-2"
              >
                Track
              </button>
            </div>
          </div>

          {/* Card 4: Admin Operations */}
          <div className="premium-card premium-card-interactive flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5">
                <Server className="w-5 h-5 text-indigo-600" />
              </div>
              <h2 className="text-base font-semibold text-[#1F2937] mb-2">
                Admin Observability
              </h2>
              <p className="text-gray-500 text-xs leading-relaxed mb-6">
                Inspect SaaS metering request quotas, Celery broker queue backlog sizes, dead-letter retry metrics, and rate limit telemetry.
              </p>
            </div>
            <Link
              to="/admin"
              className="btn-premium-primary w-full text-xs"
            >
              Open Admin Panel
            </Link>
          </div>

          {/* Card 5: Developer Portal */}
          <div className="premium-card premium-card-interactive flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-5">
                <Code className="w-5 h-5 text-indigo-600" />
              </div>
              <h2 className="text-base font-semibold text-[#1F2937] mb-2">
                Developer Portal
              </h2>
              <p className="text-gray-500 text-xs leading-relaxed mb-6">
                Access your API authentication keys, view monthly request quota remaining capacities, and inspect endpoints specifications.
              </p>
            </div>
            <Link
              to="/developers"
              className="btn-premium-primary w-full text-xs"
            >
              Open Dev Portal
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="premium-footer">
        <div className="max-w-7xl mx-auto px-6 text-center text-xs text-gray-500">
          Delivery Infrastructure Platform API
        </div>
      </footer>
    </div>
  );
};

export default Landing;
