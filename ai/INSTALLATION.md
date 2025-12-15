# Installation Guide

Complete step-by-step installation guide for the Excel to JSON Converter API.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)
- API Keys:
  - OpenAI API Key (required)
  - LandingAI API Key (optional)

## Step-by-Step Installation

### 1. Navigate to the Project Directory

```bash
cd /home/diksha-encureitlp43/Documents/EncureIT/murthy_project/ai
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- fastapi
- uvicorn[standard]
- python-multipart
- landingai-ade
- openai
- python-dotenv
- pandas
- openpyxl
- cohere

### 4. Configure Environment Variables

Create a `.env` file in the `ai` folder:

```bash
# Copy the example file
cp .env.example .env

# Edit the .env file
nano .env  # or use any text editor
```

Add your API keys:

```env
LANDINGAI_API_KEY=your_landingai_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

**Getting API Keys:**

- **OpenAI API Key**: Get from https://platform.openai.com/api-keys
- **LandingAI API Key**: Get from https://landing.ai/

### 5. Create Required Folders

```bash
# Folders will be created automatically, but you can create them manually:
mkdir -p input markdown
```

### 6. Make the Startup Script Executable

```bash
chmod +x run_server.sh
```

### 7. Verify Installation

Test that all dependencies are installed correctly:

```bash
python -c "import fastapi, uvicorn, landingai_ade, openai, pandas; print('All dependencies installed successfully!')"
```

## Starting the Server

### Method 1: Using the Startup Script (Recommended)

```bash
./run_server.sh
```

### Method 2: Using Uvicorn Directly

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Method 3: Using Python

```bash
python main.py
```

## Verify Installation

Once the server is running, test it:

```bash
# In a new terminal, test the health endpoint
curl http://localhost:8000/health

# Or open in browser
# http://localhost:8000/docs
```

## Testing the API

Run the test suite:

```bash
# Basic tests (without file upload)
python test_api.py

# Full tests (with file upload)
python test_api.py /path/to/test/file.xlsx
```

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: `ValueError: OPENAI_API_KEY is not set in .env`

**Solution:**
```bash
# Check if .env file exists
ls -la .env

# If not, create it
cp .env.example .env

# Edit and add your API key
nano .env
```

### Issue: Port 8000 already in use

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill the process or use a different port
uvicorn main:app --host 0.0.0.0 --port 8001
```

### Issue: Permission denied when running `./run_server.sh`

**Solution:**
```bash
chmod +x run_server.sh
```

### Issue: Cannot connect to server

**Solution:**
- Verify server is running: `ps aux | grep uvicorn`
- Check firewall settings
- Try accessing via localhost: `http://localhost:8000/health`

## Uninstallation

To uninstall the project:

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv

# Optionally remove output files
rm -rf markdown temp_sheets
```

## Updating

To update dependencies:

```bash
# Activate virtual environment
source venv/bin/activate

# Update packages
pip install --upgrade -r requirements.txt
```

## Production Deployment

For production deployment:

### 1. Install Gunicorn

```bash
pip install gunicorn
```

### 2. Run with Gunicorn

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 3. Use a Process Manager

**Using systemd (Linux):**

Create `/etc/systemd/system/excel-converter.service`:

```ini
[Unit]
Description=Excel to JSON Converter API
After=network.target

[Service]
Type=notify
User=your_user
WorkingDirectory=/path/to/murthy_project/ai
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable excel-converter
sudo systemctl start excel-converter
sudo systemctl status excel-converter
```

## Environment-Specific Configuration

### Development

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Staging

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Production

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
```

## Next Steps

After installation:

1. Read [README.md](README.md) for usage instructions
2. Check [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for API details
3. Run tests with [test_api.py](test_api.py)
4. Upload your first Excel file and test the conversion

## Support

If you encounter any issues not covered here, please contact the development team.
