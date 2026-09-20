import os
import time
import uuid
import traceback
import tempfile
import base64
import io
import sqlite3
from operator import itemgetter

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# LangChain / embeddings / LLM
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
import google.generativeai as genai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document, HumanMessage, AIMessage
from langchain_community.utilities import SerpAPIWrapper

# OCR / PDF -> image
from pdf2image import convert_from_path
from PIL import Image
import docx as docx_lib
from pptx import Presentation
# Machine-independent - no platform-specific imports needed

# Language detection
from langdetect import detect, LangDetectException
from langdetect.detector_factory import DetectorFactory

# Weaviate client v4
import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter


# Hybrid search
from rank_bm25 import BM25Okapi
import pandas as pd
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase

import numpy as np
import datetime
import secrets
import hashlib
from typing import Optional
import jwt
from fastapi import BackgroundTasks

DetectorFactory.seed = 0

# Load .env from backend directory (reliable regardless of cwd)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def _normalize_azure_endpoint(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")

# Gemini API config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Google Gemini configured successfully")
else:
    print("⚠️ GEMINI_API_KEY not set. Gemini integration will fail.")

# Weaviate config
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

# SerpAPI
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# JWT config
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGO = "HS256"

# Weaviate v4 client
client = None
try:
    if WEAVIATE_URL:
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=WEAVIATE_URL,
            auth_credentials=Auth.api_key(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None,
        )
        print("✅ Weaviate connected successfully")
    else:
        print("ℹ️ Weaviate not configured, running without vector database")
except Exception as e:
    print(f"⚠️ Weaviate connection failed: {e}")
    print("ℹ️ Running without vector database (BM25 search only)")
    client = None

# FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto-ingest will be triggered on startup event

# ------------------ SQLite persistence ------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL, -- 'user' or 'assistant'
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS uploaded_documents (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            name TEXT,
            file_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        """
    )
    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt BLOB NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','user')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Migration: add user_id to uploaded_documents if missing
    try:
        cur.execute("SELECT user_id FROM uploaded_documents LIMIT 1")
    except Exception:
        cur.execute("ALTER TABLE uploaded_documents ADD COLUMN user_id TEXT")
    
    # Migration: add user_id to conversations if missing
    try:
        cur.execute("SELECT user_id FROM conversations LIMIT 1")
    except Exception:
        cur.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
    
    # Migration: add title to conversations if missing
    try:
        cur.execute("SELECT title FROM conversations LIMIT 1")
    except Exception:
        cur.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
    
    conn.commit()
    conn.close()

def ensure_conversation(conversation_id: str | None, user_id: str | None = None) -> str:
    cid = conversation_id or str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO conversations(id, user_id) VALUES (?, ?)", (cid, user_id))
    conn.commit()
    conn.close()
    return cid

def add_message(conversation_id: str, role: str, content: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages(id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), conversation_id, role, content),
    )
    conn.commit()
    conn.close()

def get_chat_history(conversation_id: str, user_id: str = None):
    """Get chat history for a conversation, optionally filtered by user_id"""
    conn = get_db_connection()
    cur = conn.cursor()

    if user_id:
        # Verify the conversation belongs to the user
        cur.execute("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        if not cur.fetchone():
            conn.close()
            return []  # Return empty if conversation doesn't belong to user

    cur.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    )
    rows = cur.fetchall()
    conn.close()
    # Pair into [{user, assistant}]
    paired = []
    current = {}
    for row in rows:
        if row["role"] == "user":
            if current:
                paired.append(current)
            current = {"user": row["content"]}
        else:
            if current:
                current["assistant"] = row["content"]
                paired.append(current)
                current = {}
            else:
                paired.append({"user": "", "assistant": row["content"]})
    if current:
        paired.append(current)
    return paired

def get_user_conversations(user_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": row[0], "title": row[1], "created_at": row[2]} for row in rows]

def update_conversation_title(conversation_id: str, title: str, user_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?",
        (title, conversation_id, user_id),
    )
    conn.commit()
    conn.close()

def add_uploaded_document_record(conversation_id: str | None, doc_id: str, name: str, file_type: str, user_id: str | None = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO uploaded_documents(id, conversation_id, name, file_type, user_id) VALUES (?, ?, ?, ?, ?)",
        (doc_id, conversation_id, name, file_type, user_id),
    )
    conn.commit()
    conn.close()

def get_uploaded_documents(conversation_id: str, user_id: str = None):
    """Get uploaded documents for a conversation, optionally filtered by user_id"""
    conn = get_db_connection()
    cur = conn.cursor()

    if user_id:
        # Verify the conversation belongs to the user
        cur.execute("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        if not cur.fetchone():
            conn.close()
            return []  # Return empty if conversation doesn't belong to user

    cur.execute(
        "SELECT id, name FROM uploaded_documents WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"]} for r in rows]

def delete_uploaded_document_record(doc_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM uploaded_documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

def clear_messages(conversation_id: str, user_id: str = None):
    """Clear messages for a conversation, optionally filtered by user_id"""
    conn = get_db_connection()
    cur = conn.cursor()

    if user_id:
        # Verify the conversation belongs to the user
        cur.execute("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        if not cur.fetchone():
            conn.close()
            return False  # Return False if conversation doesn't belong to user

    cur.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return True

init_db()

# ------------------ Auth helpers (JWT) ------------------

SESSION_TTL_HOURS = 24

def hash_password(password: str, salt: bytes | None = None) -> tuple[str, bytes]:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex(), salt

def verify_password(password: str, password_hash_hex: str, salt: bytes) -> bool:
    dk_hex, _ = hash_password(password, salt)
    return secrets.compare_digest(dk_hex, password_hash_hex)

def create_jwt(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=SESSION_TTL_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def get_user_from_jwt(token: str | None):
    if not token:
        return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = data.get("sub")
        username = data.get("username")
        role = data.get("role")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {"id": row[0], "username": row[1], "role": row[2]}
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_user(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

# Globals
bm25 = None
bm25_corpus = []
bm25_docs = []
uploaded_docs = {}  # id -> docs or DataFrames

# Initialize Google Gemini embeddings
embedder = None
if GEMINI_API_KEY:
    embedder = GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDING_MODEL,
        google_api_key=GEMINI_API_KEY,
    )
else:
    print("⚠️ GEMINI_API_KEY not set. Embeddings will fail.")

# ------------------ Weaviate helpers (v4) ------------------

def ensure_weaviate_schema():
    if not client:
        return
    if not client.collections.exists("DocumentChunk"):
        client.collections.create(
            name="DocumentChunk",
            properties=[Property(name="text", data_type=DataType.TEXT)],
            vector_config=Configure.Vectors.self_provided(
                vector_index_config=Configure.VectorIndex.hfresh()
            ),
        )

def embed_and_index_docs(docs):
    if not embedder:
        raise RuntimeError("Google Gemini embeddings not configured")
    if not client:
        print("⚠️ Weaviate not available, skipping vector indexing")
        return None
    ensure_weaviate_schema()
    collection = client.collections.get("DocumentChunk")
    for doc in docs:
        vec = _embed_query_with_retry(doc.page_content)
        collection.data.insert(
            properties={"text": doc.page_content},
            vector=vec
        )
    return collection

def _embed_query_with_retry(text: str, retries: int = 3) -> list[float]:
    last_err = None
    for attempt in range(retries):
        try:
            return embedder.embed_query(text)
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(1)
    raise last_err

def retrieve_docs(query, k=4):
    if not embedder or not client:
        return []
    try:
        vec = _embed_query_with_retry(query)
        collection = client.collections.get("DocumentChunk")
        res = collection.query.near_vector(near_vector=vec, limit=k)
        return [Document(page_content=o.properties["text"]) for o in res.objects]
    except Exception as e:
        print(f"⚠️ Vector search failed, falling back to BM25 only: {e}")
        return []

def update_bm25_index(new_docs):
    global bm25, bm25_corpus, bm25_docs
    # Accumulate docs across uploads
    bm25_docs.extend(new_docs)
    bm25_corpus = [doc.page_content for doc in bm25_docs]
    if bm25_docs:
        bm25 = BM25Okapi([doc.page_content.split() for doc in bm25_docs])
    else:
        bm25 = None

def rerank_chunks(question, retrieved_docs):
    tokenized_question = question.split()
    scores = []
    for doc in retrieved_docs:
        if doc in bm25_docs:
            score = bm25.get_scores(tokenized_question)[bm25_docs.index(doc)]
        else:
            score = 0
        scores.append(score)
    scored_docs = sorted(zip(scores, retrieved_docs), key=itemgetter(0), reverse=True)
    return [doc for _, doc in scored_docs]

# ------------------ Auto-ingest documents folder ------------------

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")

def has_uploaded_document_named(name: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM uploaded_documents WHERE name = ? LIMIT 1", (name,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists

def ingest_documents_folder():
    if not os.path.isdir(DOCUMENTS_DIR):
        return
    for filename in os.listdir(DOCUMENTS_DIR):
        file_path = os.path.join(DOCUMENTS_DIR, filename)
        if not os.path.isfile(file_path):
            continue
        if has_uploaded_document_named(filename):
            continue
        ext = filename.split(".")[-1].lower()
        doc_id = str(uuid.uuid4())
        try:
            if ext == "pdf":
                docs = load_pdf(file_path)
                if not any(doc.page_content.strip() for doc in docs):
                    docs = load_scanned_pdf_with_ocr(file_path)
            elif ext in ("csv", "xls", "xlsx"):
                df = pd.read_csv(file_path) if ext == "csv" else pd.read_excel(file_path)
                rows_as_text = []
                preview_rows = min(len(df), 10000)
                columns = list(df.columns)
                for i in range(preview_rows):
                    row = df.iloc[i]
                    parts = []
                    for col in columns:
                        val = row[col]
                        val_str = "" if pd.isna(val) else str(val)
                        parts.append(f"{col}: {val_str}")
                    rows_as_text.append(" | ".join(parts))
                combined_text = "\n".join(rows_as_text)
                docs = load_text_as_docs(combined_text)
            elif ext == "txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                docs = load_text_as_docs(text)
            elif ext in ("doc", "docx"):
                if ext == "docx":
                    doc = docx_lib.Document(file_path)
                    text = "\n".join([para.text for para in doc.paragraphs])
                    docs = load_text_as_docs(text)
                else:
                    docs = load_doc_legacy(file_path)
            else:
                # Unsupported types are skipped silently
                continue

            # Image OCR
            if ext in ("png", "jpg", "jpeg", "tif", "tiff"):
                docs = ocr_image_file(file_path)
            # PPTX
            if ext == "pptx":
                docs = load_pptx(file_path)

            add_documents(docs, doc_id)
            add_uploaded_document_record(None, doc_id, filename, ext)
            print(f"✅ Ingested: {filename} ({len(docs)} chunks)")
        except Exception as e:
            print(f"❌ Failed to ingest {filename}: {e}")

def ingest_documents_folder_with_progress():
    """Same as ingest_documents_folder but with progress tracking"""
    if not os.path.isdir(DOCUMENTS_DIR):
        return
    
    files_to_process = []
    for filename in os.listdir(DOCUMENTS_DIR):
        file_path = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.isfile(file_path) and not has_uploaded_document_named(filename):
            files_to_process.append(filename)
    
    total_files = len(files_to_process)
    processed = 0
    
    for filename in files_to_process:
        file_path = os.path.join(DOCUMENTS_DIR, filename)
        ext = filename.split(".")[-1].lower()
        doc_id = str(uuid.uuid4())
        
        try:
            print(f"📄 Processing {processed + 1}/{total_files}: {filename}")
            
            if ext == "pdf":
                docs = load_pdf(file_path)
                if not any(doc.page_content.strip() for doc in docs):
                    print(f"   🔍 PDF appears to be scanned, using OCR...")
                    docs = load_scanned_pdf_with_ocr(file_path)
            elif ext in ("csv", "xls", "xlsx"):
                df = pd.read_csv(file_path) if ext == "csv" else pd.read_excel(file_path)
                rows_as_text = []
                preview_rows = min(len(df), 10000)
                columns = list(df.columns)
                for i in range(preview_rows):
                    row = df.iloc[i]
                    parts = []
                    for col in columns:
                        val = row[col]
                        val_str = "" if pd.isna(val) else str(val)
                        parts.append(f"{col}: {val_str}")
                    rows_as_text.append(" | ".join(parts))
                combined_text = "\n".join(rows_as_text)
                docs = load_text_as_docs(combined_text)
            elif ext == "txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                docs = load_text_as_docs(text)
            elif ext in ("doc", "docx"):
                if ext == "docx":
                    doc = docx_lib.Document(file_path)
                    text = "\n".join([para.text for para in doc.paragraphs])
                    docs = load_text_as_docs(text)
                else:
                    print(f"   🔧 Processing legacy .doc format...")
                    docs = load_doc_legacy(file_path)
            else:
                continue

            # Image OCR
            if ext in ("png", "jpg", "jpeg", "tif", "tiff"):
                print(f"   🔍 Using OCR for image...")
                docs = ocr_image_file(file_path)
            # PPTX
            if ext == "pptx":
                docs = load_pptx(file_path)

            add_documents(docs, doc_id)
            add_uploaded_document_record(None, doc_id, filename, ext)
            print(f"   ✅ Completed: {filename} ({len(docs)} chunks)")
            processed += 1
            
        except Exception as e:
            print(f"   ❌ Failed: {filename} - {e}")
            processed += 1

@app.on_event("startup")
async def startup_ingest():
    try:
        print("🚀 Starting document ingestion...")
        if not embedder:
            print("⚠️ Skipping document ingestion: Gemini embeddings not configured")
            return
        
        # Count total files first
        total_files = 0
        if os.path.isdir(DOCUMENTS_DIR):
            for filename in os.listdir(DOCUMENTS_DIR):
                file_path = os.path.join(DOCUMENTS_DIR, filename)
                if os.path.isfile(file_path) and not has_uploaded_document_named(filename):
                    total_files += 1
        
        print(f"📁 Found {total_files} documents to process...")
        
        # Process documents with progress feedback
        ingest_documents_folder_with_progress()
        
        print(f"✅ Document ingestion completed!")
    except Exception as _e:
        print(f"❌ Startup ingestion failed: {_e}")
        import traceback
        traceback.print_exc()

# ------------------ OCR ------------------

def encode_image(image_path):
    """Encode image file to base64 for Azure OpenAI vision API"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def encode_pil_image(page: Image.Image) -> str:
    """Encode a PIL image to base64 without writing to disk"""
    buffer = io.BytesIO()
    page.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def ocr_with_nanonets(image_path: str | None = None, page: Image.Image | None = None) -> str:
    """OCR using Google Gemini Vision API"""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured.")
    
    try:
        if page is not None:
            pil_img = page
        elif image_path:
            pil_img = Image.open(image_path)
        else:
            raise ValueError("Either image_path or page must be provided")
        
        vision_model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = (
            "Extract the text from the above document as if you were reading it naturally. "
            "Return the tables in html format. Return the equations in LaTeX representation. "
            "If there is an image in the document and image caption is not present, add a small "
            "description of the image inside the <img></img> tag; otherwise, add the image caption "
            "inside <img></img>. Watermarks should be wrapped in brackets. Ex: <watermark>OFFICIAL COPY</watermark>. "
            "Page numbers should be wrapped in brackets. Ex: <page_number>14</page_number>. "
            "Prefer using ☐ and ☑ for check boxes."
        )

        response = vision_model.generate_content([prompt, pil_img])
        return response.text if response and response.text else ""
    except Exception as e:
        print(f"Gemini OCR failed: {e}")
        return ""

def _convert_pdf_to_images(pdf_path: str, poppler_path: str | None = None):
    """Convert PDF pages to images using a cross-platform temp directory."""
    import shutil

    output_folder = tempfile.mkdtemp(prefix="pdf2image_")
    try:
        kwargs = {"output_folder": output_folder}
        if poppler_path:
            kwargs["poppler_path"] = poppler_path
        pages = convert_from_path(pdf_path, **kwargs)
        # Copy into memory so temp files can be removed safely on Windows
        return [page.copy() for page in pages]
    except Exception:
        return None
    finally:
        shutil.rmtree(output_folder, ignore_errors=True)

def load_scanned_pdf_with_ocr(pdf_path):
    """
    Machine-independent PDF to image conversion.
    Tries multiple methods to find poppler automatically.
    """
    pages = None
    
    # Method 1: Try without specifying poppler path (uses system PATH)
    pages = _convert_pdf_to_images(pdf_path)
    
    # Method 2: Try common installation paths across different systems
    if pages is None:
        possible_paths = [
            "/opt/homebrew/bin",      # macOS Homebrew
            "/usr/local/bin",          # Common Unix/Linux
            "/opt/local/bin",          # macOS MacPorts
            "/usr/bin",                # Standard Unix
            "/bin",                    # Standard Unix
            "C:\\poppler\\bin",        # Windows
            "C:\\Program Files\\poppler\\bin",  # Windows
            "C:\\poppler-25.07.0\\Library\\bin",  # Windows (common zip install)
        ]
        
        for path in possible_paths:
            pages = _convert_pdf_to_images(pdf_path, poppler_path=path)
            if pages is not None:
                break
    
    # Method 3: Try to find poppler in PATH using which/where
    if pages is None:
        try:
            import shutil
            poppler_exe = shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")
            if poppler_exe:
                poppler_dir = os.path.dirname(poppler_exe)
                pages = _convert_pdf_to_images(pdf_path, poppler_path=poppler_dir)
        except Exception:
            pass
    
    if pages is None:
        # Final fallback - return a document indicating the issue
        error_text = f"PDF: {os.path.basename(pdf_path)} - Could not convert to images for OCR. Please ensure poppler-utils is installed."
        return load_text_as_docs(error_text)
    
    all_text = ""
    for i, page in enumerate(pages):
        try:
            page_text = ocr_with_nanonets(page=page)
        except Exception as e:
            print(f"Nanonets OCR failed on page {i}: {e}")
            page_text = ""
        
        all_text += f"\n--- PAGE {i+1} ---\n{page_text}"
    
    docs = [Document(page_content=all_text)]
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_documents(docs)

def ocr_image_file(image_path: str):
    text = ocr_with_nanonets(image_path)
    return load_text_as_docs(text)

# ------------------ PDF Loader ------------------

from langchain_community.document_loaders import PyPDFLoader

def load_pdf(file_path):
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_documents(docs)

def load_text_as_docs(text: str):
    base_doc = Document(page_content=text)
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_documents([base_doc])

def load_pptx(file_path: str):
    prs = Presentation(file_path)
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                texts.append(shape.text)
    combined = "\n".join(texts)
    return load_text_as_docs(combined)

def load_doc_legacy(file_path: str):
    """
    Machine-independent .doc file processing using pure Python methods.
    No external dependencies required.
    """
    try:
        # Method 1: Try to read as binary and extract text using basic parsing
        # This is a simplified approach that works for many .doc files
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Look for text patterns in the binary content
        # This is a basic text extraction method
        import re
        
        # Try to extract readable text from the binary content
        # Remove null bytes and control characters
        text_content = content.decode('latin-1', errors='ignore')
        
        # Clean up the text
        text_content = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text_content)
        text_content = re.sub(r'\s+', ' ', text_content)
        
        # If we got some reasonable text, use it
        if len(text_content.strip()) > 50:  # Minimum threshold for valid content
            return load_text_as_docs(text_content.strip())
        
        # Method 2: Try using python-docx as a fallback (sometimes works with .doc)
        try:
            doc = docx_lib.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            if text.strip():
                return load_text_as_docs(text)
        except Exception:
            pass
        
        # Method 3: Try to extract text using basic string operations
        # Look for common document patterns
        try:
            # Convert to string and look for readable text blocks
            text_parts = []
            lines = text_content.split('\n')
            
            for line in lines:
                line = line.strip()
                # Keep lines that look like readable text
                if (len(line) > 10 and 
                    not all(c in ' \t\n\r' for c in line) and
                    any(c.isalpha() for c in line)):
                    text_parts.append(line)
            
            if text_parts:
                combined_text = '\n'.join(text_parts)
                return load_text_as_docs(combined_text)
        except Exception:
            pass
        
        # If all methods fail, return a placeholder document
        placeholder_text = f"Document: {os.path.basename(file_path)} - Content could not be extracted. Please convert to .docx format for better text extraction."
        return load_text_as_docs(placeholder_text)
        
    except Exception as e:
        # Final fallback - return a document with error information
        error_text = f"Document: {os.path.basename(file_path)} - Error processing .doc file: {str(e)}. Please convert to .docx format."
        return load_text_as_docs(error_text)

# ------------------ Add/Remove ------------------

def add_documents(docs, doc_id):
    if not docs:
        raise ValueError("No document chunks to index.")
    if embedder:
        embed_and_index_docs(docs)
    else:
        print("⚠️ Skipping vector indexing: Gemini embeddings not configured")
    update_bm25_index(docs)
    uploaded_docs[doc_id] = docs


def remove_documents(doc_id, allow_builtin: bool = False):
    # Guard: do not allow removing built-in documents (ingested at startup) unless allowed
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT conversation_id FROM uploaded_documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        conn.close()
        if row is not None and (row[0] is None or row[0] == "") and not allow_builtin:
            return False
    except Exception:
        pass
    if doc_id in uploaded_docs:
        docs = uploaded_docs[doc_id]
        del uploaded_docs[doc_id]

        if client:
            collection = client.collections.use("DocumentChunk")  # get collection
            for doc in docs:
                # Delete objects where "text" equals the page content
                collection.data.delete_many(
                    where=Filter.by_property("text").equal(doc.page_content)
                )
        # Rebuild BM25 from remaining uploaded docs
        remaining_docs = []
        for _did, _docs in uploaded_docs.items():
            if isinstance(_docs, list):
                remaining_docs.extend(_docs)
        global bm25, bm25_corpus, bm25_docs
        bm25_docs = remaining_docs
        bm25_corpus = [d.page_content for d in bm25_docs]
        if bm25_docs:
            bm25 = BM25Okapi([d.page_content.split() for d in bm25_docs])
        else:
            bm25 = None
        return True
    return False

# ------------------ Endpoints ------------------

@app.post("/upload_document")
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    current_user: dict = Depends(require_user),
):
    ext = file.filename.split(".")[-1].lower()
    doc_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    # Ensure conversation exists if provided
    conversation_id = ensure_conversation(conversation_id, current_user["id"])

    if ext == "pdf":
        docs = load_pdf(tmp_path)
        if not any(doc.page_content.strip() for doc in docs):
            docs = load_scanned_pdf_with_ocr(tmp_path)
        add_documents(docs, doc_id)
        add_uploaded_document_record(conversation_id, doc_id, file.filename, ext, user_id=current_user["id"])
        return {"message": "PDF processed", "document_id": doc_id}
    elif ext in ("png", "jpg", "jpeg", "tif", "tiff"):
        docs = ocr_image_file(tmp_path)
        add_documents(docs, doc_id)
        add_uploaded_document_record(conversation_id, doc_id, file.filename, ext, user_id=current_user["id"])
        return {"message": "Image processed", "document_id": doc_id}
    elif ext in ("csv", "xls", "xlsx"):
        df = pd.read_csv(tmp_path) if ext == "csv" else pd.read_excel(tmp_path)
        # Convert rows to compact text for RAG indexing
        rows_as_text = []
        preview_rows = min(len(df), 10000)
        columns = list(df.columns)
        for i in range(preview_rows):
            row = df.iloc[i]
            parts = []
            for col in columns:
                val = row[col]
                val_str = "" if pd.isna(val) else str(val)
                parts.append(f"{col}: {val_str}")
            rows_as_text.append(" | ".join(parts))
        combined_text = "\n".join(rows_as_text)
        docs = load_text_as_docs(combined_text)
        add_documents(docs, doc_id)
        uploaded_docs[doc_id] = docs
        add_uploaded_document_record(conversation_id, doc_id, file.filename, ext, user_id=current_user["id"])
        return {"message": "Tabular file indexed", "document_id": doc_id}
    elif ext == "txt":
        with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        docs = load_text_as_docs(text)
        add_documents(docs, doc_id)
        add_uploaded_document_record(conversation_id, doc_id, file.filename, ext, user_id=current_user["id"])
        return {"message": "Text file processed", "document_id": doc_id}
    elif ext in ("doc", "docx"):
        try:
            if ext == "docx":
                doc = docx_lib.Document(tmp_path)
                text = "\n".join([para.text for para in doc.paragraphs])
                docs = load_text_as_docs(text)
            else:
                docs = load_doc_legacy(tmp_path)
            
                add_documents(docs, doc_id)
                add_uploaded_document_record(conversation_id, doc_id, file.filename, ext, user_id=current_user["id"])
            return {"message": f"{ext.upper()} processed", "document_id": doc_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process Word document: {str(e)}")
    elif ext == "pptx":
        docs = load_pptx(tmp_path)
        add_documents(docs, doc_id)
        add_uploaded_document_record(conversation_id, doc_id, file.filename, ext, user_id=current_user["id"])
        return {"message": "PPTX processed", "document_id": doc_id}
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

@app.post("/chat/text")
async def chat_text(
    query: str = Form(...),
    search_online: bool = Form(False),
    conversation_id: str | None = Form(None),
    current_user: dict = Depends(require_user),
):
    # Ensure conversation
    conversation_id = ensure_conversation(conversation_id, current_user["id"])

    # Detect language
    detected_language = detect(query) if query else "en"
    system_prompt_text = "उत्तर फक्त मराठीत द्या." if detected_language == "mr" else "You are a helpful AI assistant. Answer questions clearly and helpfully based on the provided context. You can refer to previous conversation history when relevant. Be conversational and engaging like ChatGPT."

    # Retrieve docs
    docs_embedding = retrieve_docs(query) if client else []
    docs_bm25 = []
    if bm25:
        scores = bm25.get_scores(query.split())
        top_idx = np.argsort(scores)[-4:][::-1]
        docs_bm25 = [bm25_docs[i] for i in top_idx]

    combined_docs = list({doc.page_content: doc for doc in docs_embedding + docs_bm25}.values())
    if combined_docs and bm25:
        combined_docs = rerank_chunks(query, combined_docs)

    # Get chat history for context
    chat_history = get_chat_history(conversation_id)

    # Combine document content
    context = "\n".join([doc.page_content for doc in combined_docs])

    # Build conversation context from chat history
    conversation_context = ""
    if chat_history:
        conversation_context = "\n".join([
            f"User: {msg.get('user', '')}\nAssistant: {msg.get('assistant', '')}" 
            for msg in chat_history[-6:]  # Last 6 exchanges for context
        ])

    # Combine document context with conversation context
    if context.strip() and conversation_context.strip():
        context = f"Document Context:\n{context}\n\nPrevious Conversation:\n{conversation_context}"
    elif conversation_context.strip():
        # Use conversation context if no documents
        context = f"Previous Conversation:\n{conversation_context}"
    
    try:
        # If no context at all, still try to answer based on general knowledge
        if not context.strip():
            # Use a more general prompt for questions without specific context
            human_input = f"""
Question: {query}

Please answer this question based on your general knowledge. If you're not sure about something, please say so.
"""
            
            # Create a simple chain without document context
            model = ChatGoogleGenerativeAI(
                model=GEMINI_MODEL,
                google_api_key=GEMINI_API_KEY,
                temperature=0.7,
            )
            
            answer_obj = model.invoke(human_input)
            answer = answer_obj.content
        else:
            # Use the normal document-based flow
            # Prepare chat prompt
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_text),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

            # Initialize model
            model = ChatGoogleGenerativeAI(
                model=GEMINI_MODEL,
                google_api_key=GEMINI_API_KEY,
                temperature=0.7,
            )

            human_input = f"""
Context:
{context}

Question:
{query}

Instructions: Answer the question based on the context above, which may include uploaded documents or our previous conversation. 
If the context doesn't contain relevant information to answer the question, please say so. You can refer to our previous conversation if it's relevant to the current question.
"""

            # Invoke the model with memory
            final_chain = chat_prompt | model
            answer_obj = final_chain.invoke({
                "history": [],
                "input": human_input
            })
            answer = answer_obj.content
    except Exception as e:
        err_name = type(e).__name__
        if "Connection" in err_name or "Connect" in str(e):
            raise HTTPException(
                status_code=503,
                detail="Could not reach Gemini API. Check your internet connection and GEMINI_API_KEY in .env, then restart the server.",
            ) from e
        raise

    # Persist messages
    add_message(conversation_id, "user", query)
    add_message(conversation_id, "assistant", answer)
    chat_history = get_chat_history(conversation_id, current_user["id"])

    return {
        "question": query,
        "answer": answer,
        "references": [doc.page_content for doc in combined_docs] if combined_docs else [],
        "chat_history": chat_history,
        "conversation_id": conversation_id,
    }

@app.post("/remove_document")
async def remove_document_endpoint(document_id: str = Form(...), authorization: Optional[str] = Header(None)):
    # Identify current user
    user = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        user = get_user_from_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Load ownership and built-in status
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, conversation_id FROM uploaded_documents WHERE id = ?", (document_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"message": "Document record removed (not found)."}
    owner_user_id, conv_id = row
    is_builtin = (conv_id is None or conv_id == "")

    # Permission checks: admin can remove anything; user can remove only own non-built-in
    if user["role"] != "admin":
        if is_builtin:
            raise HTTPException(status_code=403, detail="Only admin can remove built-in documents.")
        if owner_user_id != user["id"]:
            raise HTTPException(status_code=403, detail="You can remove only your own documents.")

    success = remove_documents(document_id, allow_builtin=(user["role"] == "admin"))
    if not success:
        # Document not present in in-memory index (e.g., after restart). Still remove DB record.
        delete_uploaded_document_record(document_id)
        return {"message": "Document record removed (not found in current index)."}
    delete_uploaded_document_record(document_id)
    return {"message": "Document removed successfully."}

@app.get("/status")
async def status():
    return {"status": "running", "docs_uploaded": len(uploaded_docs)}

# ------------------ History/Documents retrieval ------------------

@app.get("/conversations/current")
async def get_current_conversation(current_user: dict = Depends(require_user)):
    """Get or create the current conversation for the user"""
    conversations = get_user_conversations(current_user["id"])
    if conversations:
        # Return the most recent conversation
        conversation_id = conversations[0]["id"]
    else:
        # Create a new conversation
        conversation_id = ensure_conversation(None, current_user["id"])
    
    return {
        "conversation_id": conversation_id,
        "chat_history": get_chat_history(conversation_id, current_user["id"])
    }

@app.get("/history")
async def get_history(conversation_id: str = Query(...), current_user: dict = Depends(require_user)):
    ensure_conversation(conversation_id, current_user["id"])
    return {"conversation_id": conversation_id, "chat_history": get_chat_history(conversation_id, current_user["id"])}

@app.get("/documents")
async def list_documents(conversation_id: str = Query(...), current_user: dict = Depends(require_user)):
    ensure_conversation(conversation_id, current_user["id"])
    return {"conversation_id": conversation_id, "documents": get_uploaded_documents(conversation_id, current_user["id"])}

@app.post("/clear_history")
async def clear_history(conversation_id: str = Form(...), current_user: dict = Depends(require_user)):
    ensure_conversation(conversation_id, current_user["id"])
    success = clear_messages(conversation_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=403, detail="You can only clear your own conversations")
    return {"message": "History cleared.", "conversation_id": conversation_id}

# ------------------ Admin-only: list built-in documents ------------------

@app.get("/admin/inbuilt-documents")
async def list_inbuilt_documents(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, created_at FROM uploaded_documents WHERE (conversation_id IS NULL OR conversation_id = '') AND (user_id IS NULL OR user_id = '') ORDER BY created_at ASC")
    rows = cur.fetchall()
    conn.close()
    return {"documents": [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]}

# ------------------ Admin-only: documents folder management ------------------

@app.get("/admin/documents-folder")
async def list_documents_folder(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not os.path.isdir(DOCUMENTS_DIR):
        return {"files": []}
    files = []
    for fn in os.listdir(DOCUMENTS_DIR):
        fp = os.path.join(DOCUMENTS_DIR, fn)
        if os.path.isfile(fp):
            try:
                size = os.path.getsize(fp)
            except Exception:
                size = None
            files.append({"name": fn, "size": size})
    return {"files": files}

@app.post("/admin/documents-folder/delete")
async def delete_documents_folder_file(filename: str = Form(...), authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    # Resolve path safely within DOCUMENTS_DIR
    target_path = os.path.normpath(os.path.join(DOCUMENTS_DIR, filename))
    if not target_path.startswith(os.path.normpath(DOCUMENTS_DIR) + os.sep):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Find any ingested records for this filename (built-in only) and remove from vector store + DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM uploaded_documents WHERE name = ? AND (conversation_id IS NULL OR conversation_id = '')", (filename,))
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        did = r[0] if isinstance(r, tuple) else r["id"]
        try:
            remove_documents(did, allow_builtin=True)
        except Exception:
            pass
        delete_uploaded_document_record(did)

    # Delete the physical file
    try:
        os.remove(target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
    return {"message": "File deleted and index cleaned"}

# ------------------ Auth Endpoints ------------------

@app.post("/auth/bootstrap_admin")
async def bootstrap_admin(username: str = Form(...), password: str = Form(...)):
    # Allow only if no admin exists
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    count = cur.fetchone()[0]
    if count and count > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Admin already exists")
    pw_hash, salt = hash_password(password)
    user_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO users(id, username, password_hash, salt, role) VALUES (?, ?, ?, ?, 'admin')",
        (user_id, username, pw_hash, salt),
    )
    conn.commit()
    conn.close()
    token = create_jwt(user_id, username, "admin")
    return {"message": "Admin created", "token": token}

@app.post("/auth/register")
async def register_user(username: str = Form(...), password: str = Form(...)):
    pw_hash, salt = hash_password(password)
    user_id = str(uuid.uuid4())
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users(id, username, password_hash, salt, role) VALUES (?, ?, ?, ?, 'user')",
            (user_id, username, pw_hash, salt),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    conn.close()
    return {"message": "User registered", "user_id": user_id}

@app.post("/auth/login")
async def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, salt FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_id, password_hash_hex, salt = row
    if not verify_password(password, password_hash_hex, salt):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
    urow = cur.fetchone()
    conn.close()
    token = create_jwt(user_id, urow[0], urow[1])
    return {"message": "Logged in", "token": token}

@app.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    return {"message": "Logged out"}

@app.get("/me")
async def me(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

@app.get("/my/documents")
async def my_documents(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, created_at FROM uploaded_documents WHERE user_id = ? ORDER BY created_at ASC", (user["id"],))
    rows = cur.fetchall()
    conn.close()
    return {"documents": [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]}

@app.get("/my/conversations")
async def my_conversations(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    user = get_user_from_jwt(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conversations = get_user_conversations(user["id"])
    return {"conversations": conversations}

@app.post("/conversations/rename")
async def rename_conversation(
    conversation_id: str = Form(...),
    title: str = Form(...),
    current_user: dict = Depends(require_user)
):
    update_conversation_title(conversation_id, title, current_user["id"])
    return {"message": "Conversation renamed successfully"}

# ------------------ User Statistics Endpoints ------------------

def get_user_document_stats(user_id: str | None = None):
    """Get document statistics for a specific user or all users"""
    conn = get_db_connection()
    cur = conn.cursor()

    if user_id:
        # Get stats for a specific user
        cur.execute("""
            SELECT u.username, u.role, COUNT(ud.id) as doc_count,
                   GROUP_CONCAT(ud.name, ', ') as document_names,
                   MAX(ud.created_at) as last_upload
            FROM users u
            LEFT JOIN uploaded_documents ud ON u.id = ud.user_id
            WHERE u.id = ?
            GROUP BY u.id, u.username, u.role
        """, (user_id,))
    else:
        # Get stats for all users
        cur.execute("""
            SELECT u.username, u.role, COUNT(ud.id) as doc_count,
                   GROUP_CONCAT(ud.name, ', ') as document_names,
                   MAX(ud.created_at) as last_upload
            FROM users u
            LEFT JOIN uploaded_documents ud ON u.id = ud.user_id
            GROUP BY u.id, u.username, u.role
            ORDER BY u.username
        """)

    rows = cur.fetchall()
    conn.close()

    # Convert to more readable format
    stats = []
    for row in rows:
        document_names = row[3].split(', ') if row[3] else []

        stats.append({
            "username": row[0],
            "role": row[1],
            "document_count": row[2],
            "document_names": document_names,
            "last_upload": row[4]
        })

    return stats

def get_user_activity_summary():
    """Get a summary of user activity across the system"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Get overall statistics
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'user'", ())
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'", ())
    total_admins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM uploaded_documents", ())
    total_documents = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM conversations", ())
    total_conversations = cur.fetchone()[0]

    # Get recent activity (last 7 days)
    cur.execute("""
        SELECT COUNT(*) FROM uploaded_documents
        WHERE created_at >= datetime('now', '-7 days')
    """)
    recent_uploads = cur.fetchone()[0]

    conn.close()

    return {
        "total_users": total_users,
        "total_admins": total_admins,
        "total_documents": total_documents,
        "total_conversations": total_conversations,
        "recent_uploads_7d": recent_uploads
    }

@app.get("/admin/user-stats")
async def get_all_user_stats(current_user: dict = Depends(require_user)):
    """Admin endpoint to view all users and their document statistics"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        user_stats = get_user_document_stats()
        activity_summary = get_user_activity_summary()

        return {
            "success": True,
            "activity_summary": activity_summary,
            "users": user_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user stats: {str(e)}")

@app.get("/my/stats")
async def get_my_stats(current_user: dict = Depends(require_user)):
    """Get current user's document statistics"""
    try:
        user_stats = get_user_document_stats(current_user["id"])
        activity_summary = get_user_activity_summary()

        # Filter to only show current user's stats
        my_stats = user_stats[0] if user_stats else {
            "username": current_user["username"],
            "role": current_user["role"],
            "document_count": 0,
            "document_names": [],
            "last_upload": None
        }

        return {
            "success": True,
            "activity_summary": activity_summary,
            "my_stats": my_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user stats: {str(e)}")

@app.get("/users/overview")
async def get_users_overview(current_user: dict = Depends(require_user)):
    """Get a general overview of all users (usernames and basic stats only)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get basic user info without sensitive data
        cur.execute("""
            SELECT u.username, u.role, COUNT(ud.id) as doc_count,
                   MAX(u.created_at) as joined_date
            FROM users u
            LEFT JOIN uploaded_documents ud ON u.id = ud.user_id
            GROUP BY u.id, u.username, u.role
            ORDER BY u.username
        """)

        rows = cur.fetchall()
        conn.close()

        users = []
        for row in rows:
            users.append({
                "username": row[0],
                "role": row[1],
                "document_count": row[2],
                "joined_date": row[3]
            })

        activity_summary = get_user_activity_summary()

        return {
            "success": True,
            "activity_summary": activity_summary,
            "users": users
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving users overview: {str(e)}")
