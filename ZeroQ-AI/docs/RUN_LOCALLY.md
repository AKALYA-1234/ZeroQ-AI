# Run ZeroQ AI on your laptop

This guide gets ZeroQ AI running on your own computer in about 20 minutes, most of it spent waiting for installs. You don't need a database server, Docker or any API key. The app comes with its own sample database file.

## What you need

| Tool | Version | Check with |
|---|---|---|
| Git | any | `git --version` |
| Python | 3.13 (tested) | `python --version` |
| Node.js | 18 or newer (tested on 23) | `node --version` |

On Windows, use **PowerShell**. On macOS or Linux, use **Terminal**. When the two differ, the commands below show both.

## 1. Download the code

```bash
git clone https://github.com/AKALYA-1234/ZeroQ-AI.git
cd ZeroQ-AI/ZeroQ-AI
```

The folder really is nested (`ZeroQ-AI/ZeroQ-AI`). Run every command below from this inner folder unless a step says otherwise.

## 2. Install the backend (one time)

Create a private Python environment so nothing touches your system Python:

**Windows**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

The install takes **5–15 minutes**, because pandas, scikit-learn and xgboost are large. Your prompt starts with `(.venv)` while the environment is active.

If PowerShell says *"running scripts is disabled"*, run this once and then activate again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 3. Point the backend at the bundled database (one time)

Create a file called `.env` inside the `backend` folder that contains this one line:

```
DATABASE_URL=sqlite:///./zeroq_ai.db
```

**Windows**
```powershell
Set-Content -Path backend\.env -Value "DATABASE_URL=sqlite:///./zeroq_ai.db" -Encoding ascii
```

**macOS / Linux**
```bash
echo "DATABASE_URL=sqlite:///./zeroq_ai.db" > backend/.env
```

This uses `backend/zeroq_ai.db`, which already holds about 6,000 sample complaints and the demo accounts. `.env` files are ignored by git, so this one is never uploaded.

## 4. Install the frontend (one time)

```bash
cd frontend
npm ci
cd ..
```

This takes under a minute.

## 5. Start the app (every time)

You need **two terminals** open at the same time.

**Terminal 1 (backend):**

```powershell
# Windows
cd ZeroQ-AI\ZeroQ-AI
.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
```bash
# macOS / Linux
cd ZeroQ-AI/ZeroQ-AI
source .venv/bin/activate
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend is ready when it prints `Application startup complete`.

**Terminal 2 (frontend):**

```bash
cd ZeroQ-AI/ZeroQ-AI/frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

To stop the app, press `Ctrl + C` in both terminals.

## 6. Log in

| Role | Email | Password |
|---|---|---|
| Customer | `demo@customer.com` | `DemoCustomer2024!` |
| Admin | `admin@zeroq.com` | `AdminZeroQ2024!` |

To see both sides at once, log in as the customer in a normal window and as the admin in a private or incognito window.

## 7. Try it out: one complaint, start to finish

1. **As the customer**, open **Submit Complaint** and fill in the form:
   - **Product:** Salted Snacks
   - **Batch ID:** `BAT000123`
   - **Title:** `Packets leaking and snacks soggy`
   - **Description:** `Two packets were torn at the side seal and the snacks inside were soft and soggy, with a stale smell.`
   - **Category and Severity:** leave as "Not sure — let AI …"

   Submit the form and write down the complaint ID (for example `CMP006002`).
2. **As the admin**, open **Complaint Management** and search for that ID. The **AI Verification & Resolution** tab shows the predicted issue, the probable root cause, similar past incidents and a recommended fix.

   The first complaint after a fresh install takes a few seconds longer, because the app trains its issue classifier at that point. Later complaints are quick.
3. **Keep the customer's Track Complaint page open.** As the admin, go to **Verify & Resolve**:
   1. Confirm or correct the category and the root cause.
   2. Write a short explanation for the customer.
   3. Click **Mark resolved & notify customer**.

   The customer's page updates within a few seconds.
4. **Try other languages.** The app understands Tamil-English and Hindi-English mixes:
   - `Packet open panna ulla chinna poochi irundhuchu` (insects inside the packet)
   - `Packet pe 500g likha hai lekin sirf 420g nikla` (packet says 500 g, but only 420 g)

The demo customer counts as a **test account**, so its complaints are tagged **TEST** and kept out of the real-world accuracy figures on **Model Monitoring**. When that page shows "insufficient data", that's expected.

## 8. Optional: turn on the LLM

Without an API key, the app uses its own ML model plus rule-based fallbacks, and everything above works. To also let a large language model help with unclear or mixed-language complaints:

1. Get a free key at https://console.groq.com/keys.
2. Add this line to `backend/.env`:
   ```
   GROQ_API_KEY=your-key-here
   ```
3. Restart the backend.

Never commit this file or share your key. If the LLM is down or the key is wrong, the complaint is still saved and the app falls back to its own model. It never makes up an answer.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uvicorn is not recognized` | Use `python -m uvicorn ...` exactly as shown, with `(.venv)` active |
| `No module named ...` | The virtual environment isn't active. Run the activate command from step 2 again |
| `Address already in use` / port 8000 or 5173 busy | Close the other program using that port, or start the backend with `--port 8001` and the frontend with `$env:VITE_API_TARGET="http://localhost:8001"; npm run dev` (Windows) or `VITE_API_TARGET=http://localhost:8001 npm run dev` (macOS/Linux) |
| Login fails or the page shows network errors | Check that Terminal 1 (backend) is still running and has no red errors |
| `npm ci` fails | Update Node.js to version 18 or newer, then delete `frontend/node_modules` and run it again |
| You want a clean database again | Stop the backend and run `git checkout -- backend/zeroq_ai.db`. This **erases** every complaint you added |

## Run the automated tests (optional)

With `(.venv)` active, from the `ZeroQ-AI/ZeroQ-AI` folder:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest tests -q
cd frontend && npm test
```

For architecture, deployment and pilot details, see [PILOT_READINESS.md](PILOT_READINESS.md).
