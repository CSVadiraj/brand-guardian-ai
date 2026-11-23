# Brand Guardian AI

Brand Guardian AI downloads a YouTube video, sends it to Azure AI Video Indexer
for transcription and OCR, retrieves compliance guidance from Azure AI Search,
and asks an Azure OpenAI deployment to produce a structured audit.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- Azure OpenAI chat and embedding deployments
- Azure AI Search with a populated vector index
- Azure AI Video Indexer account and an Azure identity allowed to access it

## Configuration

Copy `.env.example` to `.env` in the repository root and fill in the values for
your Azure resources. The project never logs API keys. `DefaultAzureCredential`
is used for Video Indexer management access; locally, authenticate with `az
login` and grant that identity the required Azure permissions. Do not copy
secrets into source files or commit `.env`.

The Video Indexer subscription variable is `AZURE_VI_SUBSCRIPTION_ID`. The
Azure OpenAI embedding deployment name is configurable separately from the chat
deployment. Azure AI Search must already contain the compliance documents
before an audit can succeed.

## Install and test

```powershell
uv sync --locked
uv run python -m unittest discover -s backend/tests -v
```

## Index the included compliance PDFs

```powershell
uv run python -m backend.scripts.index_documents
```

The indexer reads PDFs from `backend/data` and exits with a non-zero status if
configuration is missing, processing fails, or no documents can be indexed.

## Run the API

```powershell
uv run uvicorn backend.src.api.server:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger UI. Submit a YouTube HTTPS URL to
`POST /audit`. `GET /health` checks that the API process is responsive. Audits
make external Azure and YouTube requests and can take several minutes.

## Run the CLI

```powershell
uv run genai-project
```

This project command starts the API on `http://127.0.0.1:8000`. To run the
separate workflow simulation, supply a YouTube video you are authorized to
process:

```powershell
uv run python main.py --video-url https://youtu.be/VIDEO_ID
```

## Run in Docker

Build and run without embedding secrets in the image:

```powershell
docker build -f backend/Dockerfile -t brand-guardian .
docker run --rm -p 8000:8000 --env-file .env brand-guardian
```

`backend/tests/.env` is not loaded by the application; only the repository-root
`.env` is read.