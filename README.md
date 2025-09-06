# ACI Moquery Log Browser

A local, offline application for ingesting and browsing ACI moquery log files. Built with FastAPI backend and React frontend, designed to run entirely on your local machine.

## Features

- **File Upload**: Drag & drop interface supporting .txt, .log, .7z, .zip, .tar.gz files (up to 200MB)
- **Stream-based Parsing**: XML-like class detection with regex patterns
- **SQLite Database**: Local storage with WAL mode for performance
- **Data Browser**: Interactive tables with pagination, filtering, and search
- **Object Details**: View attributes, relations, and raw XML data
- **Export**: CSV and JSON export functionality
- **Configuration**: Adjustable concurrency and batch size settings
- **Privacy-focused**: No external network calls, all data stays local

## Architecture

```
aci-moquery-browser/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── main.py      # FastAPI app with CORS
│   │   ├── models.py    # SQLAlchemy database models
│   │   ├── database.py  # SQLite configuration
│   │   ├── parser.py    # XML-like class detection
│   │   └── ingest.py    # Async file processing
│   └── pyproject.toml   # Poetry dependencies
├── frontend/         # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/  # UI components
│   │   ├── lib/        # API client & utilities
│   │   └── App.tsx     # Main application
│   └── package.json    # NPM dependencies
└── data/            # SQLite database (created on first run)
```

## Prerequisites

- **Python 3.11+** (with pip)
- **Node.js 20+** (with npm)
- **Poetry** (Python dependency manager)

### Install Prerequisites

**macOS:**
```bash
# Install Python 3.11+ via Homebrew
brew install python@3.11

# Install Node.js 20+ via Homebrew
brew install node@20

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

**Ubuntu/Debian:**
```bash
# Install Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-pip

# Install Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

**Windows:**
```powershell
# Install Python 3.11+ from python.org
# Install Node.js 20+ from nodejs.org
# Install Poetry
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

## Setup Instructions

1. **Extract the application:**
   ```bash
   unzip aci-moquery-browser.zip
   cd aci-moquery-browser
   ```

2. **Setup Backend:**
   ```bash
   cd backend
   poetry install
   cd ..
   ```

3. **Setup Frontend:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Running the Application

### 🚀 Option 1: Automated Setup & Launch (Recommended)

**Windows (PowerShell):**
```powershell
.\start.ps1
```

**macOS/Linux (Bash):**
```bash
./start.sh
```

These scripts will:
- ✅ Check and install prerequisites (Poetry, Node.js, npm)
- ✅ Install backend and frontend dependencies
- ✅ Start both servers automatically
- ✅ Open your browser to the application
- ✅ Handle all setup with one command!

**Script Options:**
```powershell
# Windows
.\start.ps1 -DevMode          # Development mode with hot-reload
.\start.ps1 -SkipPrereqCheck  # Skip prerequisite checking

# macOS/Linux  
./start.sh --dev-mode         # Development mode with hot-reload
./start.sh --skip-prereq-check # Skip prerequisite checking
```

### Option 2: Manual Setup (Advanced Users)

**Terminal 1 - Backend:**
```bash
cd backend
poetry run fastapi dev app/main.py
```
The backend will start at: http://127.0.0.1:8000

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```
The frontend will start at: http://localhost:5173

### Option 3: Production Build

**Build Frontend:**
```bash
cd frontend
npm run build
cd ..
```

**Run Backend (serves both API and frontend):**
```bash
cd backend
poetry run fastapi run app/main.py
```
Access the application at: http://127.0.0.1:8000

## Usage

1. **Open your browser** to http://localhost:5173 (development) or http://127.0.0.1:8000 (production)

2. **Upload Files:**
   - Click the "Upload" tab in the sidebar
   - Drag & drop or click to select moquery files
   - Supported formats: .txt, .log, .7z, .zip, .tar.gz (max 200MB each)

3. **Browse Data:**
   - Click the "Files" tab to see uploaded files
   - Expand files to view detected ACI classes
   - Click on classes to browse objects in the main area

4. **View Object Details:**
   - Click on any object row to see detailed attributes
   - Switch between Attributes, Relations, and Raw tabs
   - Use search, filtering, and sorting controls

5. **Export Data:**
   - Use CSV or JSON export buttons in the data browser
   - Exports current filtered/searched results

6. **Configuration:**
   - Click the "Config" tab to adjust settings
   - Modify concurrent ingests and batch sizes as needed

## Supported ACI Classes

The parser automatically detects XML-like tags using regex patterns. Common ACI classes include:

- **fvTenant** - Tenant configurations
- **fvAp** - Application profiles  
- **fvAEPg** - Application endpoint groups
- **fvBD** - Bridge domains
- **fabricNode** - Fabric nodes
- **l3extOut** - L3 external connections
- **vzBrCP** - Contracts
- **vzFilter** - Filters
- And many more...

## Database Schema

- **files**: Uploaded file metadata and processing status
- **classes**: Detected ACI classes per file with object counts
- **objects**: Individual ACI objects with DN, line numbers, and raw XML
- **attributes**: Key-value pairs for each object
- **relations**: DN-based relationships between objects
- **ingest_errors**: Parse errors with context for debugging

## Configuration Options

Adjust these settings in the Config panel:

- **Max Concurrent Ingests**: Number of files processed simultaneously (default: 2)
- **Batch Size**: Objects processed per database transaction (default: 2000)
- **Upload Chunk Size**: File upload chunk size (default: 8MB)
- **Max File Size**: Maximum file size limit (default: 200MB)

## Troubleshooting

**Backend won't start:**
- Ensure Python 3.11+ is installed: `python3 --version`
- Check Poetry installation: `poetry --version`
- Try: `cd backend && poetry install --no-cache`

**Frontend won't start:**
- Ensure Node.js 20+ is installed: `node --version`
- Try: `cd frontend && rm -rf node_modules && npm install`

**Upload fails:**
- Check file format is supported (.txt, .log, .7z, .zip, .tar.gz)
- Ensure file size is under 200MB
- Verify backend is running on port 8000

**No data appears:**
- Check browser console for errors (F12)
- Verify backend logs for parsing errors
- Try uploading a smaller test file first

## Development

**Backend Development:**
```bash
cd backend
poetry run fastapi dev app/main.py  # Auto-reload on changes
```

**Frontend Development:**
```bash
cd frontend
npm run dev  # Auto-reload on changes
```

**Run Tests:**
```bash
cd backend
poetry run pytest
```

## License

This tool is provided as-is for local ACI moquery log analysis. No warranty or support is provided.
