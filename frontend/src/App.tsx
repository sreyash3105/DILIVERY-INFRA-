import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing';
import Tracking from './pages/Tracking';
import Fleet from './pages/Fleet';
import Simulator from './pages/Simulator';
import Admin from './pages/Admin';
import DeveloperPortal from './pages/DeveloperPortal';

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/track/:deliveryId" element={<Tracking />} />
        <Route path="/fleet" element={<Fleet />} />
        <Route path="/driver-simulator" element={<Simulator />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/developers" element={<DeveloperPortal />} />
      </Routes>
    </Router>
  );
};

export default App;
