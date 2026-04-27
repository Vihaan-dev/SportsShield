import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Shield, ShieldAlert, Zap, Globe, UploadCloud, Activity, CheckCircle, Image as ImageIcon, Map as MapIcon, Layers } from 'lucide-react';
import './index.css';

// Single Node Icon (Matches Cluster Theme)
const createSingleThreatIcon = (threat) => {
  const tooltipText = `1 Total Threats\n• 1x ${threat.type === 'deepfake' ? 'AI/Deepfake' : 'Repost/Watermark'}\n`;
  return new L.DivIcon({
    html: `<div class="blurry-cluster" title="${tooltipText}"><span>1</span></div>`,
    className: 'custom-cluster-wrapper',
    iconSize: L.point(40, 40, true),
  });
};

// Mock Data
const MOCK_THREATS = [
  { id: 1, type: 'deepfake', title: 'FaceSwap Detected | IPL Final', location: [19.0760, 72.8777], time: '2 mins ago', severity: 'high', platform: 'Twitter' },
  { id: 2, type: 'repost', title: 'Unauthorized Highlight | UCL', location: [51.5560, -0.2796], time: '14 mins ago', severity: 'medium', platform: 'TikTok' },
  { id: 3, type: 'deepfake', title: 'Generative AI Re-creation | NBA', location: [34.0522, -118.2437], time: '22 mins ago', severity: 'high', platform: 'Instagram' },
  { id: 4, type: 'repost', title: 'Watermarked Asset | FIFA', location: [48.8566, 2.3522], time: '1 hr ago', severity: 'low', platform: 'Reddit' }
];

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isScanning, setIsScanning] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [threats, setThreats] = useState([]);
  const [selectedThreatIds, setSelectedThreatIds] = useState(null);

  const [isAutoScraping, setIsAutoScraping] = useState(false);
  const [registeredAssets, setRegisteredAssets] = useState(0);

  useEffect(() => {
    let interval;
    if (isAutoScraping) {
      interval = setInterval(() => {
        handleSimulateScrape(true);
      }, 4000); // Automatically scrape every 4 seconds
    }
    return () => clearInterval(interval);
  }, [isAutoScraping]);

  const handleSimulateScrape = async (silent = false) => {
    try {
      const response = await fetch("http://localhost:8000/simulate_scrape");
      const data = await response.json();
      
      if (data.verdict === 'suspicious') {
        const newThreat = {
          id: Date.now(),
          type: data.type,
          title: data.title,
          location: data.location,
          time: 'Just now',
          severity: data.severity,
          platform: data.platform
        };
        // Add new threat to top of list
        setThreats(prev => [newThreat, ...prev]);
      } else if (data.error) {
        if (!silent) alert(data.error);
        setIsAutoScraping(false);
      } else {
        if (!silent) alert(`Safe Image Scraped:\n${data.title} - ${data.message || 'Clean'}`);
      }
    } catch (err) {
      if (!silent) alert("Failed to run scan. Ensure backend is running!");
      setIsAutoScraping(false);
    }
  };

  // Drag and Drop Flow
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const simulateScan = async (file) => {
    setIsScanning(true);
    
    // Create FormData to send file
    const formData = new FormData();
    formData.append("file", file);
    formData.append("owner", "Official Broadcaster");

    try {
      const response = await fetch("http://localhost:8000/register", {
        method: "POST",
        body: formData,
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setRegisteredAssets(prev => prev + 1);
        alert(`Success! Asset Registered.\nAsset ID: ${data.asset_id}\nHash: ${data.phash.substring(0, 10)}...`);
      } else {
        alert("Error registering asset: " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Failed to connect to backend. Is python main.py running?");
    } finally {
      setIsScanning(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      Array.from(e.dataTransfer.files).forEach(file => simulateScan(file));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      Array.from(e.target.files).forEach(file => simulateScan(file));
      // Reset input so the same file could be selected again if needed
      e.target.value = null;
    }
  };

  const displayedThreats = selectedThreatIds ? threats.filter(t => selectedThreatIds.includes(t.id)) : threats;

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <div className="sidebar">
        <div className="logo-area">
          <div className="logo-icon">
            <Shield color="white" size={24} />
          </div>
          <div className="logo-text">Sentinel.io</div>
        </div>

        <div className="nav-menu">
          <div className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
            <Activity size={20} />
            <span>Threat Radar</span>
          </div>
          <div className={`nav-item ${activeTab === 'register' ? 'active' : ''}`} onClick={() => setActiveTab('register')}>
            <UploadCloud size={20} />
            <span>Register Asset</span>
          </div>
          <div className="nav-item">
            <Layers size={20} />
            <span>Asset Database</span>
          </div>
          <div className="nav-item">
            <MapIcon size={20} />
            <span>Propagation Map</span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="main-content">
        <div className="header">
          <h1 className="page-title">
            {activeTab === 'dashboard' ? 'Global Threat Radar' : 'Register Official Asset'}
          </h1>
          <div style={{display: 'flex', gap: '16px', alignItems: 'center'}}>
            <span style={{color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', fontWeight: 600}}>
              <CheckCircle size={16} /> System Active
            </span>
            <div style={{width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(45deg, #10b981, #4f80ff)', cursor: 'pointer'}}></div>
          </div>
        </div>

        {activeTab === 'dashboard' ? (
          <div className="dashboard-grid">
            {/* Top Stats */}
            <div className="stats-container" style={{ position: 'relative' }}>
              
              <button 
                onClick={() => isAutoScraping ? setIsAutoScraping(false) : setIsAutoScraping(true)}
                style={{ position: 'absolute', right: 0, top: '-55px', background: isAutoScraping ? 'var(--danger)' : 'var(--warning)', color: isAutoScraping ? 'white' : '#000', border: 'none', padding: '10px 20px', borderRadius: '8px', fontWeight: 700, cursor: 'pointer', display: 'flex', gap: '8px', alignItems: 'center', transition: 'all 0.3s' }}
              >
                <Zap size={18} /> {isAutoScraping ? "Pause Live Scrape" : "Start Live Scrape"}
              </button>
              
              <div className="glass-panel stat-card">
                <div className="stat-icon blue">
                  <ImageIcon size={24} />
                </div>
                <div className="stat-info">
                  <h4>Protected Assets</h4>
                  <div className="value">{registeredAssets < 10 ? `0${registeredAssets}` : registeredAssets}</div>
                </div>
              </div>
              <div className="glass-panel stat-card">
                <div className="stat-icon red">
                  <ShieldAlert size={24} />
                </div>
                <div className="stat-info">
                  <h4>Active Threats</h4>
                  <div className="value">{threats.length < 10 ? `0${threats.length}` : threats.length}</div>
                </div>
              </div>
              <div className="glass-panel stat-card">
                <div className="stat-icon green">
                  <Zap size={24} />
                </div>
                <div className="stat-info">
                  <h4>Analyzed Today</h4>
                  <div className="value">{threats.length < 10 ? `0${threats.length}` : threats.length}</div>
                </div>
              </div>
            </div>

            {/* Geo Map */}
            <div className="glass-panel" style={{ padding: '4px' }}>
              <div className="map-container">
                <MapContainer center={[20, 0]} zoom={2} scrollWheelZoom={false} className="map-wrapper">
                  {/* Dark Mode CartoDB Map Layer */}
                  <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                  />
                  
                  <MarkerClusterGroup 
                    chunkedLoading
                    zoomToBoundsOnClick={false}
                    spiderfyOnMaxZoom={false}
                    iconCreateFunction={(cluster) => {
                      const count = cluster.getChildCount();
                      const markers = cluster.getAllChildMarkers();
                      
                      const types = {};
                      markers.forEach(marker => {
                        const type = marker.options.threatType || 'unknown';
                        types[type] = (types[type] || 0) + 1;
                      });
                      
                      let tooltipText = `${count} Total Threats\n`;
                      Object.entries(types).forEach(([t, c]) => {
                        tooltipText += `• ${c}x ${t === 'deepfake' ? 'AI/Deepfake' : 'Repost/Watermark'}\n`;
                      });

                      return new L.divIcon({
                        html: `<div class="blurry-cluster" title="${tooltipText}"><span>${count}</span></div>`,
                        className: 'custom-cluster-wrapper',
                        iconSize: L.point(40, 40, true),
                      });
                    }}
                    onClick={(e) => {
                      if (e.layer && e.layer.getAllChildMarkers) {
                        const childIds = e.layer.getAllChildMarkers().map(m => m.options.threatId);
                        setSelectedThreatIds(childIds);
                      }
                    }}
                  >
                    {threats.map(threat => (
                      <Marker 
                        key={threat.id} 
                        position={threat.location} 
                        icon={createSingleThreatIcon(threat)}
                        threatType={threat.type}
                        threatId={threat.id}
                        eventHandlers={{
                          click: (e) => {
                            setSelectedThreatIds([threat.id]);
                            e.originalEvent.stopPropagation();
                          }
                        }}
                      >
                        <Popup className="dark-popup">
                          <strong>{threat.title}</strong><br/>
                          Severity: {threat.severity}<br/>
                          Platform: {threat.platform}
                        </Popup>
                      </Marker>
                    ))}
                  </MarkerClusterGroup>
                </MapContainer>
              </div>
            </div>

            {/* Live Feed */}
            <div className="glass-panel" style={{display: 'flex', flexDirection: 'column'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                <h3 style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                  <Globe size={20} color="var(--primary)"/> {selectedThreatIds ? "Filtered Threats" : "Live Detection Feed"}
                </h3>
                {selectedThreatIds && (
                  <button 
                    onClick={() => setSelectedThreatIds(null)} 
                    style={{background: 'var(--bg-panel)', border: '1px solid var(--border)', color: 'var(--text-main)', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600}}
                  >
                    Reset View
                  </button>
                )}
              </div>
              <div className="threat-feed">
                {displayedThreats.length === 0 ? (
                  <div style={{color: 'var(--text-muted)', textAlign: 'center', marginTop: '20px'}}>No threats match this filter.</div>
                ) : (
                  displayedThreats.map(threat => (
                    <div key={threat.id} className={`threat-item ${threat.severity}`}>
                      <div className="threat-header">
                        <span className="threat-title">{threat.title}</span>
                        <span className="threat-time">{threat.time}</span>
                      </div>
                      <div className="threat-meta">
                        <span className={`threat-type ${threat.type}`}>
                          {threat.type === 'deepfake' ? 'Type 3 (AI)' : 'Type 1'}
                        </span>
                        <span>•</span>
                        <span>{threat.platform}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Registration View */
          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <div 
              className={`upload-zone ${dragActive ? 'active' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <UploadCloud size={64} className="upload-icon" />
              <h2 className="upload-title">Register Media Asset</h2>
              <p className="upload-subtitle">Drag and drop your official images/videos here to index them via FAISS and CLIP.</p>
              
              <input 
                type="file" 
                id="file-upload" 
                style={{display: 'none'}} 
                onChange={handleFileChange}
                accept="image/jpeg, image/png, image/webp"
                multiple
              />
              <label htmlFor="file-upload" className="upload-btn" style={{display: 'inline-block'}}>
                {isScanning ? 'Extracting Signatures...' : 'Browse Files'}
              </label>

              {isScanning && <div className="scan-overlay"></div>}
            </div>
            
            <div style={{marginTop: '40px', display: 'flex', gap: '32px', color: 'var(--text-muted)'}}>
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                <CheckCircle size={18} color="var(--success)"/> Creates Perceptual Hash
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                <CheckCircle size={18} color="var(--success)"/> Extracts Semantic Embedding
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                <CheckCircle size={18} color="var(--success)"/> Mints Provenance Record
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
