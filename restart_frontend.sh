#!/bin/bash

echo "===================================="
echo "Restarting Frontend"
echo "===================================="
echo ""

# Kill any existing Vite processes
echo "Stopping existing frontend processes..."
pkill -f "vite" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null
sleep 2

# Navigate to frontend directory
cd /home/diksha-encureitlp43/Documents/EncureIT/murthy_project/frontend

echo "Starting frontend..."
echo ""
echo "The frontend will start on http://localhost:8080"
echo "Check the console for the API URL being used"
echo ""
echo "Press Ctrl+C to stop"
echo "===================================="
echo ""

# Start the development server
npm run dev
