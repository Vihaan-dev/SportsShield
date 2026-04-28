# Solution Challenge 2026 - PPT Strategy & Content

Here is the proposed slide-by-slide content for the Solution Challenge 2026 prototype presentation, adhering to the structure in the provided PDF template.

---

## Slide 2: Team Details
**a. Team Name:** [Your Team Name]
**b. Team Leader Name:** [Leader Name]
**c. Problem Statement:** Protecting the Integrity of Digital Sports Media. Sports organizations generate massive volumes of high-value digital media. This vast visibility gap leaves proprietary content highly vulnerable to widespread digital misappropriation, unauthorized redistribution, and intellectual property violations. Our problem is the tracking and mitigation of this unauthorized use.

---

## Slide 3: Brief About Your Solution
**Solution Overview: "SportsShield" (or actual project name - Digital Asset Protection)**
We have built an end-to-end scalable platform designed to identify, track, and flag the unauthorized use of official sports media across the internet in near real-time. 
*   **Ingestion:** We ingest proprietary video and image assets and create secure, lightweight fingerprints (pHash and CLIP embeddings).
*   **Monitoring & Scraping:** We monitor external platforms (like Twitter, YouTube, Reddit) for suspect content using automated scrapers.
*   **Multi-Stage Detection:** We analyze suspect media using a robust, multi-tier AI processing sequence.
*   **AI Verdict:** We employ Google's Gemini LLM only for Type 3 / AI-generated cases, where it explains why the image looks synthetic. Type 1 and Type 2 cases stay on the local vision pipeline.

---

## Slide 4: Opportunities
**a. How different is it from any of the other existing ideas?**
*   **Cost-Effective Parallel AI:** Instead of relying on expensive, heavy deep learning models for every image, we use an escalating fast-fail architecture. Stage 1 (pHash) costs nearly zero compute. Only truly ambiguous assets reach Stage 3 (Gemini).
*   **Multilayered Threat Detection:** We don’t just find simple reposts. We find modified content (pixel-diff overlay detection) and deepfakes/AI-manipulation (FFT + SSIM + histogram + face checks) simultaneously.

**b. How will it be able to solve the problem?**
*   By proactively crawling platforms and indexing suspect content, rights holders don't have to wait for reports. Our system autonomously links found content back to the authenticated original asset and computes a severity score for prioritization.

**c. USP of the proposed solution**
*   **End-to-End Automation with Human-Readable Explanations:** From fingerprinting to the auto-generation of concise AI-alteration explanations via Gemini, drastically reducing manual review time.
*   **Geospatial Provenance Mapping:** Visualizing viral propagation of stolen assets in real-time on a map to identify coordinated campaigns versus lone actors.

---

## Slide 5: List of Features Offered by the Solution
1. **Asset Registration & Fingerprinting:** Generate perceptual hashes (pHash) and maintain a CLIP helper path for semantic indexing during registration.
2. **Automated Content Scraping:** Ingestion pipelines for platforms like Twitter, YouTube, and Reddit.
3. **Tri-Classifier Analysis Engine:** 
    *   **Level 1:** Hash delta comparison for direct reposts using pHash.
    *   **Level 2:** Pixel-diff overlay detection with ORB alignment for watermark and text detection.
    *   **Level 3:** Multi-signal scoring: FFT (frequency), SSIM (structural similarity), histogram correlation, and optional face consistency checks for AI deepfakes.
4. **Google AI Integration (Gemini):** Type 3 explanation layer that turns the local evidence into a concise human-readable reason.
5. **Real-time Geospatial Dashboard:** Leaflet.js powered interactive map, live feed, and scan console for suspicious content.

---

## Slide 6: Process flow diagram or Use-case diagram
*(You will need to create a visual diagram for the slide, but here is the logic it should represent):*
1. **User (Admin)** -> Uploads Original Asset.
2. **System** -> Computes pHash; CLIP exists as a helper for registration only, while the detection pipeline relies on local hashes and vision signals.
3. **Scraper Service** -> Finds suspect content on social media -> Triggers Detection.
4. **Detection Pipeline** -> 
    *   Checks FAISS (Fast Match).
    *   Runs Classifier Bank (Hash Delta, Pixel-Diff Alignment, Deepfake Multi-Signal).
5. **Decision Node** -> If Type 3 is detected, send the local evidence to **Google Gemini** for explanation.
6. **Gemini** -> Generates a concise AI-alteration explanation, not the decision itself.
7. **Frontend App** -> Displays on Geolocation Map & Dashboard.

---

## Slide 7: Wireframes/Mock diagrams of the proposed solution
*(Include screenshots or Figma designs here. Suggested screens to showcase based on the blueprint):*
1. **Registration View:** Drag & Drop upload with fingerprint preview.
2. **Dashboard View:** Live map (Leaflet.js) with clustered alerts, filtered feed, and threat summary cards.
3. **Inspection View:** Suspect upload panel, local classifier scores, pipeline status, and the Gemini-generated Type 3 explanation box.

---

## Slide 8: Architecture diagram of the proposed solution
*(You will need to design this, but mention these components):*
*   **Frontend:** React, Leaflet.js, interactive feed and inspector panels
*   **Backend:** FastAPI (Python), uvicorn
*   **Database/Storage:** FAISS (for high-speed vector similarity search), SQLite (metadata & provenance)
*   **Computer Vision/AI Layer:** `imagehash`, FAISS Vector Search, ORB Alignment, SSIM analysis, `deepface` (Facenet), `open-clip-torch`, OpenCV
*   **Cloud & Google AI:** Google Gemini API (`google-generativeai`) for Type 3 explanations only, Google deployment (GCP Cloud Run - as required by template)

---

## Slide 9: Technologies to be used in the solution
*   **Language:** Python, JavaScript (React)
*   **Frameworks:** FastAPI, React
*   **Google Technologies:** **Google Gemini API** for explanation generation on Type 3 cases, Google Cloud Run (Deployment)
*   **Core AI/CV Libraries:** `imagehash`, FAISS, OpenCV (ORB/Homography), SSIM analysis, Deepface (Facenet), OpenCLIP helper path
*   **Data/Mapping:** Geopy, Leaflet.js

---

## Slide 10: Estimated implementation cost
*   **APIs (Social Media):** Free tiers for Twitter/Reddit/YouTube (Development), estimated $X for enterprise production.
*   **Compute (GCP Cloud Run):** ~$X/month (Highly scalable, mostly scales to zero when inactive).
*   **Google Gemini API:** Free tier (Hackathon), pay-as-you-go for production.
*   *Note: Because our Stage 1 & 2 classifiers run primarily on CPU, massive GPU server costs (AWS EC2 p-instances) are avoided entirely.*

---

## Slide 11: Snapshots of the MVP
*(Insert final screenshots of your working React application here, highlighting the interactive map, recent-alert feed, suspect image inspector, and Type 3 Gemini explanation card).*

---

## Slide 12: Additional Details/Future Development
*   **Video Temporal Flow Analysis:** Fully implementing temporal variance tracking across deepface embeddings to catch advanced frame-by-frame deepfakes.
*   **Live Webhooks:** Transitioning from polling APIs to live streaming webhooks from major social platforms for instant 0-day detection.
*   **Stronger Semantic Search:** Re-enabling CLIP-based semantic matching in detection once the registration-side helper path is fully hardened.

---

## Slide 13: Links
*   **GitHub Public Repository:** [Link]
*   **Demo Video Link (3 Minutes):** [Link]
*   **MVP Link:** [Link]
*   **Working Prototype Link:** [Link]
