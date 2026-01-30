import os
import requests
import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Fix: Ensure API Key is None if it's empty or just whitespace (prevents warnings)
if not QDRANT_API_KEY or QDRANT_API_KEY.strip() == "":
    QDRANT_API_KEY = None

COLLECTION_NAME = "my_rag_collection"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 1. Initialize Embeddings
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_qdrant_client():
    """Create the specific client connection"""
    return QdrantClient(
        url=QDRANT_URL, 
        api_key=QDRANT_API_KEY, 
        prefer_grpc=False
    )

def get_vector_store():
    """Returns the vector store connected to Qdrant"""
    client = get_qdrant_client()
    
    # FIXED: Use QdrantVectorStore instead of Qdrant
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings, # Note: param name is 'embedding', not 'embeddings' in newer versions
    )

def create_collection_if_not_exists():
    """Ensures the collection exists in Qdrant before we add data"""
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )
        print(f"Created collection: {COLLECTION_NAME}")



def ingest_pdf(file_path):
    client = get_qdrant_client()
    
    # 1. DELETE existing collection (Wipe old PDF data)
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted old data from: {COLLECTION_NAME}")
    
    # 2. Re-create fresh collection
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
    )

    # 3. Load and Split PDF
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    
    # 4. Add NEW data
    vector_store = get_vector_store()
    vector_store.add_documents(texts)
    
    return f"Processed {len(texts)} new chunks. Old memory wiped."



def query_hybrid_rag(query, model_type):
    greetings = ["hi", "hello", "hey", "greetings", "sup", "what's up"]
    
    # If the user input is just a greeting, return a greeting immediately.
    if query.strip().lower().replace("!", "").replace(".", "") in greetings:
        return "Hello! I am ready to answer questions about your PDF. What would you like to know?"
   

    # 1. Retrieve Context (Normal RAG flow)
    vector_store = get_vector_store()
    
    docs = vector_store.similarity_search(query, k=3)
    
    if not docs:
        return "I couldn't find any relevant info in the PDF."

    context_text = "\n\n".join([doc.page_content for doc in docs])
    
    # 2. Construct Prompt
    final_prompt = f"Context from PDF:\n{context_text}\n\nUser Question: {query}\n\nAnswer:"
    
    # 3. Route to Model
    if model_type == 'cloud':
        return call_gemini(final_prompt)
    else:
        return call_ollama(final_prompt)

def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY not found in .env file."
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini Error: {str(e)}"

def call_ollama(prompt):
    try:
        # Assumes that Ollama is running on port 11434
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(url, json=payload)
        return response.json().get('response', "Error: No response from Ollama.")
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}. Is it running?"