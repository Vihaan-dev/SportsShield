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
  const [mediaType, setMediaType] = useState('image'); // 'image' or 'video'
  
  // New states for demo
  const [sampleImages, setSampleImages] = useState([]);
  const [sampleVideos, setSampleVideos] = useState([]);
  const [selectedViolation, setSelectedViolation] = useState(null);
  const [showComparisonModal, setShowComparisonModal] = useState(false);

  useEffect(() => {
    let interval;
    if (isAutoScraping) {
      interval = setInterval(() => {
        handleSimulateScrape(true);
      }, 4000); // Automatically scrape every 4 seconds
    }
    return () => clearInterval(interval);
  }, [isAutoScraping]);
  
  // Load sample images and videos on mount
  useEffect(() => {
    fetch("http://localhost:8000/get_sample_images")
      .then(res => res.json())
      .then(data => setSampleImages(data.samples))
      .catch(err => console.error("Failed to load samples:", err));
    
    fetch("http://localhost:8000/get_sample_videos")
      .then(res => res.json())
      .then(data => setSampleVideos(data.samples))
      .catch(err => console.error("Failed to load video samples:", err));
  }, []);

  const handleSimulateScrape = async (silent = false) => {
    try {
      // Use appropriate endpoint based on media type
      const endpoint = mediaType === 'video' ? "/simulate_video_scrape" : "/simulate_scrape";
      const response = await fetch(`http://localhost:8000${endpoint}`);
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
    
    // Detect if file is video or image
    const isVideo = file.type.startsWith('video/');
    
    // Create FormData to send file
    const formData = new FormData();
    formData.append("file", file);
    formData.append("owner", "Official Broadcaster");

    try {
      // Use appropriate endpoint based on file type
      const endpoint = isVideo ? "/register_video" : "/register";
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: "POST",
        body: formData,
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setRegisteredAssets(prev => prev + 1);
        
        // Display appropriate success message based on media type
        if (isVideo) {
          alert(`Success! Video Registered.\nAsset ID: ${data.asset_id}\nDuration: ${data.duration.toFixed(2)}s\nFPS: ${data.fps}\nResolution: ${data.resolution}`);
        } else {
          alert(`Success! Asset Registered.\nAsset ID: ${data.asset_id}\nHash: ${data.phash.substring(0, 10)}...`);
        }
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
      Array.from(e.target.files).forEach(file => {
        if (mediaType === 'image') {
          analyzeUploadedImage(file);
        } else {
          simulateScan(file);
        }
      });
      e.target.value = null;
    }
  };
  
  const analyzeUploadedImage = async (file) => {
    setIsScanning(true);
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const response = await fetch("http://localhost:8000/analyze_upload", {
        method: "POST",
        body: formData,
      });
      
      const data = await response.json();
      
      if (data.status === "found") {
        // Clear existing threats and show new violations
        setThreats([]);
        data.violations.forEach((violation, index) => {
          setTimeout(() => {
            const newThreat = {
              id: Date.now() + index,
              type: violation.color,
              title: `${violation.type} | ${violation.city}`,
              location: violation.location,
              time: violation.time,
              severity: violation.severity,
              platform: violation.platform,
              originalImage: `http://localhost:8000${violation.original_image}`,
              foundImage: `http://localhost:8000${violation.found_image}`
            };
            setThreats(prev => [...prev, newThreat]);
          }, index * 500); // Stagger appearance
        });
        
        alert(`Analysis Complete!\n\nFound ${data.total_violations} unauthorized copies across the internet.`);
      } else {
        alert(`Analysis Complete\n\n${data.message}\n\nScanned: ${data.scanned_platforms.join(", ")}\nTime: ${data.scan_time}`);
      }
    } catch (err) {
      alert("Failed to analyze image. Ensure backend is running!");
    } finally {
      setIsScanning(false);
    }
  };
  
  const analyzeSample = async (sampleId) => {
    setIsScanning(true);
    setThreats([]);
    
    const formData = new FormData();
    formData.append("sample_id", sampleId);
    
    try {
      const response = await fetch("http://localhost:8000/analyze_sample", {
        method: "POST",
        body: formData,
      });
      
      const data = await response.json();
      
      if (data.status === "found") {
        // Show violations on map with staggered animation
        data.violations.forEach((violation, index) => {
          setTimeout(() => {
            const newThreat = {
              id: Date.now() + index,
              type: violation.color,
              title: `${violation.type} | ${violation.city}`,
              location: violation.location,
              time: violation.time,
              severity: violation.severity,
              platform: violation.platform,
              originalImage: `http://localhost:8000${violation.original_image}`,
              foundImage: `http://localhost:8000${violation.found_image}`
            };
            setThreats(prev => [...prev, newThreat]);
          }, index * 500);
        });
        
        // Switch to dashboard to show results
        setTimeout(() => {
          setActiveTab('dashboard');
          alert(`Analysis Complete!\n\nFound ${data.total_violations} unauthorized copies across the internet.`);
        }, 100);
      }
    } catch (err) {
      alert("Failed to analyze sample. Ensure backend is running!");
    } finally {
      setIsScanning(false);
    }
  };
  
  const analyzeSampleVideo = async (sampleId) => {
    setIsScanning(true);
    setThreats([]);
    const formData = new FormData();
    formData.append("sample_id", sampleId);
    try {
      const response = await fetch("http://localhost:8000/analyze_sample_video", {method: "POST", body: formData});
      const data = await response.json();
      if (data.status === "found") {
        data.violations.forEach((violation, index) => {
          setTimeout(() => {
            setThreats(prev => [...prev, {id: Date.now() + index, type: violation.color, title: `${violation.type} | ${violation.city}`, location: violation.location, time: violation.time, severity: violation.severity, platform: violation.platform, originalVideo: `http://localhost:8000${violation.original_video}`, foundVideo: `http://localhost:8000${violation.found_video}`, isVideo: true}]);
          }, index * 500);
        });
        setTimeout(() => {setActiveTab('dashboard'); alert(`Found ${data.total_violations} unauthorized copies!`);}, 100);
      }
    } catch (err) {alert("Failed to analyze sample.");} finally {setIsScanning(false);}
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
              
              <div style={{ position: 'absolute', right: 0, top: '-55px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                {/* Media Type Selector */}
                <select 
                  value={mediaType}
                  onChange={(e) => setMediaType(e.target.value)}
                  style={{
                    background: 'var(--bg-panel)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-main)',
                    padding: '10px 15px',
                    borderRadius: '8px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  <option value="image">📷 Images</option>
                  <option value="video">🎥 Videos</option>
                </select>
                
                {/* Start/Pause Scraping Button */}
                <button
                  onClick={() => isAutoScraping ? setIsAutoScraping(false) : setIsAutoScraping(true)}
                  style={{ background: isAutoScraping ? 'var(--danger)' : 'var(--warning)', color: isAutoScraping ? 'white' : '#000', border: 'none', padding: '10px 20px', borderRadius: '8px', fontWeight: 700, cursor: 'pointer', display: 'flex', gap: '8px', alignItems: 'center', transition: 'all 0.3s' }}
                >
                  <Zap size={18} /> {isAutoScraping ? "Pause Live Scrape" : "Start Live Scrape"}
                </button>
              </div>
              
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
                            setSelectedViolation(threat);
                            setShowComparisonModal(true);
                            e.originalEvent.stopPropagation();
                          }
                        }}
                      >
                        <Popup className="dark-popup">
                          <strong>{threat.title}</strong><br/>
                          Severity: {threat.severity}<br/>
                          Platform: {threat.platform}<br/>
                          <button 
                            onClick={() => {
                              setSelectedViolation(threat);
                              setShowComparisonModal(true);
                            }}
                            style={{marginTop: '8px', padding: '4px 8px', cursor: 'pointer'}}
                          >
                            View Comparison
                          </button>
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
                          {threat.type === 'deepfake' ? 'AI Manipulated' : 
                           threat.type === 'watermark' ? 'Watermarked' : 
                           threat.type === 'repost' ? 'Reupload' : 'Modified'}
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
          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
            
            {/* Sample Images Gallery */}
            {mediaType === 'image' && sampleImages.length > 0 && (
              <div style={{ marginBottom: '40px', width: '100%', maxWidth: '900px' }}>
                <h3 style={{ marginBottom: '20px', textAlign: 'center' }}>Try Sample Images</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
                  {sampleImages.map(sample => (
                    <div 
                      key={sample.id}
                      style={{
                        background: 'var(--bg-panel)',
                        borderRadius: '12px',
                        padding: '16px',
                        border: '2px solid var(--border)',
                        cursor: 'pointer',
                        transition: 'all 0.3s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--primary)'}
                      onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
                    >
                      <img 
                        src={`http://localhost:8000${sample.path}`}
                        alt={sample.name}
                        style={{ width: '100%', borderRadius: '8px', marginBottom: '12px' }}
                      />
                      <h4 style={{ marginBottom: '8px', fontSize: '1rem' }}>{sample.name}</h4>
                      <button
                        onClick={() => analyzeSample(sample.id)}
                        disabled={isScanning}
                        style={{
                          width: '100%',
                          padding: '10px',
                          background: 'var(--primary)',
                          color: 'white',
                          border: 'none',
                          borderRadius: '8px',
                          fontWeight: 600,
                          cursor: isScanning ? 'not-allowed' : 'pointer',
                          opacity: isScanning ? 0.5 : 1
                        }}
                      >
                        {isScanning ? 'Analyzing...' : 'Analyze This Image'}
                      </button>
                    </div>
                  ))}
                </div>
                
                <div style={{ textAlign: 'center', margin: '30px 0', color: 'var(--text-muted)' }}>
                  <span>OR</span>
                </div>
              </div>
            )}
            
            {/* Sample Videos Gallery */}
            {mediaType === 'video' && sampleVideos.length > 0 && (
              <div style={{ marginBottom: '40px', width: '100%', maxWidth: '900px' }}>
                <h3 style={{ marginBottom: '20px', textAlign: 'center' }}>Try Sample Videos</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
                  {sampleVideos.map(sample => (
                    <div key={sample.id} style={{ background: 'var(--bg-panel)', borderRadius: '12px', padding: '16px', border: '2px solid var(--border)' }}>
                      <video src={`http://localhost:8000${sample.path}`} style={{ width: '100%', borderRadius: '8px', marginBottom: '12px' }} muted />
                      <h4 style={{ marginBottom: '8px', fontSize: '1rem' }}>{sample.name}</h4>
                      <button onClick={() => analyzeSampleVideo(sample.id)} disabled={isScanning} style={{ width: '100%', padding: '10px', background: 'var(--primary)', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: isScanning ? 'not-allowed' : 'pointer', opacity: isScanning ? 0.5 : 1 }}>
                        {isScanning ? 'Analyzing...' : 'Analyze This Video'}
                      </button>
                    </div>
                  ))}
                </div>
                <div style={{ textAlign: 'center', margin: '30px 0', color: 'var(--text-muted)' }}><span>OR</span></div>
              </div>
            )}
            
            {/* Media Type Toggle */}
            <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
              <button 
                onClick={() => setMediaType('image')}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: mediaType === 'image' ? 'var(--primary)' : 'var(--bg-panel)',
                  color: mediaType === 'image' ? 'white' : 'var(--text-main)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.3s'
                }}
              >
                📷 Images
              </button>
              <button 
                onClick={() => setMediaType('video')}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: mediaType === 'video' ? 'var(--primary)' : 'var(--bg-panel)',
                  color: mediaType === 'video' ? 'white' : 'var(--text-main)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.3s'
                }}
              >
                🎥 Videos
              </button>
            </div>
            
            <div 
              className={`upload-zone ${dragActive ? 'active' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <UploadCloud size={64} className="upload-icon" />
              <h2 className="upload-title">Register {mediaType === 'video' ? 'Video' : 'Image'} Asset</h2>
              <p className="upload-subtitle">
                Drag and drop your official {mediaType === 'video' ? 'videos' : 'images'} here to index them via FAISS {mediaType === 'video' ? '(keyframe-based)' : 'and CLIP'}.
              </p>
              
              <input 
                type="file" 
                id="file-upload" 
                style={{display: 'none'}} 
                onChange={handleFileChange}
                accept={mediaType === 'video' ? 'video/mp4,video/avi,video/mov,video/mkv' : 'image/jpeg,image/png,image/webp'}
                multiple
              />
              <label htmlFor="file-upload" className="upload-btn" style={{display: 'inline-block'}}>
                {isScanning ? 'Extracting Signatures...' : 'Browse Files'}
              </label>

              {isScanning && <div className="scan-overlay"></div>}
            </div>
            
            <div style={{marginTop: '40px', display: 'flex', gap: '32px', color: 'var(--text-muted)'}}>
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                <CheckCircle size={18} color="var(--success)"/> {mediaType === 'video' ? 'Extracts Keyframes' : 'Creates Perceptual Hash'}
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                <CheckCircle size={18} color="var(--success)"/> {mediaType === 'video' ? 'Averages Frame Hashes' : 'Extracts Semantic Embedding'}
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                <CheckCircle size={18} color="var(--success)"/> Mints Provenance Record
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Image Comparison Modal */}
      {showComparisonModal && selectedViolation && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '20px'
          }}
          onClick={() => setShowComparisonModal(false)}
        >
          <div 
            style={{
              background: 'var(--bg-main)',
              borderRadius: '16px',
              padding: '30px',
              maxWidth: '1200px',
              width: '100%',
              maxHeight: '90vh',
              overflow: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2>{selectedViolation.title}</h2>
              <button 
                onClick={() => setShowComparisonModal(false)}
                style={{
                  background: 'var(--danger)',
                  color: 'white',
                  border: 'none',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 600
                }}
              >
                Close
              </button>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '30px' }}>
              <div>
                <h3 style={{ marginBottom: '12px', color: 'var(--success)' }}>Original {selectedViolation.isVideo ? 'Video' : 'Image'}</h3>
                {selectedViolation.isVideo ? <video src={selectedViolation.originalVideo} controls style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--success)' }} /> : <img src={selectedViolation.originalImage} alt="Original" style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--success)' }} />}
                <p style={{ marginTop: '12px', color: 'var(--text-muted)' }}>Your protected asset</p>
              </div>
              
              <div>
                <h3 style={{ marginBottom: '12px', color: 'var(--danger)' }}>Found on Internet</h3>
                {selectedViolation.isVideo ? <video src={selectedViolation.foundVideo} controls style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--danger)' }} /> : <img src={selectedViolation.foundImage} alt="Found" style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--danger)' }} />}
                <div style={{ marginTop: '12px' }}>
                  <p><strong>Platform:</strong> {selectedViolation.platform}</p>
                  <p><strong>Type:</strong> {selectedViolation.title.split('|')[0].trim()}</p>
                  <p><strong>Detected:</strong> {selectedViolation.time}</p>
                  <p><strong>Severity:</strong> <span style={{ 
                    color: selectedViolation.severity === 'high' ? 'var(--danger)' : 
                           selectedViolation.severity === 'medium' ? 'var(--warning)' : 'var(--success)',
                    fontWeight: 600,
                    textTransform: 'uppercase'
                  }}>{selectedViolation.severity}</span></p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
