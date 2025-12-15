# Excel to JSON Converter API Documentation

## Overview

This FastAPI application provides endpoints to upload Excel files and convert them to JSON format using LandingAI ADE and OpenAI.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the `ai` folder with your API keys:

```env
LANDINGAI_API_KEY=your_landingai_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Start the Server

#### Using the Shell Script (Recommended)

```bash
chmod +x run_server.sh
./run_server.sh
```

#### Using Uvicorn Directly

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Using Python

```bash
python main.py
```

## API Endpoints

### 1. Health Check

**Endpoint:** `GET /health`

**Description:** Check if the service is running and get system information.

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-12-15T10:30:00.123456",
  "service": "Excel to JSON Converter",
  "input_folder": "/path/to/input",
  "output_folder": "/path/to/markdown"
}
```

**cURL Example:**

```bash
curl http://localhost:8000/health
```

---

### 2. Upload Excel File

**Endpoint:** `POST /upload`

**Description:** Upload an Excel file (.xlsx or .xls) to the input folder.

**Parameters:**

- `file` (required): Excel file to upload (multipart/form-data)

**Response:**

```json
{
  "message": "File uploaded successfully",
  "filename": "example.xlsx",
  "file_path": "/path/to/input/example.xlsx",
  "file_size": 12345,
  "timestamp": "2025-12-15T10:30:00.123456"
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/your/file.xlsx"
```

**Python Example:**

```python
import requests

url = "http://localhost:8000/upload"
files = {"file": open("example.xlsx", "rb")}
response = requests.post(url, files=files)
print(response.json())
```

---

### 3. Convert to JSON

**Endpoint:** `POST /convert`

**Description:** Convert all Excel files in the input folder to JSON format.

This endpoint:
1. Processes all Excel files in the input folder
2. Extracts tables using LandingAI ADE
3. Converts tables to JSON using OpenAI
4. Saves results to the markdown/output folder

**Response:**

```json
{
  "message": "Conversion completed successfully",
  "files_processed": 1,
  "tables_extracted": 5,
  "output_folder": "/path/to/markdown",
  "timestamp": "2025-12-15T10:30:00.123456",
  "consolidated_results": [
    {
      "sheet_name": "Sheet1",
      "table_index": 1,
      "title": "",
      "headers": ["Column1", "Column2"],
      "rows": [
        ["value1", "value2"],
        ["value3", "value4"]
      ],
      "excel_file": "example.xlsx",
      "file_index": 1
    }
  ]
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8000/convert
```

**Python Example:**

```python
import requests

url = "http://localhost:8000/convert"
response = requests.post(url)
print(response.json())
```

---

### 4. List Files

**Endpoint:** `GET /files`

**Description:** List all files in input and output folders.

**Response:**

```json
{
  "input_folder": "/path/to/input",
  "output_folder": "/path/to/markdown",
  "input_files": [
    {
      "filename": "example.xlsx",
      "size": 12345,
      "modified": "2025-12-15T10:30:00"
    }
  ],
  "output_files": [
    {
      "filename": "example_Sheet1_table_1.json",
      "size": 678,
      "modified": "2025-12-15T10:35:00"
    }
  ],
  "total_input_files": 1,
  "total_output_files": 1
}
```

**cURL Example:**

```bash
curl http://localhost:8000/files
```

---

### 5. Root

**Endpoint:** `GET /`

**Description:** Get API information and available endpoints.

**Response:**

```json
{
  "message": "Excel to JSON Converter API",
  "version": "1.0.0",
  "endpoints": {
    "upload": "/upload",
    "convert": "/convert",
    "health": "/health"
  }
}
```

## Interactive API Documentation

Once the server is running, you can access interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Workflow Example

### Complete Workflow Using cURL

```bash
# 1. Check service health
curl http://localhost:8000/health

# 2. Upload an Excel file
curl -X POST http://localhost:8000/upload \
  -F "file=@example.xlsx"

# 3. Convert to JSON
curl -X POST http://localhost:8000/convert

# 4. List all files
curl http://localhost:8000/files
```

### Complete Workflow Using Python

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Check health
health = requests.get(f"{BASE_URL}/health")
print("Health:", health.json())

# 2. Upload file
with open("example.xlsx", "rb") as f:
    files = {"file": f}
    upload_response = requests.post(f"{BASE_URL}/upload", files=files)
    print("Upload:", upload_response.json())

# 3. Convert to JSON
convert_response = requests.post(f"{BASE_URL}/convert")
print("Convert:", convert_response.json())

# 4. List files
files_response = requests.get(f"{BASE_URL}/files")
print("Files:", files_response.json())
```

## Output Files

After conversion, the following files are generated in the `markdown` folder:

1. **Individual table JSON files:** `{excel_name}_{sheet_name}_table_{index}.json`
2. **Markdown files:** `{excel_name}_{sheet_name}.md`
3. **Consolidated JSON:** `all_tables_consolidated.json`

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad request (e.g., invalid file format)
- `404`: Not found (e.g., no Excel files in input folder)
- `500`: Internal server error

## Production Deployment

For production deployment with Gunicorn:

```bash
pip install gunicorn

# Run with multiple workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Notes

- The API processes all Excel files in the `input` folder when `/convert` is called
- Temporary files are automatically cleaned up after processing
- The server supports both `.xlsx` and `.xls` file formats
- File uploads are validated to ensure only Excel files are accepted
