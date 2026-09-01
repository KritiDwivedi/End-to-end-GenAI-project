# Document Copilot: Reusable Build Skill

Use this skill when building an internal document-question-answering application with a React frontend, FastAPI backend, Supabase authentication and Postgres, local document ingestion, hybrid retrieval, and grounded answers with citations.

## Product pattern

The application lets authenticated analysts ask questions about a local corpus of filings or business documents. The system retrieves relevant passages using both semantic and keyword search, then generates an answer that cites only retrieved evidence.

The central rule is:

```text
documents -> normalized Markdown -> structured chunks -> local embeddings -> Postgres
question  -> local query embedding + full-text query -> hybrid retrieval -> grounded answer
```

## Stack

- Frontend: Vite, React, TypeScript, React Router, Supabase browser client.
- Backend: Python 3.12+, FastAPI, Pydantic v2, pydantic-settings, uvicorn.
- Authentication: Supabase Auth with email/password and bearer tokens.
- Database: Supabase Postgres, SQLAlchemy models, Alembic migrations, pgvector.
- Sparse retrieval: PostgreSQL full-text search using `tsvector`, GIN, and `websearch_to_tsquery`.
- Dense retrieval: local `sentence-transformers/all-MiniLM-L6-v2` embeddings.
- Fusion: Reciprocal Rank Fusion (RRF) in Python.
- Answer generation: Pydantic AI with Gemini or another configured chat model.
- Document processing: Docling `HybridChunker` over normalized Markdown.

## Repository layout

```text
document-copilot/
  SKILL.md
  AGENTS.md
  data/
    downloads/                 # raw HTML filings and manifest
    markdown/                  # normalized Markdown, same year structure
    html_to_markdown.py        # Docling conversion script
    load_markdown_to_db.py     # source_documents loader
    build_document_chunks.py   # chunk, embed, and persist pipeline
  backend/
    app/
      config.py                # single environment/config boundary
      auth/                     # Supabase bearer-token dependencies
      database/                 # split SQLAlchemy models and clients
      retrieval/                # dense search, sparse search, RRF
      assistant/                # Pydantic AI agent and typed dependencies
      api/                      # FastAPI routers
    alembic/
      versions/                # reviewed database migrations
  frontend/
    src/
      lib/                     # env, Supabase, HTTP, and typed API helpers
      pages/                    # auth and chat screens
```

## Configuration rules

Keep environment access in `backend/app/config.py`. Application modules should import `settings` rather than calling `os.getenv` directly.

Required values normally include:

```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
DATABASE_URL=postgresql://postgres:...@db.<project-ref>.supabase.co:5432/postgres
OPENAI_API_KEY=...
```

Local embeddings use:

```env
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LOCAL_EMBEDDING_DIMENSIONS=384
```

The database URL must be the direct/session Supabase connection, not the transaction pooler URL. URL-encode special characters in the database password.

The service-role key is backend-only and must never be placed in frontend environment variables.

## Database model pattern

Keep each SQLAlchemy model in its own file and import every model from `app/database/models.py` so Alembic can discover the metadata.

Required tables:

- `users`: application user record associated with Supabase Auth.
- `source_documents`: filing metadata and normalized Markdown content.
- `document_chunks`: chunk text, local embedding, metadata, page, and section information.
- `chat_threads`: user-owned conversations.
- `chat_messages`: user and assistant messages.
- `message_citations`: citations linking assistant messages to document chunks.

For MiniLM, `document_chunks.embedding` must be `vector(384)`. Dense indexing and query embedding must always use the same model and dimensions.

When changing embedding models:

1. Add a reviewed Alembic migration.
2. Clear old vectors because vectors from different models or dimensions are incompatible.
3. Change the vector column dimension.
4. Re-embed the corpus.
5. Re-run retrieval verification queries.

Never manually change production tables in the Supabase dashboard when the change belongs in the application schema.

## Ingestion pipeline

### 1. Convert documents

Use Docling to convert HTML to Markdown. Preserve the source folder structure, such as `year/ticker_filing_date_accession.md`, and maintain a downloads manifest containing source metadata.

Export Markdown under `data/markdown/`. Keep this script separate from the FastAPI application because ingestion is an offline/data operation.

### 2. Load source documents

Insert or upsert one `source_documents` row per filing using the accession number as the stable identity. Preserve ticker, filing type, filing date, fiscal year, source URL, and manifest metadata.

### 3. Chunk with Docling

Parse Markdown back through Docling and use `HybridChunker` with `merge_peers=True`. Preserve contextualized chunk text and Docling metadata, including headings, pages, and section information.

For MiniLM, keep chunks within its 256 word-piece input limit. A conservative chunk setting is approximately 200-250 model tokens; validate actual token lengths because tokenizer estimates can differ.

### 4. Embed locally

Load the model once per process:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
vectors = model.encode(
    texts,
    batch_size=32,
    normalize_embeddings=True,
    convert_to_numpy=True,
)
```

Local inference avoids Gemini/OpenAI embedding quotas. The model is downloaded once and reused from the Hugging Face cache. Batch encoding reduces overhead, but it does not create API calls because inference is local.

### 5. Persist chunks

Upsert chunks using `(document_id, chunk_index)` as the stable key. Store the original chunk text, embedding, token count, page number, section title, and source path metadata. Populate `search_vector` with `to_tsvector('english', text)`.

Write a manifest such as `data/markdown/chunk_manifest.json` containing the embedding model, dimensions, chunk configuration, processed files, and successful chunk records. The manifest records pipeline output; it is not the database itself.

## Running ingestion

From the repository root:

```powershell
uv run data/html_to_markdown.py
uv run data/load_markdown_to_db.py
```

After applying the embedding migration, test one file and one chunk:

```powershell
uv run data/build_document_chunks.py --smoke
```

Limit processing while debugging:

```powershell
uv run data/build_document_chunks.py --limit-files 1
uv run data/build_document_chunks.py --limit-files 2
```

Run the full corpus only after the smoke test succeeds:

```powershell
uv run data/build_document_chunks.py
```

The ingestion script is idempotent for the same document and chunk index. A failed run can be resumed, but verify the manifest and database state before assuming all chunks were processed.

## Migration workflow

Run commands from `backend/`:

```powershell
uv run alembic current
uv run alembic heads
uv run alembic upgrade head
```

Prepare and review migrations before applying them. An embedding-dimension migration should explicitly clear incompatible vectors and then alter the pgvector column.

## Retrieval pattern

For each user query:

1. Encode the query with the same local MiniLM model.
2. Run pgvector similarity search over `document_chunks.embedding`.
3. Run PostgreSQL full-text search over `document_chunks.search_vector`.
4. Keep the two ranked lists separate because their scores are not comparable.
5. Fuse them using RRF, normally with `k=60`.
6. Return the top passages with document, filing, page, section, and chunk metadata.

Useful defaults:

- final passages: `top_k=8`
- dense candidates: `dense_k=20`
- sparse candidates: `sparse_k=20`
- RRF constant: `k=60`

Dense retrieval handles paraphrases and semantic similarity. Full-text search is especially useful for exact financial terms, company names, identifiers, and section language.

## Pydantic AI pattern

Pydantic AI belongs around the answer-generation step. It does not replace retrieval.

- Retrieval finds evidence.
- Agent tools expose retrieval and chunk-reading operations.
- Typed dependencies provide the retriever, database access, and user context.
- A typed result model defines the answer contract.
- Grounding validation checks that every citation points to a retrieved passage.
- The chat route streams the answer and persists the final assistant message and citations.

Keep the agent instructions explicit: answer from retrieved evidence, cite each factual claim, say when evidence is insufficient, and refuse questions outside the document corpus when the evidence does not support an answer.

## Auth and API pattern

The frontend uses only the Supabase anon key. The shared HTTP client obtains the current access token and sends it as a bearer token to FastAPI.

FastAPI should:

- reject missing or invalid tokens with `401`;
- resolve the current user before database or LLM work;
- enforce ownership of threads and messages, returning `403` for another user's resource;
- use the service-role Supabase client only for explicitly privileged backend operations;
- use a user-scoped client when an operation should run with the signed-in user's authority.

## Verification checklist

- [ ] Backend starts and reports application startup complete.
- [ ] Frontend loads the sign-in page instead of the default Vite page.
- [ ] Supabase login returns a session and the bearer token reaches FastAPI.
- [ ] Alembic reports the expected revision.
- [ ] Local MiniLM loads without contacting an embedding API.
- [ ] A smoke run writes one 384-dimensional vector.
- [ ] Dense retrieval and full-text retrieval each return candidates.
- [ ] RRF returns a merged ranked list.
- [ ] Answers cite retrieved chunks only.
- [ ] An unsupported question produces an insufficient-evidence response.
- [ ] Chat messages and citation rows persist under the correct user/thread.

## Common failure modes

- `ModuleNotFoundError: psycopg2`: use the project's `psycopg[binary]` driver and the matching SQLAlchemy URL configuration; do not install an unrelated driver blindly.
- Database authentication errors: verify the direct Supabase URL, username, password, port, and URL encoding.
- Vector dimension errors: ensure the migration, SQLAlchemy model, ingestion model, and retrieval model all use 384.
- Empty dense search: confirm the corpus was re-embedded after the dimension migration.
- Empty sparse search: confirm `search_vector` is populated and the query uses PostgreSQL full-text syntax.
- Slow API searches: cache the local embedding model rather than loading it for every request.
- Gemini quota exhaustion: use local MiniLM for embeddings; reserve Gemini for answer generation or replace chat generation with a local model later.
- Blank frontend: inspect frontend environment variables, CSS imports, route setup, and API base URL before changing backend code.
