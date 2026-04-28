// Copy your current App.jsx and add these changes:

// 1. Add sampleVideos state
const [sampleVideos, setSampleVideos] = useState([]);

// 2. Load sample videos in useEffect
useEffect(() => {
  fetch("http://localhost:8000/get_sample_images")
    .then(res => res.json())
    .then(data => setSampleImages(data.samples));
  
  fetch("http://localhost:8000/get_sample_videos")
    .then(res => res.json())
    .then(data => setSampleVideos(data.samples));
}, []);

// 3. Add video analysis functions after analyzeSample
const analyzeUploadedVideo = async (file) => {
  setIsScanning(true);
  const formData = new FormData();
  formData.append("file", file);
  
  try {
    const response = await fetch("http://localhost:8000/analyze_upload_video", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    
    if (data.status === "found") {
      setThreats([]);
      data.violations.forEach((violation, index) => {
        setTimeout(() => {
          setThreats(prev => [...prev, {
            id: Date.now() + index,
            type: violation.color,
            title: `${violation.type} | ${violation.city}`,
            location: violation.location,
            time: violation.time,
            severity: violation.severity,
            platform: violation.platform,
            originalVideo: `http://localhost:8000${violation.original_video}`,
            foundVideo: `http://localhost:8000${violation.found_video}`,
            isVideo: true
          }]);
        }, index * 500);
      });
      alert(`Found ${data.total_violations} unauthorized copies!`);
    } else {
      alert(data.message);
    }
  } catch (err) {
    alert("Failed to analyze video.");
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
    const response = await fetch("http://localhost:8000/analyze_sample_video", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    
    if (data.status === "found") {
      data.violations.forEach((violation, index) => {
        setTimeout(() => {
          setThreats(prev => [...prev, {
            id: Date.now() + index,
            type: violation.color,
            title: `${violation.type} | ${violation.city}`,
            location: violation.location,
            time: violation.time,
            severity: violation.severity,
            platform: violation.platform,
            originalVideo: `http://localhost:8000${violation.original_video}`,
            foundVideo: `http://localhost:8000${violation.found_video}`,
            isVideo: true
          }]);
        }, index * 500);
      });
      setTimeout(() => {
        setActiveTab('dashboard');
        alert(`Found ${data.total_violations} unauthorized copies!`);
      }, 100);
    }
  } catch (err) {
    alert("Failed to analyze sample.");
  } finally {
    setIsScanning(false);
  }
};

// 4. Update handleFileChange to call video functions
const handleFileChange = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    const file = e.target.files[0];
    if (mediaType === 'image') {
      analyzeUploadedImage(file);
    } else {
      analyzeUploadedVideo(file);
    }
    e.target.value = null;
  }
};

// 5. Add video gallery after image gallery (before Media Type Toggle)
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

// 6. Update modal to support videos - replace the image tags with:
<h3>Original {selectedViolation.isVideo ? 'Video' : 'Image'}</h3>
{selectedViolation.isVideo ? (
  <video src={selectedViolation.originalVideo} controls style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--success)' }} />
) : (
  <img src={selectedViolation.originalImage} alt="Original" style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--success)' }} />
)}

// Same for found content
{selectedViolation.isVideo ? (
  <video src={selectedViolation.foundVideo} controls style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--danger)' }} />
) : (
  <img src={selectedViolation.foundImage} alt="Found" style={{ width: '100%', borderRadius: '12px', border: '2px solid var(--danger)' }} />
)}
