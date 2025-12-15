from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
from datetime import datetime
import json
from typing import Dict, Any
from dotenv import load_dotenv

from converter import process_excel_to_json

# Load environment variables
load_dotenv(".env")

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            "health": "/health"
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

        # Run the conversion process
        result = process_excel_to_json()

        # Check if consolidated JSON file exists
        consolidated_file = OUTPUT_FOLDER / "all_tables_consolidated.json"

        response_data = {
            "message": "Conversion completed successfully",
            "files_processed": result["files_processed"],
            "tables_extracted": result["tables_extracted"],
            "output_folder": str(OUTPUT_FOLDER.absolute()),
            "timestamp": datetime.now().isoformat()
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
        raise HTTPException(
            status_code=500,
            detail=f"Error during conversion: {str(e)}"
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
