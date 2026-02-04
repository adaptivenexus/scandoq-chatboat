import os
from google import genai
from google.genai import types
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from api.models import Document, DocumentChunk
from pgvector.django import L2Distance

# Configure Gemini
# Ensure GOOGLE_API_KEY is in your environment variables
def get_client():
    if os.getenv('GOOGLE_API_KEY'):
        return genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
    return None

def get_embedding(text):
    """
    Generate embedding using Gemini model.
    Using 'text-embedding-004' as it's the latest standard.
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

def process_document(document_id):
    """
    Reads the document file, splits it into chunks, generates embeddings using Gemini,
    and stores them in the DocumentChunk model.
    """
    if not os.getenv('GOOGLE_API_KEY'):
        print("GOOGLE_API_KEY not found. Skipping processing.")
        return False, "Missing API Key"

    try:
        doc = Document.objects.get(id=document_id)
        file_path = doc.file.path
        
        # 1. Load Document content
        text = ""
        if file_path.lower().endswith('.pdf'):
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            text = "\n".join([p.page_content for p in pages])
        elif file_path.lower().endswith('.txt') or file_path.lower().endswith('.md'):
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception:
                return False, "Unsupported file format"

        if not text.strip():
            # Fallback: Try using Gemini to extract text (e.g. for scanned PDFs)
            print(f"Basic extraction failed for {doc.title}. Trying Gemini extraction...")
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                
                mime_type = "application/pdf"
                if file_path.lower().endswith('.txt'): mime_type = "text/plain"
                elif file_path.lower().endswith('.md'): mime_type = "text/markdown"
                
                client = get_client()
                if client:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            types.Content(
                                parts=[
                                    types.Part.from_bytes(data=file_content, mime_type=mime_type),
                                    types.Part.from_text(text="Extract all text from this document for indexing. Return only the extracted text, no meta-commentary.")
                                ]
                            )
                        ]
                    )
                    text = response.text
            except Exception as e:
                print(f"Gemini fallback failed: {e}")

        if not text or not text.strip():
            return False, "Empty document (could not extract text)"

        # Sanitize text: Remove null bytes which PostgreSQL cannot handle
        text = text.replace('\x00', '')

        # 2. Split Text
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        chunks = text_splitter.split_text(text)
        
        # 3. Generate Embeddings & Save
        document_chunks = []
        
        # Gemini has rate limits, but for small docs it's fine. 
        # For production, implement batching or retry logic.
        for i, chunk_text in enumerate(chunks):
            embedding = get_embedding(chunk_text)
            if embedding:
                document_chunks.append(
                    DocumentChunk(
                        document=doc,
                        chunk_index=i,
                        content=chunk_text,
                        embedding=embedding
                    )
                )
            
        DocumentChunk.objects.bulk_create(document_chunks)
        
        # Update processed status
        doc.is_processed = True
        doc.save()

        print(f"Successfully processed document {document_id}: {len(document_chunks)} chunks created.")
        return True, len(document_chunks)
        
    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        return False, str(e)

def search_documents(query, user, limit=5):
    """
    Search for relevant document chunks using vector similarity.
    """
    client = get_client()
    if not client:
        return []

    try:
        # Generate embedding for the query
        query_embedding_result = client.models.embed_content(
            model="text-embedding-004",
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"
            )
        )
        query_embedding = query_embedding_result.embeddings[0].values
        
        # Search in database using pgvector L2 distance
        # Filter by documents owned by the user
        chunks = DocumentChunk.objects.filter(document__user=user) \
            .annotate(distance=L2Distance('embedding', query_embedding)) \
            .order_by('distance')[:limit]
            
        return chunks
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
        # Use select_related/prefetch_related if performance becomes an issue, but for now access property directly
        context_str = "\n\n".join([f"Document: {c.document.title}\n{c.content}" for c in relevant_chunks])
        
        if not context_str:
            context_str = "No relevant documents found."

        # 2. Construct System Instruction
        system_instruction = (
            "You are a helpful and intelligent assistant named 'Nexus'. "
            "You have access to the user's uploaded documents via the Context provided below. "
            "Always prioritize the information in the Context when answering. "
            "If the Context contains the answer, cite the information using the Document Name provided in the header (e.g., '**Document: Filename.pdf**'). "
            "Do NOT refer to 'chunks' or 'sections' by their internal index; simply refer to the document title. "
            "If the Context does not contain the answer, you can answer from your general knowledge, "
            "but explicitly state that you couldn't find it in the uploaded documents. "
            "Be concise and professional. "
            "If user says hi or hello greet them with 'Hello! How can I help you today?'.\n\n"
            "CRITICAL INSTRUCTION: at the very end of your response, on a new line, you MUST list the exact titles of the documents from the Context that you actually used to answer the question. "
            "Format the line exactly as: 'USED_SOURCES: title1, title2'. "
            "If you didn't use any documents from the context, write 'USED_SOURCES: NONE'. "
            "Do not include this line if you are just greeting."
        )

        # 3. Format Chat History for Gemini
        # Convert Django Message objects or dicts to Gemini content format
        # Expecting message_history to be a list of dicts: [{'role': 'user'|'assistant', 'content': '...'}]
        contents = []
        
        # Add a system-like message at the start (Gemini supports system_instruction param in recent APIs, 
        # but embedding it in the first turn or config is also common. 
        # google-genai SDK 0.3+ has explicit config.
        
        for msg in message_history:
            role = "user" if msg['role'] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg['content'])]
            ))

        # Add the current query with context as the last user message
        final_prompt = f"Context:\n{context_str}\n\nUser Question: {user_query}"
        
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=final_prompt)]
        ))
        
        # If the last message in history was the user query, replace it or append context to it.
        # However, views.py usually saves the message first. 
        # Let's assume message_history EXCLUDES the current new query, or we just append a new turn.
        # Actually, simpler RAG pattern:
        # System: Instructions
        # User: <Context> + <Question>
        # Model: <Answer>
        
        # Let's build a fresh request for this turn
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Using model requested by user
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
                # Get all available docs from context
                available_docs = {chunk.document.title: chunk.document for chunk in relevant_chunks}
                
                # Match titles
                source_titles = [t.strip() for t in sources_str.split(',')]
                for title in source_titles:
                    # Simple fuzzy match or exact match
                    # Trying exact match first since we told LLM to use exact titles
                    if title in available_docs:
                        referenced_documents.append(available_docs[title])
                    else:
                        # Fallback: check if title is contained in any available doc title
                        for avail_title, doc in available_docs.items():
                            if title.lower() in avail_title.lower():
                                referenced_documents.append(doc)
                                break
            
            # Remove duplicates
            referenced_documents = list(set(referenced_documents))
        else:
            # Fallback for safe measure: if LLM ignored instruction, use old logic but maybe limit it?
            # Or just return nothing to be strict. Let's return nothing to avoid "Sources" clutter.
            referenced_documents = [] # list({chunk.document for chunk in relevant_chunks})

        return final_text, referenced_documents
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I encountered an error while processing your request. Please try again later.", []
