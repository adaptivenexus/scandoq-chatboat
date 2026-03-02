import os
import tempfile
import shutil
import lancedb
import pandas as pd
from django.conf import settings
from google import genai
from google.genai import types
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from api.models import Document

# Simple wrapper to mimic the old DocumentChunk model behavior for compatibility
class ChunkResult:
    def __init__(self, document, content, score=0.0):
        self.document = document
        self.content = content
        self.score = score

def get_client():
    if os.getenv('GOOGLE_API_KEY'):
        return genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
    return None

def get_embedding(text):
    client = get_client()
    if not client:
        return None
    try:
        result = client.models.embed_content(
            model="models/gemini-embedding-001",
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

def get_db():
    # Connect to LanceDB using the URI from settings
    # If S3, ensured by environment vars for credentials
    # Added getattr fallback in case 'LANCEDB_URI' is not in settings.py (e.g., outdated local file)
    uri = getattr(settings, 'LANCEDB_URI', str(getattr(settings, 'BASE_DIR', '.')) + '/lancedb_data')
    return lancedb.connect(uri)

def process_document(document_id):
    print(f"Processing document ID: {document_id}")
    if not os.getenv('GOOGLE_API_KEY'):
        return False, "Missing API Key"

    try:
        doc = Document.objects.get(id=document_id)
        file_name = doc.file.name.lower()
        
        # Download file to temp
        temp_file_path = None
        text = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
                shutil.copyfileobj(doc.file.open('rb'), temp_file)
                temp_file_path = temp_file.name
            
            # Text Extraction Logic
            if file_name.endswith('.pdf'):
                loader = PyPDFLoader(temp_file_path)
                pages = loader.load()
                text = "\n".join([p.page_content for p in pages])
            elif file_name.endswith('.docx'):
                try:
                    from docx import Document as DocxDocument
                    doc_obj = DocxDocument(temp_file_path)
                    text = "\n".join([para.text for para in doc_obj.paragraphs])
                except ImportError:
                    print("python-docx not installed.")
                    return False, "Server missing python-docx library"
                except Exception as e:
                    print(f"Docx read error: {e}")
            elif file_name.endswith('.txt') or file_name.endswith('.md'):
                with open(temp_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            else:
                try:
                    with open(temp_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                except:
                    pass
            
            # Gemini OCR Fallback
            if not text.strip():
                print("Basic extraction failed. Using Gemini OCR...")
                with open(temp_file_path, "rb") as f:
                    file_content = f.read()
                mime_type = "application/pdf" if file_name.endswith('.pdf') else "text/plain"
                
                client = get_client()
                if client:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[types.Content(parts=[
                            types.Part.from_bytes(data=file_content, mime_type=mime_type),
                            types.Part.from_text(text="Extract all text. Return only text.")
                        ])]
                    )
                    text = response.text

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        if not text or not text.strip():
            return False, "Empty document"
        
        text = text.replace('\x00', '')

        # Chunking
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
        chunks = text_splitter.split_text(text)
        
        # Vectorization & LanceDB Storage
        db = get_db()
        table_name = "vectors"
        
        data = []
        for i, chunk_text in enumerate(chunks):
            embedding = get_embedding(chunk_text)
            if embedding:
                data.append({
                    "vector": embedding,
                    "text": chunk_text,
                    "doc_id": doc.id,
                    "chunk_index": i
                })
        
        if not data:
             return False, "No embeddings generated"

        # Create or Append to Table
        try:
            tbl = db.open_table(table_name)
            tbl.add(data)
        except:
            # Table doesn't exist, create it
            db.create_table(table_name, data)

        doc.is_processed = True
        doc.save()
        return True, len(data)

    except Exception as e:
        print(f"Error processing document: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

def search_documents(query, user, limit=3):
    client = get_client()
    if not client: return []
    
    try:
        # Check for Summary Intent
        summary_keywords = ["summarize", "summary", "overview", "what is this document", "explain this file", "key takeaways"]
        is_summary = any(k in query.lower() for k in summary_keywords)
        
        # 1. Embed Query (Get strictly RETRIEVAL_QUERY embedding if possible, or same as doc)
        # Using same model as ingestion
        query_embedding_result = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=query,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        query_vec = query_embedding_result.embeddings[0].values

        # 2. Get User's Doc IDs from Postgres
        # Optimization: Fetch ONLY the most recent document if it's a summary request
        if is_summary:
            # Get most recent doc
            recent_doc = Document.objects.filter(user=user).order_by('-uploaded_at').first()
            if not recent_doc: return []
            user_doc_ids = [recent_doc.id]
        else:
            user_doc_ids = list(Document.objects.filter(user=user).values_list('id', flat=True))
            if not user_doc_ids:
                return []

        # 3. Search LanceDB
        db = get_db()
        try:
            tbl = db.open_table("vectors")
        except:
            return []

        # Convert IDs to string for SQL filter (simplest safe way)
        ids_str = ", ".join(map(str, user_doc_ids))
        
        if is_summary:
            # For summary, DON'T use vector search. Just get the first N chunks.
            # LanceDB SQL filter
            results = tbl.search()\
                .where(f"doc_id IN ({ids_str})")\
                .limit(15)\
                .to_list() # Get first 15 chunks (Intro + Content)
        else:
            # Standard Vector Search
            results = tbl.search(query_vec) \
                .where(f"doc_id IN ({ids_str})") \
                .limit(limit) \
                .to_list() # Returns list of dicts

        # 4. Convert back to objects
        chunks = []
        # Optimization: Fetch all needed Document objects in one query
        result_doc_ids = set(r['doc_id'] for r in results)
        docs_map = {d.id: d for d in Document.objects.filter(id__in=result_doc_ids)}

        for r in results:
            if r['doc_id'] in docs_map:
                chunks.append(ChunkResult(
                    document=docs_map[r['doc_id']],
                    content=r['text'],
                    score=1.0 # LanceDB generic score
                ))
        
        return chunks

    except Exception as e:
        print(f"Error searching documents: {e}")
        return []

# Non-streaming wrapper (legacy support if needed)
def generate_chat_response(message_history, user_query, user):
    full_content = ""
    usage_data = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for chunk in generate_chat_response_stream(message_history, user_query, user):
        if isinstance(chunk, dict) and "usage_metadata" in chunk:
             # Capture final usage metadata if yielded
             usage_data = chunk["usage_metadata"]
        elif isinstance(chunk, str):
             full_content += chunk
    
    # Parse USED_SOURCES from full_content
    referenced_documents = []
    final_text = full_content
    
    # Fallback Usage Calculation if API returns 0
    if not usage_data or usage_data.get('total_tokens', 0) == 0:
        # Estimation: 1 token ~= 4 chars
        # Setup approximate counting
        est_input = len(user_query) // 4
        est_output = len(final_text) // 4
        # Add context estimation (rough avg)
        est_input += 500 
        
        usage_data = {
            "input_tokens": est_input,
            "output_tokens": est_output,
            "total_tokens": est_input + est_output
        }

    potential_titles = set()

    # 1. Parsing Strict USED_SOURCES block
    if "USED_SOURCES:" in full_content:
        parts = full_content.rsplit("USED_SOURCES:", 1)
        final_text = parts[0].strip()
        sources_str = parts[1].strip()
        if sources_str != "NONE":
             for t in sources_str.split(','):
                 potential_titles.add(t.strip())

    # 2. Regex Fallback for Inline Citations (Source: file)
    import re
    # Patterns: **Source: file**, (Source: file), Source: file
    inline_matches = re.findall(r'Source:\s*([a-zA-Z0-9_.\s-]+)', final_text, re.IGNORECASE)
    for m in inline_matches:
        # Clean up punctuation slightly
        clean_m = m.strip().rstrip('.').rstrip(')')
        if len(clean_m) > 1: # Avoid single chars
            potential_titles.add(clean_m)

    # 3. Match Titles to Database
    if potential_titles:
        user_docs = Document.objects.filter(user=user)
        for title in potential_titles:
            # removing potential file matching issues
            # 1. Exact match
            doc = user_docs.filter(title__iexact=title).first()
            if doc:
                referenced_documents.append(doc)
                continue
            
            # 2. Contains match (fallback)
            doc = user_docs.filter(title__icontains=title).first()
            if doc:
                referenced_documents.append(doc)
                continue

            # 3. Reverse Contains (Filename in Title) - helpful if title is "Resume.pdf" and source is "Resume"
            # We iterate docs for this
            for d in user_docs:
                # Check if "resume" is in "resume.pdf"
                if title.lower() in d.title.lower():
                    referenced_documents.append(d)
                    break 

    # Deduplicate referenced_docs
    referenced_documents = list(set(referenced_documents))

    # CLEANUP: Remove "Source: x" or "(Source: x)" text from the response since we show buttons
    # Regex to remove "Source: filename" patterns (case insensitive)
    # Handles: "**Source: file**", "(Source: file)", "Source: file"
    final_text = re.sub(r'\**\(?Source:\s*[a-zA-Z0-9_.\s-]+\)?\**', '', final_text, flags=re.IGNORECASE).strip()
    
    # Return formatted response
    return final_text, referenced_documents, usage_data

def generate_chat_response_stream(message_history, user_query, user):
    client = get_client()
    if not client:
        yield "Error: GOOGLE_API_KEY is missing."
        return

    try:
        relevant_chunks = search_documents(user_query, user, limit=3)
        context_str = "\n\n".join([f"Document: {c.document.title}\n{c.content}" for c in relevant_chunks])
        if not context_str: context_str = "No relevant documents found."
        
        system_instruction = (
            "You are a helpful and intelligent assistant named 'Nexus'. "
            "You have access to the user's uploaded documents via the Context provided below. "
            "Always prioritize the information in the Context when answering.\n\n"
            "**FORMATTING RULES:**\n"
            "1. **Structured Usage:** If using information from multiple documents, **group your answer by document**. Use Markdown headers (e.g., '### Document Name') to separate sections.\n"
            "2. **Bullet Points:** Use bullet points for lists, summaries, or key details to improve readability.\n"
            "3. **Citations:** Cite the document name (e.g., '**Source: Filename.pdf**') when referring to specific facts.\n"
            "4. **No Internal Indices:** Do NOT refer to 'chunks' or 'indexes'.\n"
            "5. **General Knowledge:** If Context doesn't contain the answer, use general knowledge but explicitly state that it's not from the uploaded documents.\n\n"
            "If user says hi or hello greet them with 'Hello! How can I help you today?'.\n\n"
            "CRITICAL INSTRUCTION: at the very end of your response, on a new line, you MUST list the exact titles of the documents from the Context that you actually used to answer the question. "
            "Format the line exactly as: 'USED_SOURCES: title1, title2'. "
            "If you didn't use any documents from the context, write 'USED_SOURCES: NONE'. "
            "Do not include this line if you are just greeting."
        )

        contents = []
        for msg in message_history:
            role = "user" if msg['role'] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg['content'])]))

        final_prompt = f"Context:\n{context_str}\n\nUser Question: {user_query}"
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=final_prompt)]))
        
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-flash', 
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7),
            contents=contents
        )

        for chunk in response_stream:
            if chunk.text:
                yield chunk.text
            if chunk.usage_metadata:
                # Yield usage data as a dictionary
                yield {
                    "usage_metadata": {
                        "input_tokens": chunk.usage_metadata.prompt_token_count,
                        "output_tokens": chunk.usage_metadata.candidates_token_count,
                        "total_tokens": chunk.usage_metadata.total_token_count
                    }
                }

    except Exception as e:
        yield f"Error: {str(e)}"
