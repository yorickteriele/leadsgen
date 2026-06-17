from fastapi import Depends, FastAPI

from app.config import Settings, get_settings
from app.models import EnrichDomainRequest, LeadEnrichmentResponse
from app.pipeline import LeadEnrichmentPipeline


tags_metadata = [
    {
        "name": "system",
        "description": "Operational endpoints for health checks.",
    },
    {
        "name": "enrichment",
        "description": (
            "Enrich one newly observed .nl domain into a structured Dutch B2B "
            "lead profile for Aresis."
        ),
    },
]

app = FastAPI(
    title="Aresis Lead Enrichment API",
    summary="Dutch B2B domain lead enrichment and qualification service.",
    description=(
        "Accepts one newly observed .nl domain, collects public DNS and website "
        "signals, optionally enriches with KvK data when configured, and returns "
        "a schema-valid lead profile with fit score, reasoning, evidence, and "
        "recommended next action."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=tags_metadata,
    contact={"name": "Aresis", "url": "https://aresis.nl"},
)


@app.get(
    "/health",
    tags=["system"],
    summary="Health check",
    description="Returns a small status object when the API process is running.",
)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/enrich-domain",
    response_model=LeadEnrichmentResponse,
    tags=["enrichment"],
    summary="Enrich one .nl domain",
    description=(
        "Normalizes the supplied domain, checks DNS and website availability, "
        "extracts public business evidence, optionally queries KvK, classifies "
        "sales relevance, and returns the structured lead JSON."
    ),
    response_description="Structured lead profile with evidence and next action.",
)
async def enrich_domain(
    request: EnrichDomainRequest, settings: Settings = Depends(get_settings)
) -> LeadEnrichmentResponse:
    pipeline = LeadEnrichmentPipeline(settings)
    return await pipeline.enrich(request)
