"""Shared document-format constants for routing and parsing."""

ANYDOC_EXTS = frozenset(
    {"doc", "docx", "odt", "rtf", "epub", "ppt", "pptx", "xlsx", "ods", "odp", "csv"}
)
SUPPORTED_DOCUMENT_EXTS = frozenset({"pdf"}) | ANYDOC_EXTS | {"docm", "xlsm", "pptm"}
