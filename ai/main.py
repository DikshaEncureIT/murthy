from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import shutil
from datetime import datetime
import json
from typing import Dict, Any, List
from dotenv import load_dotenv

from converter import process_excel_to_json
import logging
from logging.handlers import RotatingFileHandler
import os
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Load environment variables
load_dotenv(".env")

# Configure logging
def setup_logging():
    log_file = os.getenv("LOG_FILE", "/logs/backend.log")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Create formatter
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)

    # File handler with rotation (10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# Initialize logging
logger = setup_logging()
logger.info("Backend service starting...")

app = FastAPI(
    title="Excel to JSON Converter API",
    description="API for uploading Excel files and converting them to JSON format",
    version="1.0.0"
)

# Configure CORS to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",  # Vite default dev server
        "http://127.0.0.1:5173",
        "http://frontend:8080",  # Docker container networking
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(f"Request started: {request.method} {request.url}")

        # Process request
        response = await call_next(request)

        # Log response
        duration = time.time() - start_time
        logger.info(
            f"Request completed: {request.method} {request.url} - "
            f"Status: {response.status_code} - Duration: {round(duration * 1000, 2)}ms"
        )

        return response

# Add middleware
app.add_middleware(RequestLoggingMiddleware)

# Define folders
INPUT_FOLDER = Path("input")
OUTPUT_FOLDER = Path("markdown")

# Create folders if they don't exist
INPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Excel to JSON Converter API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload",
            "convert": "/convert",
            "health": "/health",
            "available_downloads": "/available-downloads",
            "download_excel": "/download/excel/{filename}",
            "download_all": "/download/all",
            "cleanup": "/cleanup"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify the service is running"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Excel to JSON Converter",
        "input_folder": str(INPUT_FOLDER.absolute()),
        "output_folder": str(OUTPUT_FOLDER.absolute())
    }


@app.post("/upload", tags=["File Operations"])
async def upload_file(file: UploadFile = File(...)):
    """
    Upload an Excel file to the input folder.

    Args:
        file: Excel file (.xlsx or .xls)

    Returns:
        JSON response with upload status and file information
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only .xlsx and .xls files are allowed"
        )

    try:
        # Create input folder if it doesn't exist
        INPUT_FOLDER.mkdir(parents=True, exist_ok=True)

        # Save the uploaded file
        file_path = INPUT_FOLDER / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = file_path.stat().st_size
        logger.info(f"File uploaded successfully: {file.filename} ({file_size} bytes)")

        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "filename": file.filename,
                "file_path": str(file_path),
                "file_size": file_path.stat().st_size,
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )


@app.post("/convert", tags=["File Operations"])
async def convert_to_json():
    """
    Convert all Excel files in the input folder to JSON format.

    This endpoint runs the final_json_openai.py logic to:
    1. Process all Excel files in the input folder
    2. Extract tables using LandingAI ADE
    3. Convert tables to JSON using OpenAI
    4. Save results to the markdown/output folder

    Returns:
        JSON response with conversion results
    """
    try:
        # Check if input folder has any Excel files
        excel_files = list(INPUT_FOLDER.glob("*.xlsx")) + list(INPUT_FOLDER.glob("*.xls"))

        if not excel_files:
            raise HTTPException(
                status_code=404,
                detail=f"No Excel files found in {INPUT_FOLDER}"
            )

        logger.info(f"Starting conversion process. Found {len(excel_files)} Excel files")

        # Run the conversion process
        result = await process_excel_to_json()

        # Check if consolidated JSON file exists
        consolidated_file = OUTPUT_FOLDER / "all_tables_consolidated.json"

        response_data = {
            "message": "Conversion completed successfully",
            "files_processed": result["files_processed"],
            "tables_extracted": result["tables_extracted"],
            "output_folder": str(OUTPUT_FOLDER.absolute()),
            "timestamp": datetime.now().isoformat(),
            "per_excel_files": result.get("per_excel_files", [])
        }

        # Include consolidated results if available
        if consolidated_file.exists():
            with open(consolidated_file, "r", encoding="utf-8") as f:
                response_data["consolidated_results"] = json.load(f)

        return JSONResponse(
            status_code=200,
            content=response_data
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error during conversion: {str(e)}"
        )


@app.get("/download/excel/{filename}", tags=["File Operations"])
async def download_excel_json(filename: str):
    """
    Download the JSON file for a specific Excel file.

    Args:
        filename: Name of the Excel file (without extension) or the complete JSON filename

    Returns:
        JSON file for download
    """
    try:
        # Handle both formats: "example.xlsx" or "example" or "example_complete.json"
        if filename.endswith("_complete.json"):
            json_filename = filename
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            # Remove extension and add _complete.json
            base_name = filename.rsplit(".", 1)[0]
            json_filename = f"{base_name}_complete.json"
        else:
            json_filename = f"{filename}_complete.json"

        file_path = OUTPUT_FOLDER / json_filename

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"JSON file not found: {json_filename}. Make sure the Excel file has been processed."
            )

        return FileResponse(
            path=file_path,
            media_type="application/json",
            filename=json_filename
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading file: {str(e)}"
        )


@app.get("/download/all", tags=["File Operations"])
async def download_all_json():
    """
    Download the consolidated JSON file with all tables from all Excel files.

    Returns:
        Consolidated JSON file for download
    """
    try:
        file_path = OUTPUT_FOLDER / "all_tables_consolidated.json"

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Consolidated JSON file not found. Please run conversion first."
            )

        return FileResponse(
            path=file_path,
            media_type="application/json",
            filename="all_tables_consolidated.json"
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading file: {str(e)}"
        )


@app.get("/available-downloads", tags=["File Operations"])
async def list_available_downloads():
    """
    List all available JSON files for download.

    Returns:
        JSON response with lists of per-Excel JSON files and consolidated file
    """
    try:
        per_excel_files = []
        consolidated_available = False

        # List per-Excel JSON files
        if OUTPUT_FOLDER.exists():
            for file in OUTPUT_FOLDER.glob("*_complete.json"):
                per_excel_files.append({
                    "filename": file.name,
                    "excel_name": file.name.replace("_complete.json", ""),
                    "size": file.stat().st_size,
                    "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    "download_url": f"/download/excel/{file.name}"
                })

            # Check if consolidated file exists
            consolidated_file = OUTPUT_FOLDER / "all_tables_consolidated.json"
            if consolidated_file.exists():
                consolidated_available = True

        return {
            "per_excel_files": per_excel_files,
            "total_per_excel_files": len(per_excel_files),
            "consolidated_file": {
                "available": consolidated_available,
                "download_url": "/download/all" if consolidated_available else None
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing downloads: {str(e)}"
        )


@app.get("/files", tags=["File Operations"])
async def list_files():
    """
    List all files in input and output folders.

    Returns:
        JSON response with lists of input and output files
    """
    try:
        input_files = []
        output_files = []

        # List input files
        if INPUT_FOLDER.exists():
            input_files = [
                {
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in INPUT_FOLDER.glob("*")
                if f.is_file()
            ]

        # List output files
        if OUTPUT_FOLDER.exists():
            output_files = [
                {
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in OUTPUT_FOLDER.glob("*")
                if f.is_file()
            ]

        return {
            "input_folder": str(INPUT_FOLDER.absolute()),
            "output_folder": str(OUTPUT_FOLDER.absolute()),
            "input_files": input_files,
            "output_files": output_files,
            "total_input_files": len(input_files),
            "total_output_files": len(output_files)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing files: {str(e)}"
        )


@app.post("/cleanup", tags=["File Operations"])
async def cleanup_folders():
    """
    Clean up input and output folders by removing all files.
    This endpoint is called when starting a new conversion to ensure
    a fresh start without old files.

    Returns:
        JSON response with cleanup status
    """
    try:
        input_files_removed = 0
        output_files_removed = 0

        # Clean input folder
        if INPUT_FOLDER.exists():
            for file in INPUT_FOLDER.glob("*"):
                if file.is_file():
                    file.unlink()
                    input_files_removed += 1

        # Clean output folder (markdown)
        if OUTPUT_FOLDER.exists():
            for file in OUTPUT_FOLDER.glob("*"):
                if file.is_file():
                    file.unlink()
                    output_files_removed += 1

        return JSONResponse(
            status_code=200,
            content={
                "message": "Folders cleaned successfully",
                "input_files_removed": input_files_removed,
                "output_files_removed": output_files_removed,
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error cleaning folders: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
