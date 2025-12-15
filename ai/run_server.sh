#!/bin/bash

# Excel to JSON Converter API Server
# This script starts the FastAPI server using Uvicorn

echo "Starting Excel to JSON Converter API Server..."
echo "=============================================="
echo ""
echo "Server will be available at:"
echo "  - Local:   http://localhost:8000"
echo "  - Network: http://0.0.0.0:8000"
echo ""
echo "API Documentation:"
echo "  - Swagger UI: http://localhost:8000/docs"
echo "  - ReDoc:      http://localhost:8000/redoc"
echo ""
echo "Press CTRL+C to stop the server"
echo "=============================================="
echo ""

# Run uvicorn with auto-reload for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
