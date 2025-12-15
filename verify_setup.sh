#!/bin/bash

echo "=================================="
echo "Murthy Setup Verification"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Python
echo -n "Checking Python... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python not found${NC}"
fi

# Check 2: Node.js
echo -n "Checking Node.js... "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓ Node $NODE_VERSION${NC}"
else
    echo -e "${RED}✗ Node.js not found${NC}"
fi

# Check 3: Virtual Environment
echo -n "Checking virtual environment... "
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ venv exists${NC}"
else
    echo -e "${RED}✗ venv not found${NC}"
fi

# Check 4: Backend .env
echo -n "Checking backend .env... "
if [ -f "ai/.env" ]; then
    if grep -q "OPENAI_API_KEY" ai/.env && grep -q "LANDINGAI_API_KEY" ai/.env; then
        echo -e "${GREEN}✓ API keys configured${NC}"
    else
        echo -e "${YELLOW}⚠ .env exists but keys may be missing${NC}"
    fi
else
    echo -e "${RED}✗ ai/.env not found${NC}"
fi

# Check 5: Frontend .env
echo -n "Checking frontend .env... "
if [ -f "frontend/.env" ]; then
    if grep -q "VITE_API_BASE_URL" frontend/.env; then
        API_URL=$(grep "VITE_API_BASE_URL" frontend/.env | cut -d'=' -f2)
        echo -e "${GREEN}✓ Configured: $API_URL${NC}"
    else
        echo -e "${YELLOW}⚠ .env exists but VITE_API_BASE_URL missing${NC}"
    fi
else
    echo -e "${RED}✗ frontend/.env not found${NC}"
fi

# Check 6: Backend dependencies
echo -n "Checking backend dependencies... "
if [ -f "ai/requirements.txt" ]; then
    echo -e "${GREEN}✓ requirements.txt exists${NC}"
else
    echo -e "${RED}✗ requirements.txt not found${NC}"
fi

# Check 7: Frontend dependencies
echo -n "Checking frontend dependencies... "
if [ -d "frontend/node_modules" ]; then
    echo -e "${GREEN}✓ node_modules exists${NC}"
else
    echo -e "${YELLOW}⚠ node_modules not found (run: npm install)${NC}"
fi

# Check 8: CORS in main.py
echo -n "Checking CORS configuration... "
if grep -q "CORSMiddleware" ai/main.py; then
    echo -e "${GREEN}✓ CORS configured${NC}"
else
    echo -e "${RED}✗ CORS not configured in main.py${NC}"
fi

# Check 9: API client exists
echo -n "Checking API client... "
if [ -f "frontend/src/lib/api.ts" ]; then
    echo -e "${GREEN}✓ api.ts exists${NC}"
else
    echo -e "${RED}✗ api.ts not found${NC}"
fi

echo ""
echo "=================================="
echo "Backend Test"
echo "=================================="
echo ""
echo "Testing backend connection..."
echo -n "Checking http://localhost:8000/health... "

# Test backend (if running)
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is running${NC}"
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null)
    echo "$HEALTH_RESPONSE"
else
    echo -e "${YELLOW}⚠ Backend not running${NC}"
    echo "  Start with: cd ai && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
fi

echo ""
echo "=================================="
echo "Summary"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. If backend not running: cd ai && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo "2. If frontend not running: cd frontend && npm run dev"
echo "3. Open http://localhost:8080"
echo ""
echo "For detailed instructions, see: START_HERE.md"
echo ""
