# Technical Design: wa_toolkit

**Status**: Draft
**Version**: 1.0.0
**Author**: Replate Engineering

## 1. Objective
To provide a reusable, modular Python framework for building multi-turn WhatsApp chatbots. The toolkit abstracts the "plumbing" (session persistence, state routing, AI extraction, and local simulation) so developers can focus exclusively on conversation logic and domain-specific actions.

## 2. System Architecture

```mermaid
graph TD
    A[WhatsApp/Simulator] -->|Message| B(StateMachine)
    B -->|Check Session| C(SessionManager)
    C <-->|Read/Write| D[(Supabase)]
    B -->|Dispatch| E(Domain Handlers)
    E -->|Call AI| F(AIExtractor)
    F <-->|Generate| G[Gemini API]
    E -->|Return| B
    B -->|Reply| A
    
    subgraph Errors
    H[errors.py]
    end
    B -.->|Raises| H
    C -.->|Raises| H
    F -.->|Raises| H
```

## 3. Core Components

### 3.0 Package Structure
The toolkit is organized as a modular Python package:

```text
wa_toolkit/
├── __init__.py        # Package entry point
├── session.py         # SessionManager (Supabase persistence)
├── state_machine.py   # StateMachine (Orchestration & Dispatch)
├── ai_extractor.py    # AIExtractor (Gemini with resilience)
├── simulator.py       # Simulator (Local REPL)
└── errors.py          # Exception hierarchy
```

### 3.1 SessionManager (`session.py`)
Responsible for persistence. It assumes a specific PostgreSQL schema in Supabase but allows for a custom table name.

**Implementation Details:**
- **Storage**: Supabase `JSONB` for `temp_data` to allow arbitrary key-value storage per project.
- **Consistency**: To prevent inconsistent states during process failures, the toolkit MUST perform a single write operation when updating both state and data.
- **Methods**:
    - `get(phone)`: Returns a `dict` representing the session.
    - `create(phone, state)`: Initializes a session using `.upsert()`.
    - `update(phone, state, data)`: Persists both `state` and `temp_data` in a single `.update()` call to ensure transactional consistency. (Partial update methods for state or data only are NOT exposed).
    - `delete(phone)`: Removes the session from the database.

### 3.2 StateMachine (`state_machine.py`)
The orchestrator. It manages the lifecycle of a message from arrival to reply.

**Key Features:**
- **Command Interception**: Intercepts "system" commands (`RESET`, `STOP`, `NEW`) before they reach domain handlers.
- **Robust Error Handling**: Wraps handler execution in `try/except` to prevent bot crashes.
- **V1 Media Readiness**: The `handle(phone, message)` signature accepts `Any` for the message to remain forward-compatible with future V2 rich-media objects.
- **Validation**: During the dispatch phase, if the current session state has no registered handler, the `StateMachine` MUST raise a `StateNotFoundError`.

### 3.3 AIExtractor (`ai_extractor.py`)
A wrapper around the Google GenAI SDK (Gemini) with built-in resilience.

**Robustness Strategy & Retry Policy:**
1.  **Attempts**: The system makes up to **5 attempts** per extraction.
2.  **Backoff**: Uses exponential backoff (min 4s, max 20s) between retries to handle rate limits (429) or transient API failures.
3.  **Model Fallback Chain**:
    *   Primary: Attempt using `gemini-flash-latest`.
    *   Fallback: On primary failure, switch to `gemini-flash-lite-latest` for higher throughput/lower cost.
4.  **Final Fallback (Mock)**: If both models fail after all retries, the system calls the project-provided `mock_fn` (e.g., regex-based extraction).
5.  **Termination**: If no `mock_fn` is provided and the chain fails, a `AIExtractionError` is raised.
6.  **Offline Mode**: If `MOCK_AI=true` in the environment, it bypasses the API entirely and calls the `mock_fn`.

### 3.4 Simulator (`simulator.py`)
A REPL-based interface for rapid local testing.

**API Compatibility**: The `run()` method accepts a handler function with the signature `(phone: str, message: Any) -> str`, ensuring full compatibility with the `StateMachine.handle` method.

## 4. Error Handling & Exceptions (`errors.py`)
The toolkit defines a hierarchy of exceptions:

- `WAToolkitError`: Base class.
- `AIExtractionError`: Failed after all retries and fallbacks.
- `SessionError`: Database connection or schema mismatch issues.
- `StateNotFoundError`: Raised by `StateMachine` if it attempts to dispatch to a state with no registered handler.

## 5. Configuration & Environment
The toolkit relies on the following environment variables. Host applications are responsible for loading these (e.g., via `python-dotenv`) before initializing toolkit components.

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Project URL for database persistence. |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service key to bypass RLS for session management. |
| `GEMINI_API_KEY` | Yes | API key for LLM extraction logic. |
| `MOCK_AI` | No | If "true", enables offline mode for `AIExtractor`. |

## 6. Engineering Standards (Requirements)

### 6.1 Logging Strategy
The toolkit MUST NOT use `print()` statements. It will use a named Python logger:
- **Logger Name**: `wa_toolkit`
- **Standard**: Host applications can control verbosity via `logging.getLogger("wa_toolkit").setLevel()`.
- **Key Events**: AI retry attempts, session write failures, and command interceptions MUST be logged at `INFO` or `WARNING` levels.

### 6.2 Handler Interface Specification
Domain handlers registered with the `StateMachine` MUST adhere to the following contract:
- **Input**: `(phone: str, message: Any, data: dict)`
- **Output**: `tuple[str, str, dict]` -> `(reply_text, next_state, updated_data)`

**No-Op Write Optimization**: To minimize database IO, the `StateMachine` MUST compare the handler's output (`next_state`, `updated_data`) against the current session state. If both remain unchanged, the `StateMachine` MUST skip the `SessionManager.update()` call.

### 6.3 Dependency Management
The toolkit implementation MUST include a `requirements.txt` that defines the tested range of core dependencies. Exact versions should be pinned at release time to prevent breaking changes in host projects:
- `supabase >= 2.11.0`
- `google-genai >= 1.2.0`
- `tenacity >= 9.0.0`

### 6.4 Graceful Degradation
Failed AI extractions MUST NOT raise unhandled exceptions to the `StateMachine`. Instead, the `AIExtractor` must return a valid JSON object with a project-defined flag (e.g., `requires_review: true`) indicating that human intervention is needed.

## 7. Testing Strategy

The toolkit itself must be validated independently of the projects using it:

1.  **Unit Tests (`StateMachine`)**: Verify command interception and handler routing using mock handlers and a mock SessionManager.
2.  **Mock Integration (`SessionManager`)**: Test session CRUD operations against a mock Supabase client to ensure single-write consistency.
3.  **Resilience Tests (`AIExtractor`)**: Force API failures to verify that exponential backoff and model fallback trigger correctly.
4.  **REPL Verification**: Ensure the simulator correctly terminates on `EXIT` and handles `KeyboardInterrupt`.

## 8. Roadmap / V2

- **Rich Media**: Implementation of a `Message` object to parse image URLs and voice notes.
- **Provider Agnostic**: Support for Twilio and Meta Cloud API through a unified `MessageAdapter`.
- **Storage Adapters**: Interface-based persistence to support Redis or In-Memory storage.
