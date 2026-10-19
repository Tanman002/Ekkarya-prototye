# Ekकार्य — Cooperative Gig Services Platform

**SIH 2026 · PS 26089 · Ministry of Cooperation / NCCT · Team COGNITO**

A worker-owned cooperative platform for household and community services. This repo is a fully working,
mobile-first web prototype built in Streamlit. It includes a customer app, a worker app, a cooperative manager
dashboard, a federation/Ministry dashboard, AI demand forecasting and workforce allocation.

---

## 1. Run it locally (5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. On first start the app generates six months of synthetic data (~8 s) and trains the
forecast model (~5 s). After that, pages load instantly.

## 2. Deploy free on Streamlit Community Cloud

1. Create a **public GitHub repo** (e.g. `ekkarya-prototype`) and upload everything in this folder, keeping the
   folder structure, including the hidden `.streamlit/` folder.
2. Go to **share.streamlit.io** → sign in with GitHub → **Create app** → pick the repo, branch `main`, main file
   `app.py`. Under **Advanced settings**, choose Python 3.11 or 3.12.
3. (Optional) In **App settings → Secrets**, paste the keys from `.streamlit/secrets.toml.example` to switch on
   AI text/photo understanding (Gemini) and voice transcription (Groq). Both have free tiers. Without keys the app
   uses its built-in rule-based interpreter.
4. Click **Deploy**. You get a public URL like `https://ekkarya.streamlit.app`.

**Backup mirror:** create a Hugging Face Space (SDK: Streamlit), upload the same files and set `app.py` as the
entry point.

**Before every demo:** open the app 10 minutes early (free apps sleep after inactivity), press
**Demo controls → Reset demo data**, run the full flow once, and keep a screen recording as a backup.

## 3. Demo accounts and controls

| Role | How to open |
|---|---|
| Customer — Priya Sharma, Mira Road East | Login → Customer → any 4-digit OTP |
| Worker — Ramesh Patil, electrician + plumber | Login → Worker → any 4-digit OTP |
| New worker onboarding | Login → Worker → **Join a cooperative** (demo e-Shram UAN **1002 0030 0400**) |
| Cooperative manager — Mira–Bhayandar Seva Sahakari | Login → Cooperative manager |
| Federation / Ministry admin | Login → Federation / Ministry admin |

The sidebar (» at top-left) has **🎬 Demo controls**: one-click role switching, the five scenarios below,
"next payment fails", and **Reset demo data**.

| Scenario | What it sets up |
|---|---|
| Normal booking | Ramesh becomes the best-matched electrician near Priya. Book Electrical → Fan repair → Now. |
| Emergency booking | Only Ramesh and two simulated plumbers are online within 3 km. Tap Emergency → Plumbing. Ramesh has 15 s to accept before a simulated worker does. |
| No worker found | All carpenters go offline. Book Carpentry to show the fallback. |
| Monsoon demand spike | Heavy-rain alert: plumbing and electrical forecast ×1.8 for 3 days. See Forecast and Allocation. |
| Complaint escalation | Adds a price-dispute complaint escalated from the cooperative to the federation. |

**Two-tab live demo:** open the customer in one browser window and the worker in another (or on a phone). They
share the same database, and the worker's job list refreshes every 3 seconds.

## 4. Suggested 4-minute demo script

1. **Worker onboarding (40 s):** Join a cooperative in Marathi → verify e-Shram UAN → e-KYC → skills → insurance
   opt-in. Switch to Manager → Verification → Approve.
2. **Emergency booking (60 s):** Run the *Emergency* scenario. Customer (Hindi) types "पाइप फट गया" → AI
   picks Plumbing · Burst pipe · Urgent → alert nearby workers. Worker tab lights up → Accept → live map and ETA.
3. **Completion and payment (40 s):** Worker enters the start code, adds an extra item, and the customer approves
   it. The worker marks the job complete, then the customer pays by UPI, downloads the GST invoice PDF and rates the
   worker. The worker sees the payment split.
4. **Federation (50 s):** Run *Monsoon demand spike* → Forecast heatmap → Allocation → Notify workers → the
   notification appears in the worker app. Show Impact (worker share of revenue, work-distribution Gini).

## 5. What maps to the problem statement

| PS expected feature | Where it is |
|---|---|
| Service provider registration and verification | Worker → Join a cooperative; Manager → Verification |
| Worker skill profiling and certification | Onboarding skills step, certificate upload, Manager → Approve certificate, Worker → Profile |
| Customer booking and scheduling | Customer → service tiles → Now / Schedule (date + time block) |
| Geo-location based service matching | `core/matching.py` — distance, rating, certification and fair-rotation score; "Why this worker?" |
| Digital payments and invoicing | UPI app / UPI QR (mock), success/failure states, GST invoice PDF, payment split |
| Rating and feedback | Two-way star rating, tags, comment, complaints → cooperative → federation |
| Worker welfare and insurance | Worker → Welfare: e-Shram schemes, group accident cover, per-job premium |
| Emergency and on-demand booking | Emergency button → radius broadcast 3 → 6 → 10 km, fixed fee, no surge |
| Cooperative federation dashboard | Manager dashboard + Federation overview, impact and reports |
| Multilingual mobile application | English / हिंदी / मराठी across customer and worker apps; phone-frame layout |
| AI demand forecasting and workforce allocation | Forecast (gradient boosting, back-test, drivers), Allocation (gaps, moves, notify) |
| e-Shram integration | Onboarding UAN verification, Welfare tab schemes, Manager → Sync engaged-worker data |

## 6. Architecture

```
Browser (customer / worker phone view · manager & federation desktop view)
        │
Streamlit app (app.py → views/*)
        │  UI only — every rule lives in core/
core/  matching · engine (booking lifecycle + simulation) · pricing · forecast · allocation
       eshram_client · ai_assist · routing · copilot · scenarios · i18n · invoice · ui
        │
SQLite (data/ekkarya.db, rebuilt from data/seed.db) ── swap for Supabase/Postgres in production
        │
External (optional): OpenStreetMap tiles · OSRM routing · Gemini (text/photo) · Groq Whisper (voice)
                     e-Shram connector in sandbox mode, on the aggregator API contract
```

- **Matching** is deterministic and explainable: `0.40 × proximity + 0.25 × rating + 0.15 × certification +
  0.20 × fair rotation`.
- **AI stays at the edges**: it interprets customer input and forecasts demand. Prices, matching and allocation are
  formulas, so they can't hallucinate.
- **e-Shram**: `core/eshram_client.py` implements UAN lookup, scheme status and engaged-worker submission.
  `MODE = "sandbox"` runs against a simulated registry built on the same contract. Production swaps in live
  aggregator credentials by changing only that file.
- All business placeholders (prices, 8% cooperative charge, ₹8 welfare premium, aggregator benchmark, festival
  dates) are in `core/config.py`.

## 7. Folder structure

```
app.py                     entry: login, roles, navigation
core/                      business logic (no UI)
views/                     screens: login, customer, worker, coop, federation, maps, analytics, common
data/generate_data.py      seeded synthetic data (340 workers, 800 customers, 6 months of demand)
data/build_lang.py         source of all UI strings → data/lang/{en,hi,mr}.json
assets/                    logo
.streamlit/config.toml     green · white · orange theme
requirements.txt
```

## 8. Honest limitations (say these before the judges do)

- All data is synthetic, and forecast accuracy shows that the pipeline works, not that it predicts real demand.
- Payments, e-KYC, insurance and the e-Shram connection run in sandbox or simulated mode.
- It's a responsive web app styled as a mobile app; a native Android app is on the roadmap.
- Hindi and Marathi strings need review by a native speaker (edit `data/build_lang.py`, then run it).
