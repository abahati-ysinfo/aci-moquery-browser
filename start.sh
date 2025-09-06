#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

SKIP_PREREQ_CHECK=false
DEV_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-prereq-check)
            SKIP_PREREQ_CHECK=true
            shift
            ;;
        --dev-mode)
            DEV_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --skip-prereq-check    Skip prerequisite checking"
            echo "  --dev-mode            Run in development mode (hot reload)"
            echo "  -h, --help            Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}🚀 ACI Moquery Log Browser - Automated Setup & Launch${NC}"
echo -e "${CYAN}============================================================${NC}"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

get_version() {
    local cmd="$1"
    local version_arg="${2:---version}"
    $cmd $version_arg 2>/dev/null | head -n1 || echo "Unknown"
}

if [ "$SKIP_PREREQ_CHECK" = false ]; then
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
    
    missing_prereqs=()
    
    if command_exists python3; then
        python_version=$(get_version python3 --version)
        echo -e "${GREEN}✅ Python3 found: $python_version${NC}"
        alias python=python3
    elif command_exists python; then
        python_version=$(get_version python --version)
        echo -e "${GREEN}✅ Python found: $python_version${NC}"
    else
        missing_prereqs+=("Python 3.11+")
        echo -e "${RED}❌ Python not found${NC}"
    fi
    
    if command_exists node; then
        node_version=$(get_version node --version)
        echo -e "${GREEN}✅ Node.js found: $node_version${NC}"
    else
        missing_prereqs+=("Node.js 20+")
        echo -e "${RED}❌ Node.js not found${NC}"
    fi
    
    if command_exists npm; then
        npm_version=$(get_version npm --version)
        echo -e "${GREEN}✅ npm found: $npm_version${NC}"
    else
        missing_prereqs+=("npm")
        echo -e "${RED}❌ npm not found${NC}"
    fi
    
    if command_exists poetry; then
        poetry_version=$(get_version poetry --version)
        echo -e "${GREEN}✅ Poetry found: $poetry_version${NC}"
    else
        echo -e "${YELLOW}⚠️  Poetry not found - attempting to install...${NC}"
        if curl -sSL https://install.python-poetry.org | python3 -; then
            export PATH="$HOME/.local/bin:$PATH"
            if command_exists poetry; then
                echo -e "${GREEN}✅ Poetry installed successfully${NC}"
            else
                missing_prereqs+=("Poetry (manual install required)")
            fi
        else
            missing_prereqs+=("Poetry (auto-install failed)")
            echo -e "${RED}❌ Poetry auto-install failed${NC}"
        fi
    fi
    
    if [ ${#missing_prereqs[@]} -gt 0 ]; then
        echo -e "\n${RED}❌ Missing prerequisites:${NC}"
        for prereq in "${missing_prereqs[@]}"; do
            echo -e "   - $prereq"
        done
        echo -e "\n${YELLOW}Please install the missing prerequisites and run this script again.${NC}"
        echo -e "${YELLOW}Or use --skip-prereq-check to bypass this check.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites found!${NC}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${YELLOW}📦 Setting up backend dependencies...${NC}"
cd backend

if [ ! -f "poetry.lock" ]; then
    echo -e "${CYAN}Installing backend dependencies (first time setup)...${NC}"
    poetry install
else
    echo -e "${CYAN}Backend dependencies already installed, checking for updates...${NC}"
    poetry install --no-dev
fi

cd ..

echo -e "\n${YELLOW}📦 Setting up frontend dependencies...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    echo -e "${CYAN}Installing frontend dependencies (first time setup)...${NC}"
    npm install
else
    echo -e "${CYAN}Frontend dependencies already installed, checking for updates...${NC}"
    npm install --no-audit
fi

cd ..

echo -e "\n${GREEN}🚀 Starting ACI Moquery Log Browser...${NC}"

if [ ! -d "data" ]; then
    mkdir -p data
    echo -e "${CYAN}Created data directory${NC}"
fi

cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down servers...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ All servers stopped. Thank you for using ACI Moquery Log Browser!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${CYAN}Starting backend server...${NC}"
cd backend

poetry run fastapi dev app/main.py --port 9000 &

BACKEND_PID=$!
cd ..

echo -e "${CYAN}Waiting for backend to initialize...${NC}"
sleep 3

if curl -s -f "http://127.0.0.1:9000/api/config" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend server is running on http://127.0.0.1:9000${NC}"
else
    echo -e "${YELLOW}⚠️  Backend may still be starting up...${NC}"
fi

echo -e "${CYAN}Starting frontend development server...${NC}"
cd frontend

npm run dev -- --port 3000 &
FRONTEND_PID=$!
cd ..

echo -e "${CYAN}Waiting for frontend to initialize...${NC}"
sleep 5

FRONTEND_URL="http://localhost:3000"
echo -e "${GREEN}✅ Frontend development server starting on $FRONTEND_URL${NC}"

echo -e "${CYAN}Opening browser...${NC}"
sleep 2

if command_exists open; then
    open "$FRONTEND_URL"
    echo -e "${GREEN}✅ Browser opened to $FRONTEND_URL${NC}"
elif command_exists xdg-open; then
    xdg-open "$FRONTEND_URL"
    echo -e "${GREEN}✅ Browser opened to $FRONTEND_URL${NC}"
else
    echo -e "${YELLOW}⚠️  Could not auto-open browser. Please manually navigate to: $FRONTEND_URL${NC}"
fi

echo -e "\n${GREEN}🎉 ACI Moquery Log Browser is now running!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "${CYAN}📍 Frontend URL: $FRONTEND_URL${NC}"
echo -e "${CYAN}📍 Backend URL: http://127.0.0.1:9000${NC}"
echo -e "${CYAN}📍 API Documentation: http://127.0.0.1:9000/docs${NC}"
echo -e "\n${WHITE}📋 Usage:${NC}"
echo -e "${WHITE}   1. Open frontend at http://localhost:3000${NC}"
echo -e "${WHITE}   2. Upload moquery files (.txt, .log, .7z, .zip, .tar.gz)${NC}"
echo -e "${WHITE}   3. Browse detected ACI classes in the sidebar${NC}"
echo -e "${WHITE}   4. View object details and export data${NC}"
echo -e "\n${YELLOW}⏹️  To stop: Press Ctrl+C in this window${NC}"

echo -e "\n${MAGENTA}🔧 Development Mode Active${NC}"
echo -e "${WHITE}   - Frontend: http://localhost:3000 (Hot-reload enabled)${NC}"
echo -e "${WHITE}   - Backend: http://127.0.0.1:9000 (Auto-reload enabled)${NC}"

echo -e "\n${YELLOW}Press Ctrl+C to stop all servers...${NC}"

while true; do
    sleep 1
    
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "\n${RED}❌ Backend server stopped unexpectedly!${NC}"
        if [ ! -z "$FRONTEND_PID" ]; then
            kill $FRONTEND_PID 2>/dev/null || true
        fi
        break
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "\n${RED}❌ Frontend server stopped unexpectedly!${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        break
    fi
done
