# RAG + OCR Document Intelligence System

A powerful **Retrieval-Augmented Generation (RAG)** system with **OCR capabilities** that allows users to upload documents and ask questions about their content using AI-powered natural language processing.

![System Architecture](https://img.shields.io/badge/Architecture-FastAPI%20%2B%20React-blue) ![AI](https://img.shields.io/badge/AI-LangChain%20%2B%20Azure%20OpenAI-green) ![OCR](https://img.shields.io/badge/OCR-Tesseract%20%2B%20Vision%20API-orange)

## 🌟 Features

### Core Capabilities
- **Multi-format Document Processing**: PDF, DOC/DOCX, PPTX, CSV/XLSX, TXT, Images (PNG, JPG, TIFF)
- **Intelligent OCR**: Extract text from scanned documents and images
- **Vector Search**: Semantic similarity search using Azure OpenAI embeddings
- **Hybrid Retrieval**: Combines semantic and keyword-based (BM25) search
- **Conversational AI**: Multi-turn conversations with context awareness
- **Multi-language Support**: English and Marathi language processing
- **Persistent Chat History**: SQLite-based conversation storage
- **User Management**: JWT-based authentication with role-based access

### Advanced Features
- **Auto-ingestion**: Automatically processes documents from `/backend/documents/` folder
- **Document Chunking**: Intelligent text splitting for optimal RAG performance
- **Conversation Management**: Create, rename, and manage multiple conversations
- **Admin Panel**: Complete document and user administration
- **Cross-platform OCR**: Works on Windows, macOS, and Linux

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   React Frontend│◄──►│   FastAPI Backend │◄──►│   Azure OpenAI  │
│   (Vite + Tailwind)│   │   (Python)       │    │   (GPT + Embeddings)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SQLite DB     │    │   Weaviate       │    │   Tesseract OCR │
│   (Users/Chats) │    │   (Vector Store) │    │   (Text Extract)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Technology Stack

**Backend:**
- **Framework**: FastAPI (Python)
- **AI/ML**: LangChain, Azure OpenAI, OpenAI
- **Vector Database**: Weaviate
- **OCR**: Tesseract, pdf2image, Pillow
- **Document Processing**: PyPDF2, python-docx, python-pptx, pandas
- **Database**: SQLite
- **Authentication**: JWT, bcrypt

**Frontend:**
- **Framework**: React 19 + Vite
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **Build Tools**: Vite, ESLint

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **Node.js 16+**
- **Tesseract OCR** (install via package manager)
- **Poppler-utils** (for PDF processing)
- **Azure OpenAI API Key** and endpoint

### Installation

1. **Clone and setup backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Setup frontend:**
```bash
cd ../frontend
npm install
```

3. **Configure environment:**
```bash
# Copy and edit .env file in backend/
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_VERSION=2023-12-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-35-turbo
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-ada-002

# Vector Database (Optional)
WEAVIATE_URL=your_weaviate_url
WEAVIATE_API_KEY=your_weaviate_key

# Web Search (Optional)
SERPAPI_API_KEY=your_serpapi_key

# JWT Secret
JWT_SECRET=your_jwt_secret_here
```

4. **Initialize admin user:**
```bash
cd backend
python -c "
from main import bootstrap_admin
import asyncio
asyncio.run(bootstrap_admin('admin', 'your_password'))
"
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API Key | ✅ |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | ✅ |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | GPT model deployment name | ✅ |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` | Embedding model deployment | ✅ |
| `WEAVIATE_URL` | Weaviate vector database URL | ❌ |
| `WEAVIATE_API_KEY` | Weaviate API key | ❌ |
| `SERPAPI_API_KEY` | SerpAPI key for web search | ❌ |
| `JWT_SECRET` | Secret for JWT token signing | ✅ |

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng poppler-utils
```

**macOS:**
```bash
brew install tesseract poppler
```

**Windows:**
Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki

## 📖 Usage

### Starting the Application

1. **Start Backend:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. **Start Frontend:**
```bash
cd frontend
npm run dev
```

3. **Access the application:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Basic Workflow

1. **Create Admin Account** (first-time setup)
2. **Login** to the system
3. **Upload Documents** (PDF, DOCX, images, etc.)
4. **Ask Questions** about your documents
5. **View Conversations** and manage chat history

### API Endpoints

#### Authentication
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/bootstrap_admin` - Create first admin

#### Documents
- `POST /upload_document` - Upload and process documents
- `POST /remove_document` - Remove uploaded documents
- `GET /documents` - List documents in conversation

#### Chat
- `POST /chat/text` - Send chat message
- `GET /history` - Get chat history
- `POST /clear_history` - Clear conversation history

#### Admin (Admin only)
- `GET /admin/inbuilt-documents` - List built-in documents
- `GET /admin/documents-folder` - List files in documents folder
- `POST /admin/documents-folder/delete` - Delete files from documents folder

## 📁 Project Structure

```
13. RAG + OCR/
├── backend/                 # Python FastAPI backend
│   ├── main.py             # Main application file
│   ├── requirements.txt     # Python dependencies
│   ├── .env               # Environment configuration
│   ├── app.db             # SQLite database
│   ├── documents/          # Auto-ingested documents
│   └── demo.py            # Demo/example scripts
├── frontend/               # React frontend
│   ├── src/
│   │   ├── App.jsx        # Main React component
│   │   ├── demo.jsx       # Demo interface
│   │   └── assets/        # Static assets
│   ├── package.json       # Node.js dependencies
│   └── index.html         # HTML template
└── README.md              # This file
```

## 🔍 Document Processing

### Supported File Types

| Format | Extension | Processing Method |
|--------|-----------|------------------|
| **PDF** | `.pdf` | PyPDFLoader + OCR fallback |
| **Word** | `.doc`, `.docx` | python-docx + legacy parser |
| **PowerPoint** | `.pptx` | python-pptx |
| **Excel/CSV** | `.xlsx`, `.csv` | pandas DataFrame processing |
| **Text** | `.txt` | Direct text reading |
| **Images** | `.png`, `.jpg`, `.tiff` | Tesseract OCR |

### OCR Capabilities

- **Text Extraction**: From scanned PDFs and images
- **Multi-page Support**: Processes multi-page documents
- **Language Detection**: Automatic language identification
- **Quality Enhancement**: Handles various image qualities

## 🤖 AI Features

### RAG Implementation
- **Document Chunking**: 500-character chunks with 50-character overlap
- **Vector Embeddings**: Azure OpenAI text-embedding-ada-002
- **Similarity Search**: Cosine similarity with BM25 hybrid
- **Context Window**: Includes conversation history for better responses

### Language Support
- **Primary**: English
- **Secondary**: Marathi (मराठी)
- **Auto-detection**: Automatic language detection for responses

## 🔐 Security

- **JWT Authentication**: Stateless token-based auth
- **Password Hashing**: PBKDF2 with salt
- **Role-based Access**: Admin vs User permissions
- **CORS Protection**: Configurable cross-origin policies
- **Input Validation**: Comprehensive request validation

## 🚀 Deployment

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build
```

### Production Considerations
- **Reverse Proxy**: Use Nginx for production
- **SSL/TLS**: Configure HTTPS certificates
- **Environment Variables**: Use secure secret management
- **Database Backups**: Regular SQLite backups
- **Monitoring**: Add logging and health checks

## 🛠️ Development

### Code Quality
- **Linting**: ESLint for JavaScript, custom rules for Python
- **Formatting**: Prettier for code formatting
- **Type Safety**: PropTypes for React components

### Testing
```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm run test
```

## 📚 API Documentation

Complete API documentation is available at `/docs` when running the backend server. The documentation includes:
- Interactive API testing interface
- Request/response schemas
- Authentication requirements
- Example requests

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the API documentation at `/docs`
- Review the demo interface for usage examples
- Examine the sample documents in `/backend/documents/`

## 🔄 Updates

This system supports:
- **Hot reloading** during development
- **Automatic document re-ingestion** on restart
- **Database migrations** for schema updates
- **Configuration changes** without restart

---

**Built with ❤️ using FastAPI, React, LangChain, and Azure OpenAI**
