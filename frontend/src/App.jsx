import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Activity,
  ArrowUpRight,
  Bot,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  FileSearch,
  Filter,
  Globe,
  Image as ImageIcon,
  Layers,
  Map as MapIcon,
  PauseCircle,
  PlayCircle,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  UploadCloud,
  Zap,
} from 'lucide-react';
import './index.css';

const API_BASE = 'http://localhost:8000';

const WORLD_POINTS = [
  [19.076, 72.8777],
  [51.556, -0.2796],
  [34.0522, -118.2437],
  [48.8566, 2.3522],
  [-33.8688, 151.2093],
  [40.7128, -74.006],
  [35.6895, 139.6917],
];

const FILTERS = [
  { key: 'all', label: 'All alerts' },
  { key: 'type1', label: 'Type 1' },
  { key: 'type2', label: 'Type 2' },
  { key: 'type3', label: 'Type 3' },
  { key: 'gemini', label: 'Gemini explained' },
];

const MOCK_ALERTS = [
  {
    id: 'seed-1',
    title: 'FaceSwap Detected | IPL Final',
    kind: 'type3',
    severity: 'high',
    platform: 'Twitter',
    time: '2 mins ago',
    location: [19.076, 72.8777],
    source: 'Live scrape',
    fileName: 'ipl_face_ai.jpg',
    explanation: {
      enabled: true,
      provider: 'gemini',
      explanation: 'The suspect frame keeps the same scene layout but the face region and frequency profile drift enough to look synthetic. The strongest clues are the low structural similarity and the changed high-frequency texture.',
      status: 'ok',
    },
    pipeline: {
      phash: true,
      ocr: true,
      deepfake: true,
      gemini: true,
      clip: { active: false, note: 'CLIP is not used in detection.' },
    },
    scores: { 'Type 1 - Repost / Near Exact Copy': 0.8, 'Type 2 - Watermark / Text Addition': 0.7, 'Type 3 - Deepfake / AI Alteration': 2.8 },
  },
  {
    id: 'seed-2',
    title: 'Watermarked Asset | FIFA',
    kind: 'type2',
    severity: 'medium',
    platform: 'Reddit',
    time: '14 mins ago',
    location: [48.8566, 2.3522],
    source: 'Live scrape',
    fileName: 'fifa_watermark.jpg',
    explanation: null,
    pipeline: { phash: true, ocr: true, deepfake: true, gemini: false, clip: { active: false, note: 'CLIP is not used in detection.' } },
    scores: { 'Type 1 - Repost / Near Exact Copy': 0.4, 'Type 2 - Watermark / Text Addition': 1.9, 'Type 3 - Deepfake / AI Alteration': 0.3 },
  },
  {
    id: 'seed-3',
    title: 'Unauthorized Highlight | UCL',
    kind: 'type1',
    severity: 'low',
    platform: 'TikTok',
    time: '22 mins ago',
    location: [51.556, -0.2796],
    source: 'Live scrape',
    fileName: 'ucl_repost.jpg',
    explanation: null,
    pipeline: { phash: true, ocr: true, deepfake: true, gemini: false, clip: { active: false, note: 'CLIP is not used in detection.' } },
    scores: { 'Type 1 - Repost / Near Exact Copy': 2.1, 'Type 2 - Watermark / Text Addition': 0.0, 'Type 3 - Deepfake / AI Alteration': 0.0 },
  },
  {
    id: 'seed-4',
    title: 'Generative AI Re-creation | NBA',
    kind: 'type3',
    severity: 'high',
    platform: 'Instagram',
    time: '1 hr ago',
    location: [34.0522, -118.2437],
    source: 'Live scrape',
    fileName: 'nba_ai.jpg',
    explanation: {
      enabled: true,
      provider: 'gemini',
      explanation: 'Gemini sees a visually consistent scene, but the edges, face contours, and texture statistics look like a regenerated frame rather than a copy. It reads as AI-altered instead of a normal repost or overlay.',
      status: 'ok',
    },
    pipeline: { phash: true, ocr: true, deepfake: true, gemini: true, clip: { active: false, note: 'CLIP is not used in detection.' } },
    scores: { 'Type 1 - Repost / Near Exact Copy': 0.6, 'Type 2 - Watermark / Text Addition': 0.4, 'Type 3 - Deepfake / AI Alteration': 3.3 },
  },
];

const formatScore = (value) => `${Number(value || 0).toFixed(2)}`;

const classifyType = (violationType = '') => {
  if (violationType.includes('Type 3')) return 'type3';
  if (violationType.includes('Type 2')) return 'type2';
  return 'type1';
};

const severityForType = (kind) => {
  if (kind === 'type3') return 'high';
  if (kind === 'type2') return 'medium';
  return 'low';
};

const labelForKind = (kind) => {
  if (kind === 'type3') return 'Type 3';
  if (kind === 'type2') return 'Type 2';
  return 'Type 1';
};

const chooseLocation = (kind, index = 0) => WORLD_POINTS[(index + (kind === 'type3' ? 2 : kind === 'type2' ? 1 : 0)) % WORLD_POINTS.length];

const createThreatIcon = (kind) => {
  const label = kind === 'type3' ? 'AI' : kind === 'type2' ? 'TXT' : 'COPY';
  return new L.DivIcon({
    html: `<div class="threat-pin ${kind}"><span>${label}</span></div>`,
    className: 'threat-pin-wrap',
    iconSize: L.point(46, 46, true),
  });
};

const createClusterIcon = (cluster) => {
  const count = cluster.getChildCount();
  return new L.DivIcon({
    html: `<div class="threat-cluster"><span>${count}</span></div>`,
    className: 'threat-cluster-wrap',
    iconSize: L.point(54, 54, true),
  });
};

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isAutoScraping, setIsAutoScraping] = useState(false);
  const [alerts, setAlerts] = useState(MOCK_ALERTS);
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [selectedAlertId, setSelectedAlertId] = useState(MOCK_ALERTS[0]?.id ?? null);
  const [registeredAssets, setRegisteredAssets] = useState(24);
  const [latestScan, setLatestScan] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [scanFile, setScanFile] = useState(null);
  const [registerFile, setRegisterFile] = useState(null);
  const [scanPreviewUrl, setScanPreviewUrl] = useState('');
  const [registerPreviewUrl, setRegisterPreviewUrl] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(null), 4500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!scanFile) {
      setScanPreviewUrl('');
      return undefined;
    }
    const url = URL.createObjectURL(scanFile);
    setScanPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [scanFile]);

  useEffect(() => {
    if (!registerFile) {
      setRegisterPreviewUrl('');
      return undefined;
    }
    const url = URL.createObjectURL(registerFile);
    setRegisterPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [registerFile]);

  useEffect(() => {
    if (!isAutoScraping) return undefined;

    const timer = window.setInterval(() => {
      void runLiveScrape(true);
    }, 5000);

    return () => window.clearInterval(timer);
  }, [isAutoScraping]);

  useEffect(() => {
    if (!alerts.length) {
      setSelectedAlertId(null);
      return;
    }
    if (!alerts.some((alert) => alert.id === selectedAlertId)) {
      setSelectedAlertId(alerts[0].id);
    }
  }, [alerts, selectedAlertId]);

  const visibleAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      if (selectedFilter === 'all') return true;
      if (selectedFilter === 'gemini') return Boolean(alert.explanation?.enabled);
      return alert.kind === selectedFilter;
    });
  }, [alerts, selectedFilter]);

  const selectedAlert = alerts.find((alert) => alert.id === selectedAlertId) ?? null;
  const latestExplanation = latestScan?.gemini_explanation ?? null;

  const addAlert = (result, sourceLabel, fileName) => {
    const kind = classifyType(result.violation_type || '');
    let createdAlert = null;

    setAlerts((prev) => {
      createdAlert = {
        id: `alert-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        title: result.title || fileName || 'Detected asset',
        kind,
        severity: severityForType(kind),
        platform: result.platform || (kind === 'type3' ? 'Instagram' : 'Twitter'),
        time: 'Just now',
        location: chooseLocation(kind, prev.length),
        source: sourceLabel,
        fileName,
        explanation: result.gemini_explanation ?? null,
        pipeline: result.pipeline ?? null,
        scores: result.classification_scores ?? null,
        evidence: {
          ocr: result.ocr_findings ?? null,
          deepfake: result.deepfake_findings ?? null,
        },
        raw: result,
      };

      return [createdAlert, ...prev].slice(0, 40);
    });

    if (createdAlert) {
      setSelectedAlertId(createdAlert.id);
    }

    return createdAlert;
  };

  const runLiveScrape = async (silent = false) => {
    try {
      const response = await fetch(`${API_BASE}/simulate_scrape`);
      const data = await response.json();

      if (data.verdict === 'suspicious') {
        setLatestScan(data);
        addAlert(data, 'Live scrape', data.suspect_phash ? `scrape-${data.suspect_phash.slice(0, 8)}` : 'scraped-media');
        if (!silent) {
          setNotice({
            tone: 'success',
            title: 'Threat captured',
            message: data.gemini_explanation?.explanation || data.message || 'Suspicious media entered the feed.',
          });
        }
      } else if (data.error) {
        if (!silent) {
          setNotice({ tone: 'danger', title: 'Live scrape failed', message: data.error });
        }
        setIsAutoScraping(false);
      } else {
        if (!silent) {
          setNotice({
            tone: 'success',
            title: 'Clean scrape',
            message: data.message || data.title || 'No issue detected.',
          });
        }
      }
    } catch (error) {
      if (!silent) {
        setNotice({ tone: 'danger', title: 'Backend offline', message: 'Failed to run scan. Start the FastAPI backend first.' });
      }
      setIsAutoScraping(false);
    }
  };

  const runDetection = async (file) => {
    setIsAnalyzing(true);
    setScanFile(file);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/inspect`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      setLatestScan({ ...data, fileName: file.name, previewUrl: scanPreviewUrl });

      if (data.registered?.asset_id) {
        setRegisteredAssets((prev) => prev + 1);
      }

      if (response.ok && data.verdict === 'suspicious') {
        const createdAlert = addAlert(data, 'Manual inspection', file.name);
        setNotice({
          tone: 'success',
          title: 'Inspected & auto-registered',
          message: data.gemini_explanation?.explanation || 'Local pipeline flagged the image. Asset added to registry.',
        });
      } else if (response.ok) {
        setNotice({
          tone: 'success',
          title: data.title || 'Inspected & auto-registered',
          message: data.registered?.asset_id
            ? `Clean scan. Registered as ${data.registered.asset_id}.`
            : (data.message || 'The asset looked clean or was too ambiguous to escalate.'),
        });
      } else {
        setNotice({ tone: 'danger', title: 'Scan failed', message: data.detail || 'Detection request failed.' });
      }
    } catch (error) {
      setNotice({ tone: 'danger', title: 'Scan failed', message: 'Could not connect to the backend.' });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const runRegistration = async (file) => {
    setIsRegistering(true);
    setRegisterFile(file);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('owner', 'Official Broadcaster');

    try {
      const response = await fetch(`${API_BASE}/register`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (response.ok) {
        setRegisteredAssets((prev) => prev + 1);
        setNotice({
          tone: 'success',
          title: 'Asset indexed',
          message: `Asset ${data.asset_id} registered. CLIP remains disabled in detection, but the backend keeps the helper path ready.`,
        });
      } else {
        setNotice({ tone: 'danger', title: 'Registration failed', message: data.detail || JSON.stringify(data) });
      }
    } catch (error) {
      setNotice({ tone: 'danger', title: 'Backend offline', message: 'Could not connect to register the asset.' });
    } finally {
      setIsRegistering(false);
    }
  };

  const handleDrop = async (event, mode) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);

    const file = event.dataTransfer.files?.[0];
    if (!file) return;

    if (mode === 'scan') {
      await runDetection(file);
    } else {
      await runRegistration(file);
    }
  };

  const handleFileInput = async (event, mode) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (mode === 'scan') {
      await runDetection(file);
    } else {
      await runRegistration(file);
    }

    event.target.value = '';
  };

  const scoreEntries = latestScan?.classification_scores
    ? Object.entries(latestScan.classification_scores)
    : selectedAlert?.scores
      ? Object.entries(selectedAlert.scores)
      : [];

  const maxScore = scoreEntries.length ? Math.max(...scoreEntries.map(([, value]) => Number(value) || 0)) : 0;

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <button
          type="button"
          className="brand-block"
          onClick={() => setSidebarCollapsed((p) => !p)}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <div className="brand-mark">
            <Shield color="#ffffff" size={22} />
          </div>
          {!sidebarCollapsed && (
            <div>
              <div className="brand-name">Sentinel.io</div>
              <div className="brand-subtitle">Media integrity</div>
            </div>
          )}
        </button>

        <nav className="nav-stack">
          <button className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')} type="button" title="Threat Radar">
            <Activity size={18} />
            {!sidebarCollapsed && <span>Threat Radar</span>}
          </button>
          <button className={`nav-item ${activeTab === 'inspect' ? 'active' : ''}`} onClick={() => setActiveTab('inspect')} type="button" title="Inspect & Register">
            <FileSearch size={18} />
            {!sidebarCollapsed && <span>Inspect & Register</span>}
          </button>
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <div className="eyebrow">Digital asset intelligence</div>
            <h1>{activeTab === 'overview' ? 'Global Threat Radar' : 'Inspect & Register'}</h1>
            <p>
              {activeTab === 'overview'
                ? 'Track suspicious media across the map, inspect the local scores, and open a Gemini explanation only when the result is Type 3.'
                : 'Drop an image to run the full pipeline. The asset is auto-registered to the official index after inspection.'}
            </p>
          </div>

          <div className="topbar-actions">
            <button className={`pill-button ${isAutoScraping ? 'danger' : 'warning'}`} onClick={() => setIsAutoScraping((prev) => !prev)} type="button">
              {isAutoScraping ? <PauseCircle size={16} /> : <PlayCircle size={16} />}
              {isAutoScraping ? 'Pause live scrape' : 'Start live scrape'}
            </button>
            <div className="alert-counter">
              <ShieldAlert size={15} />
              <span><strong>{visibleAlerts.length}</strong> visible alerts</span>
            </div>
          </div>
        </header>

        {notice && (
          <div className={`notice-card ${notice.tone}`}>
            <div className="notice-title">{notice.title}</div>
            <div className="notice-message">{notice.message}</div>
          </div>
        )}

        {activeTab === 'overview' && (
          <section className="overview-layout">
            <div className="metric-row">
              <article className="metric-card">
                <div className="metric-icon cyan"><ImageIcon size={22} /></div>
                <div>
                  <div className="metric-label">Protected assets</div>
                  <div className="metric-value">{registeredAssets.toString().padStart(2, '0')}</div>
                </div>
              </article>
              <article className="metric-card">
                <div className="metric-icon red"><ShieldAlert size={22} /></div>
                <div>
                  <div className="metric-label">Active alerts</div>
                  <div className="metric-value">{alerts.length.toString().padStart(2, '0')}</div>
                </div>
              </article>
              <article className="metric-card">
                <div className="metric-icon green"><Sparkles size={22} /></div>
                <div>
                  <div className="metric-label">Gemini explanations</div>
                  <div className="metric-value">{alerts.filter((alert) => alert.explanation?.enabled).length.toString().padStart(2, '0')}</div>
                </div>
              </article>
              <article className="metric-card">
                <div className="metric-icon amber"><TrendingUp size={22} /></div>
                <div>
                  <div className="metric-label">Type 3 share</div>
                  <div className="metric-value">{alerts.length ? `${Math.round((alerts.filter((a) => a.kind === 'type3').length / alerts.length) * 100)}%` : '0%'}</div>
                </div>
              </article>
            </div>

            <div className="overview-grid">
              <section className="panel map-panel">
                <div className="panel-head">
                  <div>
                    <div className="panel-kicker">Live intelligence map</div>
                    <h2>Alert propagation</h2>
                  </div>
                  <div className="panel-head-meta">
                    <MapIcon size={16} />
                    <span>Interactive clusters</span>
                  </div>
                </div>
                <div className="map-frame">
                  <MapContainer center={[20, 0]} zoom={2} scrollWheelZoom={false} className="leaflet-map">
                    <TileLayer
                      url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png"
                      attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                    />
                    <MarkerClusterGroup
                      chunkedLoading
                      zoomToBoundsOnClick={false}
                      spiderfyOnMaxZoom={false}
                      iconCreateFunction={createClusterIcon}
                    >
                      {visibleAlerts.map((alert) => (
                        <Marker
                          key={alert.id}
                          position={alert.location}
                          icon={createThreatIcon(alert.kind)}
                          eventHandlers={{
                            click: () => setSelectedAlertId(alert.id),
                          }}
                        >
                          <Popup className="dark-popup">
                            <strong>{alert.title}</strong>
                            <br />
                            {labelForKind(alert.kind)} · {alert.platform}
                            <br />
                            {alert.explanation?.enabled ? 'Gemini explanation available' : 'Local scores only'}
                          </Popup>
                        </Marker>
                      ))}
                    </MarkerClusterGroup>
                  </MapContainer>
                </div>
              </section>

              <section className="panel detail-panel">
                {selectedAlert ? (
                  <>
                    <div className="alert-hero">
                      <div className={`alert-hero-icon ${selectedAlert.kind}`}>
                        {selectedAlert.kind === 'type3' ? 'AI' : selectedAlert.kind === 'type2' ? 'TXT' : 'CP'}
                      </div>
                      <div className="alert-hero-body">
                        <div className="panel-kicker">Selected alert</div>
                        <h2>{selectedAlert.title}</h2>
                        <div className="alert-hero-meta">
                          <span>{labelForKind(selectedAlert.kind)}</span>
                          <span className="dot">·</span>
                          <span>{selectedAlert.platform}</span>
                          <span className="dot">·</span>
                          <span>{selectedAlert.time}</span>
                        </div>
                      </div>
                      <div className={`severity-badge ${selectedAlert.severity}`}>{selectedAlert.severity}</div>
                    </div>

                    <div className="kv-row">
                      <div className="kv-cell">
                        <span className="kv-label">Source</span>
                        <span className="kv-value">{selectedAlert.source}</span>
                      </div>
                      <div className="kv-cell">
                        <span className="kv-label">File</span>
                        <span className="kv-value mono">{selectedAlert.fileName}</span>
                      </div>
                    </div>

                    <div className="section-block">
                      <div className="section-label">Detector confidence</div>
                      <div className="score-list">
                        {(() => {
                          const entries = Object.entries(selectedAlert.scores || {});
                          const total = entries.reduce((s, [, v]) => s + (Number(v) || 0), 0) || 1;
                          const winnerVal = Math.max(...entries.map(([, v]) => Number(v) || 0));
                          return entries.map(([label, value]) => {
                            const num = Number(value) || 0;
                            const pct = (num / total) * 100;
                            const isWinner = num === winnerVal && num > 0;
                            const short = label.split(' - ')[0];
                            const desc = label.split(' - ')[1] || '';
                            return (
                              <div className={`score-row ${isWinner ? 'winner' : ''}`} key={label}>
                                <div className="score-row-head">
                                  <span className="score-tag">{short}</span>
                                  <span className="score-desc">{desc}</span>
                                  <span className="score-num">{pct.toFixed(0)}%</span>
                                </div>
                                <div className="score-track">
                                  <div className="score-fill" style={{ width: `${Math.max(pct, 4)}%` }} />
                                </div>
                              </div>
                            );
                          });
                        })()}
                      </div>
                    </div>

                    {selectedAlert.explanation?.enabled ? (
                      <div className="explanation-card highlight">
                        <div className="explanation-head">
                          <Bot size={18} />
                          <span>{selectedAlert.explanation.provider === 'gemini' ? 'Gemini explanation' : 'Local explanation'}</span>
                        </div>
                        <p>{selectedAlert.explanation.explanation}</p>
                      </div>
                    ) : (
                      <div className="explanation-card muted">
                        <div className="explanation-head">
                          <FileSearch size={18} />
                          <span>Local note</span>
                        </div>
                        <p>
                          This case did not need Gemini. Simple crop or text-overlay cases stay on the local path so the dashboard remains fast and cheap.
                        </p>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <div className="panel-head">
                      <div>
                        <div className="panel-kicker">Selected alert</div>
                        <h2>No alert selected</h2>
                      </div>
                      <div className="severity-badge low">idle</div>
                    </div>
                    <div className="empty-state">Select an alert from the feed or run a live scrape to populate the panel.</div>
                  </>
                )}
              </section>
            </div>

            <section className="panel feed-panel">
              <div className="panel-head">
                <div>
                  <div className="panel-kicker">Live feed</div>
                  <h2>Recent detections</h2>
                </div>
                <div className="filter-row">
                  <Filter size={16} />
                  {FILTERS.map((filter) => (
                    <button
                      key={filter.key}
                      type="button"
                      className={`filter-chip ${selectedFilter === filter.key ? 'active' : ''}`}
                      onClick={() => setSelectedFilter(filter.key)}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="feed-list">
                {visibleAlerts.length === 0 ? (
                  <div className="empty-state">No alerts match this filter yet.</div>
                ) : (
                  visibleAlerts.map((alert) => (
                    <button key={alert.id} type="button" className={`feed-item ${selectedAlertId === alert.id ? 'selected' : ''}`} onClick={() => setSelectedAlertId(alert.id)}>
                      <div className={`feed-dot ${alert.kind}`} />
                      <div className="feed-content">
                        <div className="feed-topline">
                          <span>{alert.title}</span>
                          <span>{alert.time}</span>
                        </div>
                        <div className="feed-meta">
                          <span>{labelForKind(alert.kind)}</span>
                          <span>•</span>
                          <span>{alert.platform}</span>
                          <span>•</span>
                          <span>{alert.source}</span>
                        </div>
                      </div>
                      <ArrowUpRight size={16} className="feed-arrow" />
                    </button>
                  ))
                )}
              </div>
            </section>
          </section>
        )}

        {activeTab === 'inspect' && (
          <section className="inspect-grid">
            <div className={`panel upload-panel ${dragActive ? 'drag-active' : ''}`} onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }} onDragOver={(event) => { event.preventDefault(); setDragActive(true); }} onDragLeave={(event) => { event.preventDefault(); setDragActive(false); }} onDrop={(event) => handleDrop(event, 'scan')}>
              <div className="upload-hero">
                <div className="upload-icon-wrap">
                  <UploadCloud size={48} />
                </div>
                <div>
                  <h2>Drop an image</h2>
                  <p>Runs the full detection pipeline, then auto-registers the asset to the official index.</p>
                </div>
              </div>

              <label className="upload-button" htmlFor="scan-input">
                {isAnalyzing ? 'Analyzing...' : 'Browse suspect media'}
              </label>
              <input id="scan-input" type="file" accept="image/png,image/jpeg,image/webp" className="hidden-input" onChange={(event) => handleFileInput(event, 'scan')} />

              {scanPreviewUrl && (
                <div className="preview-card">
                  <img src={scanPreviewUrl} alt="Suspect preview" className="preview-image" />
                  <div className="preview-meta">
                    <span>{scanFile?.name}</span>
                    <span>{isAnalyzing ? 'Scanning now' : 'Ready'}</span>
                  </div>
                </div>
              )}

            </div>

            <div className="panel result-panel">
              <div className="panel-head">
                <div>
                  <div className="panel-kicker">Latest inspection</div>
                  <h2>{latestScan?.title || 'Awaiting scan'}</h2>
                </div>
                <div className={`severity-badge ${latestScan?.verdict === 'clear' ? 'low' : latestScan?.violation_type?.includes('Type 3') ? 'high' : 'medium'}`}>
                  {latestScan?.verdict || 'idle'}
                </div>
              </div>

              {latestScan ? (
                <>
                  <div className="detail-summary stacked">
                    <div>
                      <div className="detail-label">Decision</div>
                      <div className="detail-value">{latestScan.verdict === 'suspicious' ? latestScan.violation_type : latestScan.verdict}</div>
                    </div>
                    <div>
                      <div className="detail-label">Closest original</div>
                      <div className="detail-value">{latestScan.closest_original_asset || 'n/a'}</div>
                    </div>
                    <div>
                      <div className="detail-label">pHash distance</div>
                      <div className="detail-value">{latestScan.hamming_distance_estimate ?? 'n/a'}</div>
                    </div>
                  </div>

                  <div className="score-list compact">
                    {scoreEntries.length ? scoreEntries.map(([label, value]) => {
                      const width = maxScore ? Math.max((Number(value) / maxScore) * 100, 8) : 0;
                      return (
                        <div className="score-row" key={label}>
                          <div className="score-row-head">
                            <span>{label}</span>
                            <span>{formatScore(value)}</span>
                          </div>
                          <div className="score-track">
                            <div className="score-fill" style={{ width: `${width}%` }} />
                          </div>
                        </div>
                      );
                    }) : (
                      <div className="empty-state">No classification scores yet.</div>
                    )}
                  </div>

                  <div className="pipeline-grid">
                    <div className={`pipeline-card ${latestScan?.pipeline?.phash ? 'on' : 'off'}`}>
                      <strong>pHash</strong>
                      <span>Structural match gate</span>
                    </div>
                    <div className={`pipeline-card ${latestScan?.pipeline?.ocr ? 'on' : 'off'}`}>
                      <strong>OCR</strong>
                      <span>Watermark / text overlay path</span>
                    </div>
                    <div className={`pipeline-card ${latestScan?.pipeline?.deepfake ? 'on' : 'off'}`}>
                      <strong>Deepfake</strong>
                      <span>FFT, SSIM, histogram signals</span>
                    </div>
                    <div className={`pipeline-card ${latestScan?.pipeline?.gemini ? 'on' : 'off'}`}>
                      <strong>Gemini</strong>
                      <span>Type 3 explanation layer</span>
                    </div>
                    <div className="pipeline-card off">
                      <strong>CLIP</strong>
                      <span>{latestScan?.pipeline?.clip?.note || 'Not used in detection'}</span>
                    </div>
                  </div>

                  <div className="explanation-card highlight">
                    <div className="explanation-head">
                      <Bot size={18} />
                      <span>{latestExplanation?.enabled ? 'Gemini explanation' : 'Local interpretation'}</span>
                    </div>
                    <p>
                      {latestExplanation?.explanation || latestScan.message || 'The local pipeline produced a result, but no Gemini explanation was needed for this case.'}
                    </p>
                  </div>

                  <div className="raw-note">
                    <strong>Evidence snapshot</strong>
                    <span>OCR and deepfake findings stay local; Gemini is only used after the local verdict lands on Type 3.</span>
                  </div>
                </>
              ) : (
                <div className="empty-state">Scan an image to populate the explanation panel.</div>
              )}
            </div>
          </section>
        )}

      </main>
    </div>
  );
}

export default App;
