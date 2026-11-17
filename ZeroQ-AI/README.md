# ZeroQ AI — Predictive Quality Intelligence & Zero Customer Complaint Platform

ZeroQ AI is an end-to-end manufacturing quality intelligence platform designed for ABT-CPD. It integrates a 19-year manufacturing quality dataset (2008–2026) spanning 24,000 production batches, 37,245 quality inspections, 6,000 complaints, 4,000 investigations, and 3,500 corrective actions with a production-grade XGBoost binary classifier (10,038 transformed features) to predict 90-day post-dispatch customer complaint risk before batches leave the facility.

---

## 1. Key Features

- **Real Manufacturing Dataset (Zero Mock Data)**: All 10 cleaned datasets from the ML workspace imported idempotently into the database with 100% relational integrity and SHA-256 validation.
- **Calibrated XGBoost Model Serving**: Cached singleton service loading `final_xgboost_model.joblib`, `preprocessor.joblib`, and `final_threshold.joblib` (0.325).
- **Train/Serve Skew Elimination**: Verified 0.000000 maximum probability divergence between offline test set predictions and real-time inference.
- **Conversational NLP Query Pipeline**: Free-text query parsing extracting products, facilities, shifts, telemetry (temperature, humidity, pressure), and deviation flags; automatically applying documented defaults and persisting predictions to the database.
- **Dual User Experiences**:
  - **Customer Portal**: File quality complaints, real-time ticket tracking, profile management, and an interactive **AI Risk Predictor** with persistent query history.
  - **Admin Quality Intelligence Portal**: Executive dashboard, 19-year complaint analytics, root cause analysis (RCA), CAPA workflow tracker, risk matrix, and AI Prediction Center.

---

## 2. Technology Stack

- **Frontend**: React 18, Vite, Tailwind CSS, Recharts, Lucide-React, Axios, React Router v6.
- **Backend**: FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2, Python-Jose (JWT), Passlib/Bcrypt.
- **Database**: PostgreSQL (primary on port 5432) with automated SQLite fallback (`zeroq_ai.db`).
- **Machine Learning**: XGBoost 3.2.0, Scikit-Learn 1.7.2, Joblib 1.5.3, Pandas 2.3.3, NumPy 2.2.6.
- **NLP**: Rule-based regex + domain taxonomy entity extractor (zero external API dependency).

---

## 3. Directory Layout

```
C:\Projects\ZeroQ-AI\
├── Model\                         # ML Workspace
│   ├── raw_data\                  # Raw CSV files
│   ├── processed_data\            # Cleaned CSV files (10 tables)
│   ├── feature_engineered_data\   # Pre-dispatch batch features (24,000 rows)
│   ├── model_ready_data\          # preprocessor.joblib, train/test raw splits
│   ├── model_training\            # XGBoost training artifacts & metrics
│   └── preprocessing\             # 10 data engineering notebooks
├── ZeroQ-AI\                      # Application Project Root
│   ├── backend\
│   │   ├── app\
│   │   │   ├── api\               # Auth, Complaints, Admin, Customer, Predictions
│   │   │   ├── core\              # Config, Security, JWT dependencies
│   │   │   ├── database\          # Connection & SQLAlchemy base
│   │   │   ├── ml\                # model_service.py & nlp_parser.py
│   │   │   ├── models\            # Database ORM models
│   │   │   └── schemas\           # Pydantic validation schemas
│   │   └── requirements.txt
│   ├── frontend\                  # React + Vite application
│   │   ├── src\
│   │   │   ├── pages\             # Admin & Customer pages
│   │   │   └── layouts\           # AdminLayout & CustomerLayout
│   ├── models\trained\            # final_xgboost_model.joblib
│   ├── scripts\
│   │   ├── import_dataset.py      # Idempotent database seeder
│   │   ├── initialize_database.py # Database table & index initializer
│   │   └── create_demo_users.py   # Demo credential configurator
│   └── tests\                     # Pytest suite (28 test cases)
├── PLAN.md                        # Master implementation plan
└── CHANGELOG.md                   # Mock removal and fix log
```

---

## 4. Setup & Installation

### 4.1 Prerequisites
- Python 3.10+
- Node.js v18+ & npm
- PostgreSQL (optional, port 5432; SQLite is used automatically as fallback)

### 4.2 Backend Setup
```bash
cd C:\Projects\ZeroQ-AI\ZeroQ-AI\backend
pip install -r requirements.txt
```

### 4.3 Database Initialization & Real Dataset Import
Run the idempotent dataset importer to load all 10 real tables from `Model/processed_data`:
```bash
cd C:\Projects\ZeroQ-AI\ZeroQ-AI
python scripts/import_dataset.py
```
This loads:
- 20 Products
- 5 Facilities
- 15 Production Lines
- 40 Materials
- 500 Customers
- 24,000 Production Batches
- 37,245 Quality Inspections
- 6,000 Complaints
- 4,000 Investigations
- 3,500 Corrective Actions
- Demo Users (Admin & Customer)

### 4.4 Frontend Setup
```bash
cd C:\Projects\ZeroQ-AI\ZeroQ-AI\frontend
npm install
npm run build
```

---

## 5. Running the Application

### Start the Backend (Terminal 1)
```bash
cd C:\Projects\ZeroQ-AI\ZeroQ-AI\backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation is available at: `http://127.0.0.1:8000/api/docs`

### Start the Frontend (Terminal 2)
```bash
cd C:\Projects\ZeroQ-AI\ZeroQ-AI\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
Open `http://127.0.0.1:5173/` in your browser.

---

## 6. Demo Credentials

| Role | Email | Password | Access |
|---|---|---|---|
| **Quality Admin** | `admin@zeroq.com` | `AdminZeroQ2024!` | Executive Dashboard, Analytics, RCA, CAPA, AI Center |
| **Customer Portal** | `demo@customer.com` | `DemoCustomer2024!` | Complaints, Tracking, AI Quality Predictor, History |

---

## 7. Testing & Verification

Run the comprehensive pytest suite covering unit tests, API tests, train/serve skew verification, database filter validation, and end-to-end Playwright tests:
```bash
pytest C:\Projects\ZeroQ-AI\ZeroQ-AI\tests -v
```
*(All 29 tests pass in ~8.4s).*

### Standalone End-to-End Browser Test (Playwright):
```bash
python C:\Projects\ZeroQ-AI\ZeroQ-AI\tests\test_e2e_playwright.py
```
*(Executes complete 10-step customer and admin journey, capturing screenshots in `tests/screenshots/` with 0 console errors).*

### Key Test Validations:
- **`test_train_serve_skew_reproduction`**: Re-evaluates 3,571 test batches and asserts max probability difference is 0.000000 against offline saved model outputs.
- **`test_filter_combinations_match_db_queries_100_percent`**: Validates 10 filter permutations against direct database SQL queries with 100% agreement.
- **`test_evaluate_nlp_query`**: Validates natural language query entity parsing, default substitution, and XGBoost probability prediction.
- **`test_full_application_e2e`**: Automated Playwright test verifying login, NLP query submission, prediction display & persistence, complaint filing, tracking, customer list, admin dashboard KPIs, and AI prediction center.
