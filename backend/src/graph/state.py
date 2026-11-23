import operator
from typing import Annotated, Any, NotRequired, Optional, TypedDict

# 1. Define the Schema for a Single Compliance Result
# This ensures structural consistency for every issue detected by the AI.
class ComplianceIssue(TypedDict):
    category: str           # e.g., "FTC_DISCLOSURE"
    description: str        # Specific detail of the violation
    severity: str           # "CRITICAL" | "WARNING"
    timestamp: NotRequired[Optional[str]]

# 2. Define the Global Graph State
class VideoAuditState(TypedDict):
    """
    Defines the data schema for the LangGraph execution context.
    """
    # --- Input Parameters ---
    video_url: str
    video_id: str

    # --- Ingestion & Extraction Data ---
    # Optional because they are populated asynchronously by the Indexer Node.
    local_file_path: NotRequired[Optional[str]]
    video_metadata: NotRequired[dict[str, Any]]
    transcript: NotRequired[Optional[str]]
    ocr_text: NotRequired[list[str]]

    # --- Analysis Output ---
    # annotated with operator.add to allow append-only updates from multiple nodes.
    compliance_results: Annotated[list[ComplianceIssue], operator.add]
    
    # --- Final Deliverables ---
    final_status: NotRequired[str]
    final_report: NotRequired[str]
    
    # --- System Observability ---
    # Appends system-level errors (e.g., API timeouts) without halting execution logic.
    errors: Annotated[list[str], operator.add]