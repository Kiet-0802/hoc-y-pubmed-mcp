"""Remote MCP service. Requires the official `mcp` Python package on the host."""
import os
from starlette.responses import PlainTextResponse, JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pubmed import search_medical_literature as search_impl, fetch_medical_article as fetch_impl

# Accept the actual HTTPS hostname rather than the SDK's localhost-only default.
# Keep DNS-rebinding protection enabled and restrict accepted hosts/origins.
PUBLIC_HOST = "hoc-y-pubmed-mcp.onrender.com"
SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        PUBLIC_HOST,
        f"{PUBLIC_HOST}:*",
        "127.0.0.1:*",
        "localhost:*",
    ],
    allowed_origins=[
        "https://chatgpt.com",
        "https://platform.openai.com",
        "https://chat.openai.com",
        f"https://{PUBLIC_HOST}",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
)
mcp = FastMCP(
    'Hoc Y Evidence',
    stateless_http=True,
    json_response=True,
    transport_security=SECURITY,
)
READ_ONLY_PUBLIC = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)

@mcp.tool(annotations=READ_ONLY_PUBLIC)
async def search_medical_literature(query: str, study_type: str = 'any', since_year: int | None = None, max_results: int = 5) -> dict:
    """Search NCBI PubMed for peer-reviewed medical literature by a study question. Optional study_type: any, systematic_review, guideline, randomized_trial, observational. Returns publication metadata, not conclusions about evidence certainty. Never send patient identifiers."""
    return await search_impl(query, study_type, since_year, max_results)

@mcp.tool(annotations=READ_ONLY_PUBLIC)
async def fetch_medical_article(pmid: str) -> dict:
    """Retrieve PubMed citation metadata and abstract for a verified numeric PMID. Useful for reviewing study scope, outcomes and dates; abstracts cannot replace full-text appraisal or check that clinical guidelines are current."""
    return await fetch_impl(pmid)

_mcp_app = mcp.streamable_http_app()

async def app(scope, receive, send):
    """MCP app with a separate verification challenge/health endpoint."""
    if scope['type'] == 'http' and scope['path'] == '/.well-known/openai-apps-challenge':
        challenge = os.getenv('OPENAI_APPS_CHALLENGE_TOKEN', '')
        resp = PlainTextResponse(challenge if challenge else 'not configured', status_code=200 if challenge else 404)
        await resp(scope, receive, send)
    elif scope['type'] == 'http' and scope['path'] == '/healthz':
        await JSONResponse({'status':'ok'})(scope, receive, send)
    else:
        await _mcp_app(scope, receive, send)
