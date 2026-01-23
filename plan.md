# Chatbot Test Project Plan

## Project Overview

A full-stack chatbot application utilizing Django (Backend), React (Frontend), PostgreSQL (Database), a Vector Database (for embeddings), and OpenAI (LLM).

## Architecture

### 1. Frontend (React)

- **Framework:** React (Vite)
- **UI Library:** Tailwind CSS 
- **Features:**
  - Chat Interface (User input, Bot response)
  - Message History Display
  - Loading States
  - API Integration with Backend

### 2. Backend (Django)

- **Framework:** Django + Django REST Framework (DRF)
- **Database:** PostgreSQL (Relational Data)
- **Vector Database:** pgvector (PostgreSQL extension) 
- **LLM Integration:** OpenAI API
- **Embedding Model:** TBD (e.g., OpenAI text-embedding-3-small, HuggingFace models)
- **Key Modules:**
  - **API App:** Handles HTTP requests from React.
  - **Chat Module:** Manages conversation history and context.
  - **RAG Module:** Handles Retrieval-Augmented Generation (Embeddings + Vector Search).

### 3. Database

- **PostgreSQL:**
  - `Users` (Authentication)
  - `Conversations` (Session management)
  - `Messages` (Chat history)
- **Vector Store:**
  - Stores document embeddings for context retrieval.

---

## Implementation Plan

### Phase 1: Setup & Infrastructure (Current Status: In Progress)

- [x] Initialize Django Project (`backend`)
- [x] Configure PostgreSQL Connection
- [x] Create Health Check Route
- [x] Initialize React Project (`frontend`)


### Phase 2: Backend Core - Chat Logic

- [x] Create `Chat` and `Message` models in Django.
- [x] Create API endpoints for:
  - Creating a new conversation.
  - Sending a message.
  - Retrieving conversation history.
- [ ] Integrate OpenAI API for basic LLM responses.

### Phase 3: Frontend Development

- [ ] Setup React project structure.
- [ ] Build Chat UI components.
- [ ] Connect Frontend to Backend APIs.

### Phase 4: RAG Implementation (Vector DB & Embeddings)

- [ ] Select and setup Vector Database (e.g., `pgvector`).
- [ ] Select Embedding Model.
- [ ] Implement document ingestion (Text -> Embedding -> Vector DB).
- [ ] Implement context retrieval logic (Query -> Embedding -> Similarity Search).
- [ ] Update Chat Logic to use RAG (Retrieve Context -> Prompt Engineering -> LLM).

### Phase 5: Refinement & Testing

- [ ] Optimize prompts.
- [ ] Improve UI/UX (Streaming responses, error handling).
- [ ] Deploy to production (Render/VPS).

## Technical Stack Summary

- **Backend:** Django, Django REST Framework, Python
- **Frontend:** React, Vite, Axios/Fetch
- **Database:** PostgreSQL
- **AI/ML:** OpenAI API, Vector DB (pgvector/ChromaDB)
