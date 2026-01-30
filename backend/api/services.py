import os
import shutil
import lancedb
import boto3
from google import genai
from google.genai import types
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from api.models import Document
from django.conf import settings
from botocore.config import Config

# Configure Gemini
def get_client():
    if os.getenv('GOOGLE_API_KEY'):
        return genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
    return None

def get_embedding(text):
    """
    Generate embedding using Gemini model.
    """
    client = get_client()
    if not client:
        return None

    try:
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                title="Chatbot Document Chunk"
            )
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def get_vector_db():
    """
    Connect to LanceDB on S3.
    """
    bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
    
    if bucket_name:
        # S3 Connection
        # URI format: s3://bucket/path
        uri = f"s3://{bucket_name}/vectors"
        # LanceDB automatically picks up AWS credentials from env vars (AWS_ACCESS_KEY_ID etc)
        # We don't need to manually pass boto3 session if env vars are set.
        return lancedb.connect(uri)
    else:
        # Fallback to local
        return lancedb.connect("./lancedb_data")

def get_or_create_table(db, table_name="documents"):
    """
    Get or create the vector table.
    """
    try:
        if table_name in db.table_names():
            return db.open_table(table_name)
        
        # Define schema implicitly by adding first record or explicitly if needed.
        # For simplicity, we'll let it infer or create empty if supported.
        # LanceDB requires data to create a table usually, or a pyarrow schema.
        # We will handle creation in process_document if it doesn't exist.
        return None
    except Exception as e:
        print(f"Error getting table: {e}")
        return None

def process_document(document_id):
    """
    Reads the document file, splits it into chunks, generates embeddings,
    and stores them in S3 via LanceDB.
    """
    if not os.getenv('GOOGLE_API_KEY'):
        return False, "Missing API Key"

    try:
        doc = Document.objects.get(id=document_id)
        
        # 1. Load Document content
        # doc.file.open() handles S3 or local automatically thanks to django-storages
        try:
            doc.file.open('rb')
            file_content = doc.file.read()
            doc.file.close()
        except Exception as e:
            return False, f"Could not read file: {e}"

        text = ""
        # Simple extraction based on extension
        filename = doc.file.name.lower()
        
        if filename.endswith('.pdf'):
            # For PDF, we might need a temp file for PyPDFLoader or use a stream parser
            # PyPDFLoader usually requires a file path.
            # We will save to a temp file.
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
            
            try:
                loader = PyPDFLoader(tmp_path)
                pages = loader.load()
                text = "\n".join([p.page_content for p in pages])
            finally:
                os.unlink(tmp_path)
                
        else:
            # Text/MD
            try:
                text = file_content.decode('utf-8')
            except:
                text = str(file_content)

        if not text.strip():
             return False, "Empty document text"

        text = text.replace('\x00', '')

        # 2. Split Text
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        chunks = text_splitter.split_text(text)
        
        # 3. Generate Embeddings & Prepare Data
        data = []
        for i, chunk_text in enumerate(chunks):
            embedding = get_embedding(chunk_text)
            if embedding:
                data.append({
                    "vector": embedding,
                    "text": chunk_text,
                    "document_id": doc.id,
                    "chunk_index": i,
                    "title": doc.title
                })
        
        if not data:
             return False, "No embeddings generated"

        # 4. Save to LanceDB (S3)
        db = get_vector_db()
        table_name = "documents"
        
        if table_name in db.table_names():
            table = db.open_table(table_name)
            table.add(data)
        else:
            # Create a table
            db.create_table(table_name, data=data)

        # Update processed status
        doc.is_processed = True
        doc.save()

        return True, len(data)
        
    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, str(e)

def search_documents(query, user, limit=5):
    """
    Search for relevant document chunks using LanceDB on S3.
    """
    client = get_client()
    if not client:
        return []

    try:
        # Generate embedding for the query
        query_result = client.models.embed_content(
            model="text-embedding-004",
            contents=query,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        query_embedding = query_result.embeddings[0].values
        
        # Connect to DB
        db = get_vector_db()
        if "documents" not in db.table_names():
            return []
            
        table = db.open_table("documents")
        
        # Get User's Document IDs first to filter in LanceDB
        # LanceDB SQL filtering is powerful but let's be explicit
        user_doc_ids = list(Document.objects.filter(user=user).values_list('id', flat=True))
        
        if not user_doc_ids:
            return []
            
        # Search
        # Filter syntax: "document_id IN (1, 2, 3)"
        # Note: Large lists in SQL string might be slow, but fine for prototype.
        id_list = ", ".join(map(str, user_doc_ids))
        
        results = table.search(query_embedding) \
            .where(f"document_id IN ({id_list})") \
            .limit(limit) \
            .to_list()
            
        # Convert to object-like structure for compatibility with views
        class ChunkResult:
            def __init__(self, data):
                self.content = data['text']
                self.document = Document(id=data['document_id'], title=data['title'])
                
        return [ChunkResult(r) for r in results]

    except Exception as e:
        print(f"Error searching documents: {e}")
        return []

def generate_chat_response(message_history, user_query, user):
    """
    Generate response using Gemini Flash model with RAG.
    """
    client = get_client()
    if not client:
        return "Error: GOOGLE_API_KEY is missing.", []

    try:
        # 1. Search for relevant context
        relevant_chunks = search_documents(user_query, user)
        context_str = "\n\n".join([f"Document: {c.document.title}\n{c.content}" for c in relevant_chunks])
        
        if not context_str:
            context_str = "No relevant documents found."

        # 2. Construct System Instruction
        system_instruction = (
            "You are a helpful and intelligent assistant named 'Nexus'. "
            "You have access to the user's uploaded documents via the Context provided below. "
            "Always prioritize the information in the Context when answering. "
            "If the Context contains the answer, cite the information using the Document Name provided in the header (e.g., '**Document: Filename.pdf**'). "
            "If the Context does not contain the answer, you can answer from your general knowledge, "
            "but explicitly state that you couldn't find it in the uploaded documents. "
            "Be concise and professional. "
            "If user says hi or hello greet them with 'Hello! How can I help you today?'.\n\n"
            "CRITICAL INSTRUCTION: at the very end of your response, on a new line, you MUST list the exact titles of the documents from the Context that you actually used to answer the question. "
            "Format the line exactly as: 'USED_SOURCES: title1, title2'. "
            "If you didn't use any documents from the context, write 'USED_SOURCES: NONE'. "
            "Do not include this line if you are just greeting."
        )

        # 3. Format Chat History
        contents = []
        for msg in message_history:
            role = "user" if msg['role'] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg['content'])]
            ))

        final_prompt = f"Context:\n{context_str}\n\nUser Question: {user_query}"
        
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=final_prompt)]
        ))
        
        # 4. Generate
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
            contents=contents
        )
        
        raw_text = response.text
        
        # Parse USED_SOURCES
        final_text = raw_text
        referenced_documents = []
        
        if "USED_SOURCES:" in raw_text:
            parts = raw_text.rsplit("USED_SOURCES:", 1)
            final_text = parts[0].strip()
            sources_str = parts[1].strip()
            
            if sources_str != "NONE":
                 # We simply return the distinct docs found in relevant_chunks which match the titles.
                 source_titles = [t.strip().lower() for t in sources_str.split(',')]
                 seen_ids = set()
                 
                 # Create a map for quick lookup
                 # chunk.document is a lightweight object with id and title
                 available_docs = {}
                 for chunk in relevant_chunks:
                     available_docs[chunk.document.title.lower()] = chunk.document
                 
                 for title in source_titles:
                     # 1. Exact match (case-insensitive)
                     if title in available_docs:
                         doc = available_docs[title]
                         if doc.id not in seen_ids:
                             referenced_documents.append(doc)
                             seen_ids.add(doc.id)
                         continue
                     
                     # 2. Partial match (if LLM shortened the title)
                     for available_title, doc in available_docs.items():
                         if title in available_title or available_title in title:
                             if doc.id not in seen_ids:
                                 referenced_documents.append(doc)
                                 seen_ids.add(doc.id)
                             break
        
        return final_text, referenced_documents
        
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I encountered an error while processing your request.", []
