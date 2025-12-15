# Excel to JSON Converter API

A FastAPI-based REST API service that converts Excel files to JSON format using LandingAI ADE and OpenAI.

## Features

- **File Upload**: Upload Excel files (.xlsx, .xls) to the server
- **JSON Conversion**: Convert Excel tables to structured JSON using AI
- **Health Check**: Monitor service status
- **File Management**: List and manage input/output files
- **Interactive Documentation**: Auto-generated Swagger UI and ReDoc

## Project Structure

```
ai/
├── main.py                  # FastAPI application with endpoints
├── converter.py             # Core conversion logic (refactored from final_json_openai.py)
├── final_json_openai.py     # Original standalone script
├── requirements.txt         # Python dependencies
├── run_server.sh           # Server startup script
├── test_api.py             # API testing script
├── API_DOCUMENTATION.md    # Detailed API documentation
├── README.md               # This file
├── .env                    # Environment variables (API keys)
├── input/                  # Folder for uploaded Excel files
└── markdown/               # Output folder for JSON and markdown files
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with your API keys:

```bash
LANDINGAI_API_KEY=your_landingai_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 3. Start the Server

```bash
# Make script executable (first time only)
chmod +x run_server.sh

# Start the server
./run_server.sh
```

The server will start at `http://localhost:8000`

### 4. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### 1. Health Check
```bash
GET /health
```
Check service status and configuration.

### 2. Upload Excel File
```bash
POST /upload
```
Upload an Excel file to the input folder.

**Example:**
```bash
curl -X POST http://localhost:8000/upload -F "file=@example.xlsx"
```

### 3. Convert to JSON
```bash
POST /convert
```
Convert all Excel files in the input folder to JSON.

**Example:**
```bash
curl -X POST http://localhost:8000/convert
```

### 4. List Files
```bash
GET /files
```
List all files in input and output folders.

### 5. Root
```bash
GET /
```
Get API information.

## Usage Examples

### Using cURL

```bash
# Upload a file
curl -X POST http://localhost:8000/upload -F "file=@data.xlsx"

# Convert to JSON
curl -X POST http://localhost:8000/convert

# Check health
curl http://localhost:8000/health
```

### Using Python

```python
import requests

# Upload file
with open("data.xlsx", "rb") as f:
    response = requests.post("http://localhost:8000/upload", files={"file": f})
    print(response.json())

# Convert to JSON
response = requests.post("http://localhost:8000/convert")
print(response.json())
```

## Testing

Run the test suite to verify all endpoints:

```bash
# Test without file upload
python test_api.py

# Test with file upload
python test_api.py /path/to/your/file.xlsx
```

## How It Works

1. **Upload**: Excel files are uploaded to the `input/` folder
2. **Processing**:
   - Each sheet is exported to a temporary Excel file
   - LandingAI ADE extracts markdown from the Excel sheet
   - OpenAI processes the markdown to extract structured table data
   - Results are saved as individual JSON files
3. **Output**:
   - Individual table JSON files: `{excel}_{sheet}_table_{n}.json`
   - Markdown files: `{excel}_{sheet}.md`
   - Consolidated JSON: `all_tables_consolidated.json`

## Output Format

Each table is converted to JSON with this structure:

```json
{
  "sheet_name": "Sheet1",
  "table_index": 1,
  "title": "",
  "headers": ["Column1", "Column2", "Column3"],
  "rows": [
    ["value1", "value2", "value3"],
    ["value4", "value5", "value6"]
  ],
  "excel_file": "example.xlsx",
  "file_index": 1
}
```

## Running with Uvicorn Directly

```bash
# Development mode with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Running with Gunicorn (Production)

```bash
# Install gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LANDINGAI_API_KEY` | LandingAI ADE API key | Optional* |
| `OPENAI_API_KEY` | OpenAI API key | Yes |

*LandingAI API key may have a default value

## Dependencies

- **FastAPI**: Modern web framework for building APIs
- **Uvicorn**: ASGI server for FastAPI
- **LandingAI ADE**: Document parsing and markdown extraction
- **OpenAI**: Table extraction and JSON conversion
- **Pandas**: Excel file processing
- **python-multipart**: File upload support

## Troubleshooting

### Server won't start
- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check .env file exists with valid API keys

### Upload fails
- Ensure file is .xlsx or .xls format
- Check file size limits
- Verify input folder has write permissions

### Conversion fails
- Verify API keys in .env file
- Check if Excel files exist in input folder
- Review server logs for detailed error messages

### Connection refused
- Ensure server is running: `./run_server.sh`
- Check firewall settings
- Verify correct host and port

## Development

### Project Files

- **[main.py](main.py)**: FastAPI application and endpoint definitions
- **[converter.py](converter.py)**: Modular conversion logic extracted from final_json_openai.py
- **[final_json_openai.py](final_json_openai.py)**: Original standalone conversion script
- **[run_server.sh](run_server.sh)**: Server startup script with uvicorn
- **[test_api.py](test_api.py)**: Automated API testing script

### Adding New Endpoints

1. Define endpoint in [main.py](main.py)
2. Add conversion logic to [converter.py](converter.py) if needed
3. Update [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
4. Add tests to [test_api.py](test_api.py)

## API Documentation

For detailed API documentation with request/response examples, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

## License

This project is part of the EncureIT Murthy Project.

## Support

For issues or questions, please contact the development team.
