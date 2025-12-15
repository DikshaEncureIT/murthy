# 🚀 Quick Start Guide - Murthy Excel to JSON Converter

## ✅ Prerequisites Check

Before starting, ensure you have:
- ✅ Python 3.11+ installed
- ✅ Node.js 18+ installed
- ✅ API Keys configured in `ai/.env`

## 📋 Step-by-Step Instructions

### **STEP 1: Start Backend (Terminal 1)**

```bash
# Navigate to project root
cd /home/diksha-encureitlp43/Documents/EncureIT/murthy_project

# Activate virtual environment
source venv/bin/activate

# Navigate to AI directory
cd ai

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the backend server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

✅ **Backend is ready when you see:** `Application startup complete.`

**Test backend:**
Open browser: http://localhost:8000/health
Should see: `{"status":"healthy",...}`

---

### **STEP 2: Start Frontend (Terminal 2 - NEW TERMINAL)**

```bash
# Navigate to frontend directory
cd /home/diksha-encureitlp43/Documents/EncureIT/murthy_project/frontend

# Install dependencies (first time only)
npm install

# Start frontend development server
npm run dev
```

**Expected Output:**
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:8080/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

✅ **Frontend is ready when you see:** Local URL displayed

---

### **STEP 3: Open Application**

Open your browser and go to:
```
http://localhost:8080
```

You should see the Murthy Excel to JSON Converter interface!

---

## 🧪 Test the AI Integration

1. **Upload a file:**
   - Drag & drop an Excel file (.xlsx or .xls)
   - Or click to browse and select

2. **Watch the magic happen:**
   - 📢 Toast: "Files added - 1 file ready to upload"
   - Click "Upload & Convert"
   - 📢 Toast: "Uploading files..."
   - 📢 Toast: "✓ File uploaded - yourfile.xlsx uploaded successfully"
   - 📢 Toast: "Converting files... - AI is extracting tables"
   - ⏳ **Backend is now using:**
     - **LandingAI ADE** to extract tables from Excel
     - **OpenAI GPT-4o-mini** to structure the data as JSON
   - 📢 Toast: "✓ Conversion successful! - Extracted X tables"

3. **Download result:**
   - Click "Download JSON File"
   - 📢 Toast: "Download started"

---

## 🔍 How the AI Backend Works

### Upload Process:
```
Frontend → POST /upload → Backend saves file to ai/input/
```

### Conversion Process (AI Magic! ✨):
```
1. Backend reads Excel file from ai/input/
2. For each sheet:
   ├─ LandingAI ADE extracts tables as markdown
   ├─ OpenAI GPT-4o-mini converts markdown to structured JSON
   └─ Saves individual table JSONs
3. Creates consolidated JSON with all tables
4. Returns result to frontend
```

### Files Created:
```
ai/input/           ← Your uploaded Excel files
ai/markdown/        ← AI-generated outputs
  ├─ *.md          ← Markdown from LandingAI
  ├─ *_table_1.json ← Individual tables
  └─ all_tables_consolidated.json ← Final result
```

---

## ⚙️ API Endpoints Being Used

### 1. `POST /upload`
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@yourfile.xlsx"
```
**What it does:** Saves Excel file to backend

### 2. `POST /convert`
```bash
curl -X POST http://localhost:8000/convert
```
**What it does:**
- Calls LandingAI ADE API with your `LANDINGAI_API_KEY`
- Calls OpenAI API with your `OPENAI_API_KEY`
- Returns structured JSON

### 3. `GET /health`
```bash
curl http://localhost:8000/health
```
**What it does:** Checks if backend is running

---

## 🐛 Troubleshooting

### Issue: "Cannot connect to backend"

**Check 1: Is backend running?**
```bash
curl http://localhost:8000/health
```
If error → Backend not running. Start it with Step 1.

**Check 2: CORS enabled?**
```bash
# Check ai/main.py line 22-34
grep -A 10 "CORS" ai/main.py
```
Should see `CORSMiddleware` configuration.

**Check 3: Frontend .env configured?**
```bash
cat frontend/.env
```
Should see: `VITE_API_BASE_URL=http://localhost:8000`

---

### Issue: "Conversion failed - API key error"

**Check API keys:**
```bash
cat ai/.env
```

Should contain:
```env
LANDINGAI_API_KEY=MDVoc3RnNGQ0Nm9rdjhkN2Qya2MxOnZkcTlQZnJQUnNJM3VXeHAwRWI3cGpRR29XMm00U0Qw
OPENAI_API_KEY=sk-proj-...
```

**Verify keys are loaded:**
```bash
cd ai
source ../venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); print('LandingAI:', os.getenv('LANDINGAI_API_KEY')[:20]); print('OpenAI:', os.getenv('OPENAI_API_KEY')[:20])"
```

---

### Issue: "ModuleNotFoundError"

**Backend:**
```bash
cd ai
source ../venv/bin/activate
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

### Issue: "Port already in use"

**Backend (port 8000):**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
# Then update frontend/.env: VITE_API_BASE_URL=http://localhost:8001
```

**Frontend (port 8080):**
```bash
# Vite will auto-use next port (8081, 8082, etc.)
```

---

## 📊 Verify AI Integration

### Check Backend Logs
When you upload and convert, you should see in Terminal 1:
```
INFO:     Processing Excel File 1/1: yourfile.xlsx
INFO:     Found 1 sheet(s): Sheet1
INFO:     -> Exporting sheet to temporary Excel file...
INFO:     -> Sending to Landing AI ADE...
INFO:     -> Extracting tables with OpenAI...
INFO:     Successfully extracted 3 table(s)
```

### Check Generated Files
```bash
ls -la ai/markdown/
```
Should see:
- `*.md` files (markdown from LandingAI)
- `*_table_*.json` files (individual tables)
- `all_tables_consolidated.json` (final result)

---

## 🎯 Success Indicators

✅ Backend shows: "Application startup complete"
✅ Frontend shows: Local URL
✅ Browser opens Murthy interface
✅ Toast notifications appear on file upload
✅ File upload shows ✓ checkmark
✅ Backend logs show "Landing AI" and "OpenAI"
✅ Conversion completes with table count
✅ Download provides JSON file

---

## 💡 Quick Commands

**Start everything:**
```bash
# Terminal 1 - Backend
cd ~/Documents/EncureIT/murthy_project && source venv/bin/activate && cd ai && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd ~/Documents/EncureIT/murthy_project/frontend && npm run dev
```

**Stop everything:**
```
Ctrl + C in each terminal
```

**View API docs:**
```
http://localhost:8000/docs
```

---

## 📞 Need Help?

1. Check backend logs (Terminal 1)
2. Check frontend console (Browser F12)
3. Check network tab (Browser F12 → Network)
4. Verify API keys in `ai/.env`
5. Ensure CORS is configured in `ai/main.py`

---

## 🎉 You're All Set!

Your frontend is now connected to the AI-powered backend using:
- **LandingAI ADE** for table extraction
- **OpenAI GPT-4o-mini** for JSON conversion

Enjoy converting Excel to JSON with AI! ✨
