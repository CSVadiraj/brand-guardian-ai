# Brand Guardian AI

**Brand Guardian AI** is a prototype video brand-compliance auditing
application. It accepts a public YouTube video URL, attempts to extract
video transcript and on-screen text, retrieves relevant compliance
guidance, and uses an Azure OpenAI model to produce a compliance
assessment.

> **Project status:** Prototype / under development. The FastAPI
> application has been started and its Swagger interface has been
> accessed during development. An audit attempt returned
> `No Transcript`, so successful end-to-end video processing and
> compliance-report generation have **not yet been verified**. Do not
> treat the complete pipeline as production-ready.

## What the application is intended to do

1.  Accept a YouTube URL through a FastAPI endpoint.
2.  Download the video using `yt-dlp`.
3.  Submit the downloaded video to Azure Video Indexer.
4.  Extract transcript and OCR text from the video insights.
5.  Search an Azure AI Search index for relevant compliance guidance.
6.  Use Azure OpenAI to assess the extracted content against the
    retrieved guidance.
7.  Return a structured `PASS` / `FAIL`-style audit result, findings,
    and diagnostic errors.

## Architecture

The implemented LangGraph workflow is a **sequential two-node graph**,
not a multi-agent system:

``` text
Client
  |
  | POST /audit  { "video_url": "..." }
  v
FastAPI
  |
  v
LangGraph workflow
  |
  +--> Indexer node
  |      |
  |      +--> yt-dlp: download YouTube video
  |      +--> Azure Video Indexer: process video
  |      +--> extract transcript and OCR text
  |
  +--> Auditor node
         |
         +--> Azure AI Search: retrieve compliance guidance
         +--> Azure OpenAI: assess content against guidance
         |
         v
      Audit result
```

### Main technologies

  Technology            Role in this project
  --------------------- ------------------------------------------------
  Python                Application language
  FastAPI               HTTP API and Swagger documentation
  LangGraph             Orchestrates the Indexer → Auditor workflow
  yt-dlp                Downloads public YouTube videos
  Azure Video Indexer   Video insights, transcript and OCR extraction
  Azure AI Search       Retrieves indexed compliance reference content
  Azure OpenAI          Generates the compliance assessment
  `uv`                  Python environment and dependency management

## Repository layout

``` text
.
├── backend/
│   ├── data/                 # Compliance reference PDFs
│   ├── scripts/
│   │   └── index_documents.py
│   └── src/
│       ├── api/
│       │   ├── server.py     # FastAPI endpoints and request/response models
│       │   └── telemetry.py
│       ├── graph/
│       │   ├── state.py      # LangGraph state definition
│       │   ├── nodes.py      # Indexer and Auditor node logic
│       │   └── workflow.py   # Graph construction
│       └── services/
│           └── video_indexer.py
├── src/
│   └── genai_project/
├── tests/
├── main.py
├── pyproject.toml
├── requirements.txt
├── uv.lock
├── .env.example
└── .gitignore
```

## Prerequisites

-   Windows, macOS, or Linux
-   Python 3.13 (the project currently declares `>=3.13`)
-   [`uv`](https://docs.astral.sh/uv/) installed
-   FFmpeg recommended for video download/format handling
-   Azure resources and permissions for the integrations you intend to
    use:
    -   Azure OpenAI chat deployment
    -   Azure OpenAI embedding deployment
    -   Azure AI Search service and index
    -   Azure Video Indexer account/resource
-   Network access to YouTube and the configured Azure services

The Azure services are external dependencies. Creating the Python
environment does not create or configure those Azure resources.

## Setup

Run the following commands from the repository root (the directory
containing `pyproject.toml`).

### 1. Create the environment and install dependencies

``` powershell
uv lock
uv sync
```

### 2. Configure environment variables

Copy the example file:

``` powershell
Copy-Item .env.example .env
```

Fill in `.env` with values from your own Azure resources. The
application reads these settings:

  -----------------------------------------------------------------------------
  Variable                                  Purpose
  ----------------------------------------- -----------------------------------
  `AZURE_OPENAI_ENDPOINT`                   Azure OpenAI resource endpoint

  `AZURE_OPENAI_API_KEY`                    Azure OpenAI API key

  `AZURE_OPENAI_API_VERSION`                Azure OpenAI API version

  `AZURE_OPENAI_CHAT_DEPLOYMENT`            Chat model deployment name

  `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`       Embedding model deployment name

  `AZURE_SEARCH_ENDPOINT`                   Azure AI Search endpoint

  `AZURE_SEARCH_API_KEY`                    Azure AI Search API key

  `AZURE_SEARCH_INDEX_NAME`                 Name of the compliance search index

  `AZURE_VI_ACCOUNT_ID`                     Video Indexer account ID

  `AZURE_VI_LOCATION`                       Azure region/location for Video
                                            Indexer

  `AZURE_VI_NAME`                           Video Indexer Azure resource name

  `AZURE_SUBSCRIPTION_ID`                   Azure subscription ID

  `AZURE_RESOURCE_GROUP`                    Azure resource group

  `APPLICATIONINSIGHTS_CONNECTION_STRING`   Optional Application Insights
                                            connection string
  -----------------------------------------------------------------------------

`AZURE_OPENAI_EMBEDDING_DEPLOYMENT` defaults to `text-embedding-3-small`
in the auditor code if it is not set. Use the actual deployment name
configured in your Azure OpenAI resource.

**Security:** `.env` contains secrets. It must remain local and must
never be committed. Only `.env.example` with placeholders belongs in
Git.

### 3. Authenticate to Azure

The Video Indexer service uses Azure identity for its ARM-based
authentication flow. For local development, sign in with Azure CLI if
your environment is configured to use `DefaultAzureCredential`:

``` powershell
az login
```

The signed-in identity must have the required permissions on the
relevant Azure resources.

## Run the API

From the repository root:

``` powershell
uv run uvicorn backend.src.api.server:app --host 127.0.0.1 --port 8000 --reload
```

Open these URLs:

-   API health check: http://127.0.0.1:8000/health
-   Interactive Swagger UI: http://127.0.0.1:8000/docs

The health endpoint checks that the API process is responding. It does
**not** verify Azure connectivity or that an audit can complete.

## Submit an audit request

Use Swagger UI (`POST /audit`) or send this JSON body:

``` json
{
  "video_url": "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
}
```

The request model expects a valid URL. The API additionally restricts
the host to YouTube domains (`youtube.com`, its supported subdomains, or
`youtu.be`).

The response model contains:

-   `session_id`
-   `video_id`
-   `status`
-   `final_report`
-   `compliance_results` (category, severity, description)
-   `errors` (diagnostic messages)

An HTTP success response alone does not mean the audit passed. Inspect
`status`, `final_report`, and `errors`.

## Index compliance reference PDFs

The repository includes a `backend/data/` directory for compliance
reference PDFs. The indexing script reads PDF files from that directory,
splits their text into chunks, creates embeddings, and uploads the
chunks to the configured Azure AI Search index.

Run from the repository root:

``` powershell
uv run python backend/scripts/index_documents.py
```

Before running it, ensure that:

-   the PDF files are present in `backend/data/`;
-   the Azure OpenAI embedding deployment is configured;
-   the Azure AI Search endpoint, key, and index name are correct;
-   the search index schema is compatible with the embedding dimensions
    produced by the configured embedding deployment.

## Tests

A `tests/` directory is included in the repository. Run the available
tests with:

``` powershell
uv run pytest
```

A passing local test suite does not, by itself, prove that the live
YouTube and Azure integrations work. Those require separate integration
tests using valid resources, permissions, and network access.

## Current verification and known limitations

-   FastAPI startup and access to `/docs` have been demonstrated during
    development.
-   A previous `POST /audit` attempt returned a failure indicating that
    no transcript was available.
-   Successful YouTube download, Azure Video Indexer processing,
    transcript/OCR extraction, Azure AI Search retrieval, Azure OpenAI
    assessment, and final report generation have **not been demonstrated
    as a complete successful run**.
-   Azure resource configuration, permissions, quotas, network access,
    YouTube availability, and search-index contents can each prevent an
    audit from completing.
-   The graph currently has two sequential nodes (Indexer and Auditor).
    It should not be described as an autonomous multi-agent
    architecture.
-   This repository is a prototype and needs further integration
    testing, error-path testing, security review, and operational
    hardening before production use.

## Security notes

-   Never commit `.env`, API keys, access tokens, certificates, or other
    credentials.
-   Keep `.env.example` limited to placeholder values.
-   Before making the repository public, review the Git history as well
    as the current files. A secret committed in an earlier commit can
    remain in repository history even after the file is removed.
-   If a real credential was pushed to a public repository,
    rotate/revoke it in the corresponding Azure service.

## Development workflow

When changing the application:

1.  Make a focused change.
2.  Run the relevant local tests.
3.  Record whether the result was verified locally or against live Azure
    services.
4.  Update this README when setup, API behavior, architecture, or
    verification status changes.

## License

No license has been specified yet. Unless a license is added, the
repository should not be assumed to grant others permission to reuse,
modify, or distribute the code.
