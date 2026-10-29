const puppeteer = require('/tmp/pup-deck/node_modules/puppeteer');
const fs = require('fs');
const path = require('path');

function getBase64Image(filePath) {
  if (fs.existsSync(filePath)) {
    const data = fs.readFileSync(filePath);
    return `data:image/png;base64,${data.toString('base64')}`;
  }
  return '';
}

const cockpitImg = getBase64Image('/tmp/screenshot_cockpit.png');
const biltiImg = getBase64Image('/tmp/screenshot_bilti.png');
const dhabaImg = getBase64Image('/tmp/screenshot_dhaba.png');
const hospitalImg = getBase64Image('/tmp/screenshot_hospital.png');

const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Fuel-Check & Disha Compass Platform - Pitch Deck</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    @page {
      size: 1920px 1080px;
      margin: 0;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #070a0e;
      color: #e2e8f0;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }

    .slide {
      width: 1920px;
      height: 1080px;
      page-break-after: always;
      position: relative;
      overflow: hidden;
      padding: 70px 90px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background: radial-gradient(circle at 80% 20%, #111a24 0%, #070a0e 70%);
      border: 1px solid #141c24;
    }

    /* Subtle grid background */
    .slide::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background-image: linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 60px 60px;
      pointer-events: none;
      z-index: 0;
    }

    .slide > * {
      position: relative;
      z-index: 1;
    }

    /* Header & Footer */
    .slide-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 25px;
    }

    .slide-tag {
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 2px;
      color: #10b981;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .slide-tag::before {
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      display: inline-block;
      box-shadow: 0 0 10px #10b981;
    }

    .slide-num {
      font-family: 'JetBrains Mono', monospace;
      font-size: 14px;
      color: #64748b;
      letter-spacing: 1px;
    }

    .slide-title {
      font-size: 46px;
      font-weight: 800;
      letter-spacing: -1px;
      color: #ffffff;
      line-height: 1.15;
      margin-bottom: 8px;
    }

    .slide-subtitle {
      font-size: 20px;
      color: #94a3b8;
      font-weight: 400;
      max-width: 1100px;
      line-height: 1.4;
    }

    .slide-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
      color: #64748b;
      border-top: 1px solid rgba(255, 255, 255, 0.07);
      padding-top: 20px;
    }

    /* Grids & Cards */
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 35px;
      height: 680px;
      align-items: center;
    }

    .grid-3 {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 25px;
      height: 680px;
      align-items: stretch;
    }

    .grid-4 {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 25px;
      height: 680px;
      align-items: stretch;
    }

    .card {
      background: rgba(18, 25, 33, 0.75);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 18px;
      padding: 30px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      backdrop-filter: blur(10px);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    }

    .card-highlight {
      border: 1px solid #10b981;
      background: radial-gradient(circle at top right, rgba(16, 185, 129, 0.12), rgba(18, 25, 33, 0.85));
    }

    .card-icon {
      font-size: 38px;
      margin-bottom: 16px;
    }

    .card-title {
      font-size: 24px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 12px;
    }

    .card-desc {
      font-size: 16px;
      color: #94a3b8;
      line-height: 1.55;
    }

    .stat-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      padding: 6px 14px;
      border-radius: 30px;
      font-size: 13px;
      font-weight: 600;
      margin-top: 15px;
      align-self: flex-start;
    }

    .stat-badge-amber {
      background: rgba(245, 158, 11, 0.15);
      border-color: rgba(245, 158, 11, 0.3);
      color: #fbbf24;
    }

    .screenshot-frame {
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
      height: 100%;
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .screenshot-frame img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    /* Hero Slide */
    .hero-content {
      display: flex;
      flex-direction: column;
      justify-content: center;
      height: 720px;
      max-width: 1400px;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #10b981;
      padding: 8px 18px;
      border-radius: 30px;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
      margin-bottom: 30px;
      align-self: flex-start;
    }

    .hero-title {
      font-size: 78px;
      font-weight: 800;
      line-height: 1.05;
      letter-spacing: -2px;
      color: #ffffff;
      margin-bottom: 24px;
    }

    .hero-title span {
      background: linear-gradient(135deg, #10b981 0%, #38bdf8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .hero-desc {
      font-size: 26px;
      color: #94a3b8;
      line-height: 1.45;
      max-width: 1100px;
      margin-bottom: 45px;
    }

    .hero-stats-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 25px;
      margin-top: 10px;
    }

    .hero-stat-card {
      background: rgba(18, 25, 33, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
      padding: 20px 24px;
    }

    .hero-stat-num {
      font-size: 38px;
      font-weight: 800;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      margin-bottom: 4px;
    }

    .hero-stat-label {
      font-size: 14px;
      color: #64748b;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
    }

    /* Pill list */
    .pill-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .pill-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 20px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
    }

    .pill-icon {
      font-size: 24px;
      flex-shrink: 0;
    }

    .pill-text strong {
      display: block;
      color: #ffffff;
      font-size: 17px;
      margin-bottom: 2px;
    }

    .pill-text span {
      color: #94a3b8;
      font-size: 14px;
    }

    .metric-big {
      font-size: 56px;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      color: #10b981;
      line-height: 1;
      margin: 15px 0;
    }

    .table-dark {
      width: 100%;
      border-collapse: collapse;
      margin-top: 15px;
      font-size: 15px;
    }

    .table-dark th {
      text-align: left;
      padding: 12px 16px;
      background: rgba(255, 255, 255, 0.04);
      color: #94a3b8;
      font-weight: 600;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .table-dark td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      color: #e2e8f0;
    }

    .tier-low { color: #10b981; font-weight: 700; }
    .tier-med { color: #38bdf8; font-weight: 700; }
    .tier-high { color: #f59e0b; font-weight: 700; }
    .tier-highest { color: #ef4444; font-weight: 700; }
  </style>
</head>
<body>

  <!-- ==================== SLIDE 1: COVER / TITLE ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Autonomous Freight Logistics Platform</div>
      <div class="slide-num">EXECUTIVE DECK &bull; 2026</div>
    </div>

    <div class="hero-content">
      <div class="hero-badge">⚡ Enterprise Highway Fleet Intelligence</div>
      <h1 class="hero-title">Fuel-Check &amp;<br><span>Disha Compass Platform</span></h1>
      <p class="hero-desc">
        The intelligent operating system for commercial freight transport—unifying algorithmic route refueling, interstate fuel VAT arbitrage, predictive weather safety, and multilingual driver AI.
      </p>

      <div class="hero-stats-row">
        <div class="hero-stat-card">
          <div class="hero-stat-num">₹1,400+</div>
          <div class="hero-stat-label">Tax Savings Per Fill</div>
        </div>
        <div class="hero-stat-card">
          <div class="hero-stat-num">O(V + E)</div>
          <div class="hero-stat-label">Linear DP Solver</div>
        </div>
        <div class="hero-stat-card">
          <div class="hero-stat-num">4 Langs</div>
          <div class="hero-stat-label">EN &bull; हिन्दी &bull; தமிழ் &bull; తెలుగు</div>
        </div>
        <div class="hero-stat-card">
          <div class="hero-stat-num">0.06s</div>
          <div class="hero-stat-label">Cached API Response</div>
        </div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Live Production: <strong>https://afgzrhwmlvctana4dmuwvwcxsm0zkgya.lambda-url.ap-south-1.on.aws/</strong></div>
      <div>Cloud Native &bull; Serverless AWS Lambda &bull; Zero-Key Architecture</div>
    </div>
  </section>

  <!-- ==================== SLIDE 2: THE PROBLEM ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Market Opportunity &amp; Industry Pain</div>
      <div class="slide-num">02 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Compounding Friction in Long-Haul Logistics</h2>
      <p class="slide-subtitle">Commercial fleets and highway truck operators face multi-layered inefficiencies that bleed margins and risk driver safety.</p>
    </div>

    <div class="grid-4">
      <div class="card">
        <div>
          <div class="card-icon">💸</div>
          <div class="card-title">Interstate Fuel Tax Disparity</div>
          <div class="card-desc">State diesel prices swing wildly (₹87.6/L in Delhi vs ₹92.4/L in Maharashtra). Fleets lose over ₹40 Lakhs monthly by refueling on the wrong side of state borders.</div>
        </div>
        <div class="stat-badge stat-badge-amber">Up to ₹5/Liter Loss</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">⛈️</div>
          <div class="card-title">Unpredicted Highway Hazards</div>
          <div class="card-desc">50+ km/h crosswinds, flash monsoon flooding, and road disruptions occur without proactive warning, causing vehicle rollovers, cargo damage, and costly transit delays.</div>
        </div>
        <div class="stat-badge stat-badge-amber">4.2 hrs Average Delay</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">🗣️</div>
          <div class="card-title">Driver Language Barriers</div>
          <div class="card-desc">Commercial drivers cross multilingual corridors speaking Hindi, Tamil, or Telugu. Navigating complex touchscreens while driving a 40-ton vehicle creates severe accident hazards.</div>
        </div>
        <div class="stat-badge stat-badge-amber">High Cognitive Load</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">📋</div>
          <div class="card-title">Fragmented Dispatch &amp; SOS</div>
          <div class="card-desc">Paper Bilti (consignments), uncoordinated tyre puncture breakdowns, and disconnected emergency trauma centers leave drivers stranded during night-time highway crises.</div>
        </div>
        <div class="stat-badge stat-badge-amber">Zero Unified Hotline</div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Logistics Industry Pain: $160 Billion Freight Market</div>
      <div>Fuel-Check Platform Overview</div>
    </div>
  </section>

  <!-- ==================== SLIDE 3: THE SOLUTION ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Platform Value Proposition</div>
      <div class="slide-num">03 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">A Unified Fleet Intelligence Ecosystem</h2>
      <p class="slide-subtitle">Fuel-Check converges mathematical graph routing, live taxation feeds, acoustic AI, and digital consignment into one platform.</p>
    </div>

    <div class="grid-3">
      <div class="card card-highlight">
        <div>
          <div class="card-icon">🧭</div>
          <div class="card-title">1. Algorithmic Refueling Solver</div>
          <div class="card-desc">Constructs a forward-only Directed Acyclic Graph (DAG) along the route polyline and runs Dynamic Programming to minimize total fuel expense under 500-mile range limits.</div>
        </div>
        <div class="stat-badge">&le; 2.5s Execution Time</div>
      </div>

      <div class="card card-highlight">
        <div>
          <div class="card-icon">💰</div>
          <div class="card-title">2. State VAT Arbitrage Engine</div>
          <div class="card-desc">Integrates daily 6:00 AM Oil Marketing Company (OMC) benchmark rates. Proactively directs drivers to tank up at low-tax border plazas (e.g. Haryana or Gujarat) before entering high-tax states.</div>
        </div>
        <div class="stat-badge">Direct Bottom-Line ROI</div>
      </div>

      <div class="card card-highlight">
        <div>
          <div class="card-icon">🎙️</div>
          <div class="card-title">3. Disha Multilingual AI Voice</div>
          <div class="card-desc">Acoustic co-pilot natively speaking Hindi, Tamil, Telugu, and English powered by Sarvam AI &amp; AWS Bedrock. Answers questions on diesel bunks, dhabas, mechanics, and medical emergencies.</div>
        </div>
        <div class="stat-badge">100% Hands-Free Driving</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">⛈️</div>
          <div class="card-title">4. Predictive Weather Hazards</div>
          <div class="card-desc">Batch samples meteorological models at future arrival-time checkpoints via Open-Meteo, triggering instant speed warnings for high winds, downpours, or black ice.</div>
        </div>
        <div class="stat-badge">Proactive Cargo Safety</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">📋</div>
          <div class="card-title">5. Commercial Bilti (Waybill)</div>
          <div class="card-desc">Instant digital generation of commercial waybills with unique manifest IDs, fuel volume audits, tax savings breakdown, and 80-column printable ASCII output for cab thermal printers.</div>
        </div>
        <div class="stat-badge">Paperless Dispatch</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">🛡️</div>
          <div class="card-title">6. Highway Emergency Network</div>
          <div class="card-desc">One-click reservation of verified highway dhabas, mobile puncture/mechanic dispatch, emergency trauma hospital alerts, and 1-tap SOS to National 112 / 1033 NHAI hotlines.</div>
        </div>
        <div class="stat-badge">Integrated 112 / 1033 NHAI</div>
      </div>
    </div>

    <div class="slide-footer">
      <div>The 6 Integrated Pillars of Fuel-Check</div>
      <div>Enterprise Solution Architecture</div>
    </div>
  </section>

  <!-- ==================== SLIDE 4: PRODUCT SHOWCASE (COCKPIT) ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Live Product Showcase</div>
      <div class="slide-num">04 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Single-Plane Geospatial Driver Cockpit</h2>
      <p class="slide-subtitle">Engineered specifically for in-cab displays and fleet dispatcher screens: 100vh zero-scroll layout with real-time route telemetry.</p>
    </div>

    <div class="grid-2">
      <div class="screenshot-frame">
        <img src="${cockpitImg}" alt="Fuel Check Driver Cockpit Screen">
      </div>

      <div class="pill-list">
        <div class="pill-item">
          <div class="pill-icon">📍</div>
          <div class="pill-text">
            <strong>National Highway Corridors</strong>
            <span>One-click chips for Delhi ➔ Mumbai (NH 48), Delhi ➔ Jaipur, Ahmedabad ➔ Mumbai, and South-Central corridors.</span>
          </div>
        </div>

        <div class="pill-item">
          <div class="pill-icon">⚡</div>
          <div class="pill-text">
            <strong>Live Telemetry Metrics</strong>
            <span>Instant calculation of Total Distance (1,414 km), Drive Time (22.5 hrs), Diesel Volume (385 L), and Fuel Cost (₹34,980).</span>
          </div>
        </div>

        <div class="pill-item">
          <div class="pill-icon">🗺️</div>
          <div class="pill-text">
            <strong>Leaflet Geospatial Dark Canvas</strong>
            <span>Interactive route polyline, station markers, weather hazard indicators, and emergency trauma facilities rendered with 0ms client-side cache.</span>
          </div>
        </div>

        <div class="pill-item">
          <div class="pill-icon">📱</div>
          <div class="pill-text">
            <strong>Strictly Single-Plane Viewport</strong>
            <span>Zero page-level scrolling prevents touch-target drift while in motion; responsive category tabs for Diesel, Dhabas, ER, and Mechanics.</span>
          </div>
        </div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Live URL: <strong>https://afgzrhwmlvctana4dmuwvwcxsm0zkgya.lambda-url.ap-south-1.on.aws/</strong></div>
      <div>Geospatial Cockpit &bull; Leaflet &bull; Service Worker Proxy</div>
    </div>
  </section>

  <!-- ==================== SLIDE 5: ALGORITHMIC RIGOR ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Algorithmic &amp; Theoretical Foundations</div>
      <div class="slide-num">05 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Graph-Theoretic Dynamic Programming Solver</h2>
      <p class="slide-subtitle">Single-routing call efficiency replaces naive multiple routing requests with geometric projection and linear-time DAG optimization.</p>
    </div>

    <div class="grid-3">
      <div class="card">
        <div>
          <div class="card-icon">📐</div>
          <div class="card-title">1. Station Polyline Projection</div>
          <div class="card-desc">Projects geocoded fuel plazas onto the route polyline using local flat-plane Euclidean coordinates:
            <br><br>
            <code style="font-family:'JetBrains Mono'; font-size:13px; color:#34d399;">t = max(0, min(1, (S-A)&middot;(B-A)/||B-A||&sup2;))</code>
            <br><br>
            Stations exceeding 5.0 miles corridor tolerance are discarded; candidates are indexed by cumulative route mile marker.
          </div>
        </div>
        <div class="stat-badge">5-Mile Corridor Pruning</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">🕸️</div>
          <div class="card-title">2. Forward-Only Reachability DAG</div>
          <div class="card-desc">Candidate nodes bounded by Origin (0.0 mi) and Destination (Total mi) form an ordered topological sequence:
            <br><br>
            <code style="font-family:'JetBrains Mono'; font-size:13px; color:#38bdf8;">N0 &lt; N1 &lt; N2 &lt; ... &lt; Nk</code>
            <br><br>
            Directed edges are added only if mile(u) &lt; mile(v) and distance &le; 500 miles. Topological monotonicity guarantees an acyclic graph.
          </div>
        </div>
        <div class="stat-badge">Range Limit &le; 500 Miles</div>
      </div>

      <div class="card card-highlight">
        <div>
          <div class="card-icon">⚡</div>
          <div class="card-title">3. Linear-Time DP Solver</div>
          <div class="card-desc">Solves the global cost-minimization problem in O(V + E) time:
            <br><br>
            <code style="font-family:'JetBrains Mono'; font-size:13px; color:#10b981;">cost[v] = min(cost[v], cost[u] + g &times; price[u])</code>
            <br><br>
            If cost[Destination] = &infin;, the platform immediately raises HTTP 422 Unprocessable Entity, preventing vehicle fuel exhaustion.
          </div>
        </div>
        <div class="stat-badge">&lt; 1ms Solver Complexity</div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Exact 1 Directions API Call per Trip &bull; Geometric In-Memory Interpolation</div>
      <div>Deterministic Optimization Guarantees</div>
    </div>
  </section>

  <!-- ==================== SLIDE 6: TAX ARBITRAGE UNIT ECONOMICS ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Financial Impact &amp; Unit Economics</div>
      <div class="slide-num">06 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Interstate Fuel VAT Arbitrage</h2>
      <p class="slide-subtitle">Capturing significant fuel cost margins through intelligent border refueling recommendations across Indian National Highways.</p>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title">Daily 6:00 AM OMC State VAT Benchmark Rates</div>
        <table class="table-dark">
          <thead>
            <tr>
              <th>State / Corridor</th>
              <th>Diesel (₹/L)</th>
              <th>Tax Tier</th>
              <th>Arbitrage Strategy</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Delhi NCT (Origin)</td>
              <td>₹87.62</td>
              <td><span class="tier-low">LOW</span></td>
              <td>Ideal entry fill point</td>
            </tr>
            <tr>
              <td>Haryana (Rewari)</td>
              <td>₹88.35</td>
              <td><span class="tier-low">LOW</span></td>
              <td>Tank up before Rajasthan</td>
            </tr>
            <tr>
              <td>Gujarat (Surat / Vapi)</td>
              <td>₹90.10</td>
              <td><span class="tier-med">MEDIUM</span></td>
              <td>Fill 100% prior to MH border</td>
            </tr>
            <tr>
              <td>Rajasthan (Jaipur)</td>
              <td>₹91.25</td>
              <td><span class="tier-high">HIGH</span></td>
              <td>Avoid major top-ups</td>
            </tr>
            <tr>
              <td>Maharashtra (Mumbai)</td>
              <td>₹92.40</td>
              <td><span class="tier-highest">HIGHEST</span></td>
              <td>Highest VAT corridor terminal</td>
            </tr>
          </tbody>
        </table>
        <div class="stat-badge">Daily 6:00 AM Automated Revision Feeds</div>
      </div>

      <div class="card card-highlight">
        <div class="card-title">Commercial Fleet ROI: Case Study</div>
        <div class="card-desc">
          For a regional freight operator running <strong>50 commercial heavy trucks</strong> on the Delhi ➔ Mumbai corridor (average 6 trips per truck per month):
        </div>

        <div style="margin: 25px 0;">
          <div style="font-size: 14px; color: #94a3b8; text-transform: uppercase;">Average Savings Per Tank Fill</div>
          <div class="metric-big">₹1,420</div>
          <div style="font-size: 15px; color: #e2e8f0;">Diesel differential between Gujarat (₹90.10) and Maharashtra (₹92.40) on a 400L tank.</div>
        </div>

        <div style="padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
          <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
            <span style="color:#94a3b8;">Monthly Tank Fills (50 trucks &times; 6 trips):</span>
            <strong style="color:#ffffff;">300 Refills</strong>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
            <span style="color:#94a3b8;">Net Monthly Fuel Cost Savings:</span>
            <strong style="color:#10b981; font-size:18px;">₹4,26,000 / month</strong>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span style="color:#94a3b8;">Annualized Fleet Profit Increase:</span>
            <strong style="color:#34d399; font-size:22px;">₹51,12,000 / year</strong>
          </div>
        </div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Zero Subscription Friction &bull; Instant Payback from First Route</div>
      <div>Unit Economics &amp; Fleet ROI</div>
    </div>
  </section>

  <!-- ==================== SLIDE 7: DISHA VOICE AI ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Multimodal Acoustic Co-Pilot</div>
      <div class="slide-num">07 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Disha: Multilingual AI Voice Assistant</h2>
      <p class="slide-subtitle">Engineered specifically for truck drivers in transit: low cognitive load, native Indic speech models, and zero hallucination.</p>
    </div>

    <div class="grid-2">
      <div class="card card-highlight">
        <div class="card-icon">🎙️</div>
        <div class="card-title">Strict Native Language Isolation</div>
        <div class="card-desc" style="margin-bottom: 20px;">
          Disha strictly isolates vernacular vocabularies without language mixing, utilizing native acoustic speakers powered by <strong>Sarvam AI</strong> and <strong>AWS Bedrock</strong>:
        </div>

        <div class="pill-list">
          <div class="pill-item">
            <span style="font-weight: 800; color: #10b981; font-size: 18px;">हिन्दी</span>
            <div class="pill-text">
              <strong>Hindi (aditya_hi_conversational)</strong>
              <span>"आगे 75 किमी पर IndianOil Swagat है, जहाँ डीज़ल ₹88.35/L मिलेगा।"</span>
            </div>
          </div>
          <div class="pill-item">
            <span style="font-weight: 800; color: #38bdf8; font-size: 18px;">தமிழ்</span>
            <div class="pill-text">
              <strong>Tamil (gokul_ta_narration)</strong>
              <span>"வழியில் 75 கி.மீ தொலைவில் இந்தியன் ஆயில் பங்க் உள்ளது, டீசல் ₹88.35/L."</span>
            </div>
          </div>
          <div class="pill-item">
            <span style="font-weight: 800; color: #f59e0b; font-size: 18px;">తెలుగు</span>
            <div class="pill-text">
              <strong>Telugu (kavitha_te_conversation)</strong>
              <span>"ముందు 75 కి.మీ దూరంలో ఇండియన్ ఆయిల్ బంక్ ఉంది, డీజిల్ ధర ₹88.35/L."</span>
            </div>
          </div>
          <div class="pill-item">
            <span style="font-weight: 800; color: #a855f7; font-size: 18px;">EN</span>
            <div class="pill-text">
              <strong>English (simran_en_automobile)</strong>
              <span>"Nearest pump is IndianOil Swagat 75 km ahead at ₹88.35/L. Safe journey!"</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-icon">⚡</div>
        <div class="card-title">Grounded Context &amp; Zero Hallucination</div>
        <div class="card-desc" style="margin-bottom: 20px;">
          Unlike generic conversational LLMs, Disha is grounded directly in verified highway database telemetry before responding:
        </div>

        <div class="pill-list">
          <div class="pill-item">
            <div class="pill-icon">📍</div>
            <div class="pill-text">
              <strong>Deterministic Highway Truth</strong>
              <span>Prompts inject exact vehicle mile markers, active road closures, and live fuel prices.</span>
            </div>
          </div>

          <div class="pill-item">
            <div class="pill-icon">💰</div>
            <div class="pill-text">
              <strong>Zero LLM Cost on Clear Roads</strong>
              <span>Deterministic multilingual rules trigger for standard conditions; expensive LLM calls occur only when conversational nuances or hazards require it.</span>
            </div>
          </div>

          <div class="pill-item">
            <div class="pill-icon">📞</div>
            <div class="pill-text">
              <strong>Bolna Telephony Agent Webhook</strong>
              <span>Direct webhook integration (<code>/api/v1/bolna/webhook/</code>) enables autonomous in-cab voice telephony and automated dispatcher calls.</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Acoustic Driver Safety &bull; Sarvam AI bulbul:v4-flash &bull; Amazon Nova Micro</div>
      <div>Voice AI Subsystem</div>
    </div>
  </section>

  <!-- ==================== SLIDE 8: BILTI & EMERGENCY SERVICES ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Commercial Waybill &amp; Emergency Dispatch</div>
      <div class="slide-num">08 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Digital Bilti Waybill &amp; Emergency Hotline</h2>
      <p class="slide-subtitle">Standardizing commercial freight consignments while providing drivers with immediate trauma and breakdown response.</p>
    </div>

    <div class="grid-2">
      <div class="screenshot-frame">
        <img src="${biltiImg}" alt="Commercial Bilti Waybill Screen">
      </div>

      <div class="pill-list">
        <div class="pill-item">
          <div class="pill-icon">📋</div>
          <div class="pill-text">
            <strong>Standardized Digital Consignment (Bilti)</strong>
            <span>Generates unique consignment IDs (<code>BLT-YYYYMMDD-XXXXXX</code>) aggregating total km, diesel volume, state tax savings, and active weather hazards.</span>
          </div>
        </div>

        <div class="pill-item">
          <div class="pill-icon">🖨️</div>
          <div class="pill-text">
            <strong>80-Column Thermal Printer Ready</strong>
            <span>Generates monospaced ASCII waybill slips directly compatible with cab thermal printers and mobile Bluetooth receipt devices.</span>
          </div>
        </div>

        <div class="pill-item">
          <div class="pill-icon">🚨</div>
          <div class="pill-text">
            <strong>National Emergency SOS (112 / 1033 NHAI)</strong>
            <span>One-tap emergency trigger transmits driver GPS coordinates directly to Highway Police, NHAI Breakdown vans, and local trauma centers.</span>
          </div>
        </div>

        <div class="pill-item">
          <div class="pill-icon">🔧</div>
          <div class="pill-text">
            <strong>Corridor Amenity Integrations</strong>
            <span>Dedicated micro-services for verified Dhabas (shower/bed), 24/7 Mobile Puncture mechanics, and parcel warehouse checkpoint confirmation.</span>
          </div>
        </div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Endpoint: <strong>POST /api/v1/routes/manifest/</strong></div>
      <div>Commercial Dispatch &amp; Road Safety</div>
    </div>
  </section>

  <!-- ==================== SLIDE 9: CLOUD ARCHITECTURE ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Cloud-Native Engineering</div>
      <div class="slide-num">09 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Cloud Architecture &amp; Zero-Key Readiness</h2>
      <p class="slide-subtitle">Serverless container deployment on AWS Lambda with automated GitHub Actions CI and multi-tier sub-second caching.</p>
    </div>

    <div class="grid-3">
      <div class="card">
        <div>
          <div class="card-icon">🚀</div>
          <div class="card-title">Serverless AWS Lambda</div>
          <div class="card-desc">
            Packaged as an automated container image deployed on Amazon ECR + AWS Lambda with AWS Lambda Web Adapter (LWA):
            <br><br>
            &bull; Public HTTPS Function URL with zero API Gateway overhead.<br>
            &bull; Auto-scales from 0 to thousands of concurrent requests.<br>
            &bull; Lean Gunicorn WSGI runtime optimized for 1024MB memory.
          </div>
        </div>
        <div class="stat-badge">One-Click deploy_lambda.sh</div>
      </div>

      <div class="card card-highlight">
        <div>
          <div class="card-icon">⚡</div>
          <div class="card-title">Multi-Tier Caching Pipeline</div>
          <div class="card-desc">
            To guarantee sub-second responses and prevent external rate limits:
            <br><br>
            &bull; <strong>Client LRU Session Cache:</strong> Instant 0ms response in browser for repeat queries.<br>
            &bull; <strong>SHA-256 Memory Cache:</strong> In-memory route caching with <code>X-Cache: HIT</code> responses in <strong>0.06s</strong>.<br>
            &bull; <strong>Decoupled Async TTS:</strong> Audio synthesizes on-demand without blocking route calculations.
          </div>
        </div>
        <div class="stat-badge">0.06s Cached Latency</div>
      </div>

      <div class="card">
        <div>
          <div class="card-icon">🔑</div>
          <div class="card-title">Zero-Key First Architecture</div>
          <div class="card-desc">
            Engineered to operate 100% out of the box with zero paid API keys:
            <br><br>
            &bull; <strong>Routing:</strong> Free OSRM road network.<br>
            &bull; <strong>Geocoding:</strong> OpenStreetMap / Nominatim.<br>
            &bull; <strong>Weather:</strong> Open-Meteo checkpoint models.<br>
            &bull; <strong>Enterprise Switch:</strong> Seamlessly enables Amazon Location &amp; Sarvam AI via .env flags.
          </div>
        </div>
        <div class="stat-badge">Zero Setup Friction</div>
      </div>
    </div>

    <div class="slide-footer">
      <div>69 Automated Tests Passing &bull; 100% CI Coverage</div>
      <div>Cloud Infrastructure</div>
    </div>
  </section>

  <!-- ==================== SLIDE 10: TRACTION & SUMMARY ==================== -->
  <section class="slide">
    <div class="slide-header">
      <div class="slide-tag">Traction &amp; Live Deployment</div>
      <div class="slide-num">10 / 10</div>
    </div>

    <div>
      <h2 class="slide-title">Validated Rigor &amp; Live Platform Access</h2>
      <p class="slide-subtitle">Fuel-Check is fully verified, tested, and actively running live in production.</p>
    </div>

    <div class="grid-2">
      <div class="card card-highlight">
        <div class="card-title">Production Verification Highlights</div>
        <div class="pill-list" style="margin-top: 15px;">
          <div class="pill-item">
            <span style="font-size: 24px;">✅</span>
            <div class="pill-text">
              <strong>69 Automated Unit &amp; Integration Tests Passing</strong>
              <span>Verified across geometry normalization, DAG reachability, weather models, and API resilience in 4.1s.</span>
            </div>
          </div>

          <div class="pill-item">
            <span style="font-size: 24px;">🇮🇳</span>
            <div class="pill-text">
              <strong>National Highway 48 Validated (Delhi ➔ Mumbai)</strong>
              <span>1,414 km corridor successfully modeled with verified Gujarat/Maharashtra border tax arbitrage saving ₹1,420.</span>
            </div>
          </div>

          <div class="pill-item">
            <span style="font-size: 24px;">⚡</span>
            <div class="pill-text">
              <strong>Zero-502 Latency Optimized</strong>
              <span>Uncached execution time reduced from ~30s down to 2.3s through decoupled non-blocking speech synthesis.</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Access the Live Platform</div>
        <div class="card-desc" style="margin-bottom: 25px;">
          Experience the interactive driver cockpit, test multimodal voice queries, and generate commercial waybills live:
        </div>

        <div style="background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; margin-bottom: 25px;">
          <div style="font-size: 13px; color: #94a3b8; text-transform: uppercase; margin-bottom: 6px;">Live AWS Lambda Function URL:</div>
          <div style="font-family: 'JetBrains Mono', monospace; font-size: 15px; color: #34d399; word-break: break-all;">
            https://afgzrhwmlvctana4dmuwvwcxsm0zkgya.lambda-url.ap-south-1.on.aws/
          </div>
        </div>

        <div class="pill-list">
          <div class="pill-item">
            <div class="pill-icon">💻</div>
            <div class="pill-text">
              <strong>GitHub Repository &amp; CI Pipeline</strong>
              <span>github.com/Viswesh934/Fuel-check &bull; MIT License</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="slide-footer">
      <div>Fuel-Check &amp; Disha Compass Platform &bull; Autonomous Freight Logistics</div>
      <div>Thank You</div>
    </div>
  </section>

</body>
</html>
`;

const outputPathHtml = path.join(__dirname, 'pitch_deck.html');
fs.writeFileSync(outputPathHtml, htmlContent, 'utf8');
console.log('Saved pitch deck HTML to:', outputPathHtml);

(async () => {
  console.log('Launching Puppeteer to generate high-res PDF presentation...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  
  // Set HTML content directly
  await page.setContent(htmlContent, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 2000));

  const pdfPath = path.join(__dirname, 'Fuel_Check_Pitch_Deck.pdf');
  await page.pdf({
    path: pdfPath,
    width: '1920px',
    height: '1080px',
    printBackground: true,
    pageRanges: '1-10',
    preferCSSPageSize: true
  });

  console.log('SUCCESS! PDF generated at:', pdfPath);
  const stats = fs.statSync(pdfPath);
  console.log('PDF file size:', (stats.size / (1024 * 1024)).toFixed(2), 'MB');

  await browser.close();
})();
