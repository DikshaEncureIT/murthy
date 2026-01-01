# Excel to JSON Converter

An AI-powered full-stack application for converting Excel files to structured JSON format using LandingAI ADE and OpenAI.

## Overview

The Excel to JSON Converter is a comprehensive AI-powered solution that transforms Excel spreadsheets into intelligently structured, nested JSON. Using a three-phase pipeline combining LandingAI's ADE DPT-2 document parsing model and OpenAI's GPT-4o-mini language model, the system analyzes table semantics to create meaningful hierarchical data structures rather than flat arrays.

### How It Works

1. **Phase 1: Sheet Splitting** - Each Excel sheet is exported to individual temporary files
2. **Phase 2: Document Parsing** - LandingAI ADE DPT-2 model extracts markdown representation of tables
3. **Phase 3: Intelligent Structuring** - OpenAI GPT-4o-mini analyzes table semantics and creates nested JSON structures

This approach goes beyond simple row/column extraction by understanding the semantic meaning of your data, producing clean, application-ready JSON.

## Features

### Core Functionality
- **Excel Upload** - Support for .xlsx and .xls file formats (max 5 files per batch)
- **AI-Powered Extraction** - LandingAI ADE DPT-2 model for document parsing and markdown extraction
- **Intelligent Structuring** - OpenAI GPT-4o-mini analyzes and structures tables into nested JSON
- **Multiple Output Formats**:
  - Per-Excel JSON files (one per uploaded Excel file)
  - Consolidated JSON file (all tables from all files)
- **Real-time Processing** - Live conversion status and progress tracking
- **Download Management** - Easy access to processed files
- **Upload Limits** - Maximum 5 Excel files per conversion batch
- **Automatic Cleanup** - Previous conversion data automatically cleared on page load/refresh

### Technical Features
- **Dockerized Deployment** - Complete Docker Compose setup for both services
- **Request Tracking** - Request ID-based logging for debugging
- **Rotating Logs** - Automatic log rotation with configurable size limits
- **Hot Reload** - Development mode with live code reloading
- **Health Checks** - Service health monitoring and status endpoints
- **CORS Support** - Properly configured for frontend-backend communication

## Architecture

```
excel-to-json-converter/
├── ai/                          # Backend API Service
│   ├── main.py                  # FastAPI application and endpoints
│   ├── converter.py             # Core conversion logic
│   ├── logger.py                # Centralized logging with RotatingFileHandler
│   ├── request_context.py       # Request ID context management
│   ├── final_json_openai.py     # Original standalone script
│   ├── test_api.py              # API testing script
│   ├── requirements.txt         # Python dependencies
│   ├── Dockerfile               # Backend container configuration
│   ├── API_DOCUMENTATION.md     # Detailed API documentation
│   ├── input/                   # Uploaded Excel files
│   └── markdown/                # Output JSON and markdown files
│
├── frontend/                    # React TypeScript Frontend
│   ├── src/
│   │   ├── components/          # React components (shadcn/ui)
│   │   ├── lib/                 # Utility functions and API client
│   │   └── App.tsx              # Main application component
│   ├── public/                  # Static assets
│   ├── Dockerfile               # Frontend container configuration
│   └── package.json             # Node dependencies
│
├── logs/                        # Application logs
│   ├── backend.log              # Backend service logs
│   └── frontend.log             # Frontend service logs
│
├── docker-compose.yml           # Docker orchestration
└── README.md                    # This file
```

## Prerequisites

### For Docker Deployment (Recommended)
- Docker Engine 20.10+
- Docker Compose 2.0+

### For Manual Setup
- Python 3.11+
- Node.js 18+
- npm or bun

### API Keys (Required)
- **OpenAI API Key** - Required for JSON structuring with GPT-4o-mini
- **LandingAI API Key** - Required for document parsing with ADE DPT-2 model

## Quick Start with Docker

### 1. Configure Environment Variables

Create `.env` file in the `ai/` directory:

```bash
cd ai/
cp .env.example .env
```

Edit `ai/.env` and add your API keys:

```env
LANDINGAI_API_KEY=your_landingai_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 2. Start the Services

```bash
# From project root
docker-compose up -d
```

This will start:
- Backend API at http://localhost:8000
- Frontend UI at http://localhost:8080

### 3. Access the Application

- **Web Interface**: http://localhost:8080
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

### 4. Stop the Services

```bash
docker-compose down
```

## Manual Setup

### Backend Setup

```bash
# Navigate to backend directory
cd ai/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be available at http://localhost:8000

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend/

# Install dependencies
npm install
# or using bun:
bun install

# Configure environment (optional)
cp .env.example .env

# Start development server
npm run dev
# or using bun:
bun run dev
```

Frontend will be available at http://localhost:5173 (Vite default) or http://localhost:8080 (Docker)

## Usage

### Web Interface

1. Open http://localhost:8080 in your browser
2. Click "Choose File" or drag and drop an Excel file
3. Click "Upload & Convert"
4. Wait for processing to complete
5. Download individual or consolidated JSON files

**Note:** The system supports uploading up to 5 Excel files per conversion batch. Files and results are automatically cleaned on page refresh or when starting a new conversion.

### API Usage

For detailed API documentation, see [ai/API_DOCUMENTATION.md](ai/API_DOCUMENTATION.md)

#### Basic Workflow

```bash
# 1. Check service health
curl http://localhost:8000/health

# 2. Upload Excel file
curl -X POST http://localhost:8000/upload \
  -F "file=@example.xlsx"

# 3. Convert to JSON
curl -X POST http://localhost:8000/convert

# 4. Download results
curl http://localhost:8000/download/all -O
```

#### Python Example

```python
import requests

BASE_URL = "http://localhost:8000"

# Upload file
with open("data.xlsx", "rb") as f:
    response = requests.post(f"{BASE_URL}/upload", files={"file": f})
    print(response.json())

# Convert to JSON
response = requests.post(f"{BASE_URL}/convert")
results = response.json()

# Download consolidated results
download = requests.get(f"{BASE_URL}/download/all")
with open("all_tables.json", "wb") as f:
    f.write(download.content)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/upload` | POST | Upload Excel file |
| `/convert` | POST | Convert uploaded files to JSON |
| `/files` | GET | List input/output files |
| `/available-downloads` | GET | List available JSON downloads |
| `/download/excel/{filename}` | GET | Download specific Excel JSON |
| `/download/all` | GET | Download consolidated JSON |
| `/cleanup` | POST | Clear input/output folders |

For detailed request/response examples, see the [API Documentation](ai/API_DOCUMENTATION.md).

## Output Format

The converter produces **nested, intelligently structured JSON** that reflects the semantic meaning of your Excel data, not just flat tables.

### Structure Overview

Each table extraction includes:
- `excel_file`: Source Excel filename
- `sheet_name`: Sheet name where the table was found
- `data`: Nested JSON object representing the table's semantic structure

### Example 1: Nested Key-Value Structure

For a form-like table with categories and fields:

**Input Excel Table:**
```
| Referrer | Name         | Richard Woodhead              |
|          | Company Name | GPS Investment Fund Limited   |
|          | Email        | Richard@gpsinvest.com.au      |
```

**Output JSON:**
```json
{
  "excel_file": "example.xlsx",
  "sheet_name": "Borrower",
  "data": {
    "Referrer": {
      "Name": "Richard Woodhead",
      "Company Name": "GPS Investment Fund Limited",
      "Email": "Richard@gpsinvest.com.au"
    }
  }
}
```

### Example 2: Array of Objects

For tabular data with repeating records:

**Input Excel Table:**
```
| Stock Description | No. Lots | Gross Revenue | Per Lot |
|-------------------|----------|---------------|---------|
| 1 Br              | 3        | 795000        | 265000  |
| 2 bed             | 11       | 3289000       | 299000  |
```

**Output JSON:**
```json
{
  "excel_file": "example.xlsx",
  "sheet_name": "Feasibility",
  "data": {
    "Stock Description": [
      {
        "Type": "1 Br",
        "No. Lots": 3,
        "Gross Revenue": "$795,000",
        "Per Lot": "$265,000"
      },
      {
        "Type": "2 bed",
        "No. Lots": 11,
        "Gross Revenue": "$3,289,000",
        "Per Lot": "$299,000"
      }
    ]
  }
}
```

### Output Files Generated

1. **Per-Excel JSON Files**: `{excel_name}_complete.json`
   - Contains all tables from a single Excel file
   - Each file is an array of table objects

2. **Consolidated JSON File**: `all_tables_consolidated.json`
   - Contains all tables from all processed Excel files
   - Useful for batch processing multiple files

### Key Features

- **Intelligent Structuring**: OpenAI GPT-4o-mini analyzes table semantics to create meaningful nested structures
- **Preservation of Data**: All cells are preserved, including empty values (represented as `""`)
- **Multiple Format Support**: Handles various Excel table layouts (forms, lists, hierarchical data)
- **No Data Loss**: Every row and cell from the original Excel is captured

## Development

### Backend Development

```bash
cd ai/

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn main:app --reload --log-level debug

# Run tests
python test_api.py /path/to/test/file.xlsx
```

### Frontend Development

```bash
cd frontend/

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Docker Development

```bash
# Build and start services
docker-compose up --build

# View logs
docker-compose logs -f

# Restart specific service
docker-compose restart backend
docker-compose restart frontend

# Execute commands in containers
docker exec -it excel_backend bash
docker exec -it excel_frontend sh
```

## Configuration

### Environment Variables

#### Backend (`ai/.env`)
- `LANDINGAI_API_KEY` - LandingAI API key (required) - Get from https://landing.ai/
- `OPENAI_API_KEY` - OpenAI API key (required) - Get from https://platform.openai.com/
- `LOG_FILE` - Log file path (default: `/logs/backend.log`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

#### Frontend (`frontend/.env`)
- `VITE_API_BASE_URL` - Backend API URL (default: `http://backend:8000` for Docker, `http://localhost:8000` for manual setup)
- `LOG_FILE` - Log file path (default: `/logs/frontend.log`)

### Docker Configuration

Edit `docker-compose.yml` to customize:
- Port mappings
- Resource limits (CPU/memory)
- Volume mounts
- Health check intervals

## Logging

### Request Tracking
All requests are tracked with unique request IDs. Logs include:
- `[req:xxxxxxxxxxxx]` - Request ID (first 12 characters of UUID)
- Request method, URL, and duration
- Error stack traces when applicable

### Log Files
- **Backend**: `logs/backend.log` - Rotates at 10MB, keeps 5 backups
- **Frontend**: `logs/frontend.log` - Console output from Vite dev server

### Log Levels
- `DEBUG` - Detailed diagnostic information
- `INFO` - General informational messages
- `WARNING` - Warning messages
- `ERROR` - Error messages with stack traces

## Troubleshooting

### Backend Issues

**Server won't start**
- Check if port 8000 is already in use
- Verify all dependencies installed: `pip install -r requirements.txt`
- Ensure `.env` file exists with valid API keys

**Upload fails**
- Verify file is .xlsx or .xls format
- Check file size (max 10MB default)
- Ensure `ai/input/` directory has write permissions

**Conversion fails**
- Verify API keys in `.env` file
- Check logs: `tail -f logs/backend.log`
- Ensure OpenAI API has credits

### Frontend Issues

**Cannot connect to backend**
- Verify backend is running: `curl http://localhost:8000/health`
- Check `VITE_API_BASE_URL` in `.env`
- Verify CORS settings in `ai/main.py`

**Build fails**
- Clear cache: `rm -rf node_modules package-lock.json`
- Reinstall: `npm install`
- Check Node.js version: `node --version` (should be 18+)

### Docker Issues

**Containers won't start**
- Check Docker daemon: `docker ps`
- View logs: `docker-compose logs`
- Rebuild: `docker-compose up --build`

**Cannot access services**
- Check port conflicts: `netstat -an | grep 8000`
- Verify container status: `docker-compose ps`
- Check firewall settings

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **LandingAI ADE DPT-2** - Document parsing model for markdown extraction
- **OpenAI GPT-4o-mini** - Language model for intelligent JSON structuring
- **Pandas** - Excel file processing and sheet manipulation
- **openpyxl** - Excel file structure preservation (columns, formatting, merged cells)
- **Python 3.11** - Programming language

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool and dev server
- **shadcn/ui** - Component library
- **Tailwind CSS** - Utility-first CSS
- **Radix UI** - Accessible component primitives

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **GitHub** - Version control

## Project Status

Current Version: **1.0.0**

### Completed Features
- ✅ Backend API with FastAPI
- ✅ Frontend UI with React + TypeScript
- ✅ AI-powered Excel to JSON conversion
- ✅ Docker Compose deployment
- ✅ Request ID tracking and logging
- ✅ File upload and download management
- ✅ Health monitoring
- ✅ API documentation

### Roadmap
- [ ] Batch file processing
- [ ] User authentication
- [ ] Processing history
- [ ] Custom conversion templates
- [ ] Advanced error handling
- [ ] Rate limiting

## License

This project is part of the EncureIT Project.

## Support

For issues or questions:
- Check the [API Documentation](ai/API_DOCUMENTATION.md)
- Review logs in `logs/` directory
- Contact the development team

---

**Built with ❤️ by the EncureIT Team**
