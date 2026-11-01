# Học Y PubMed MCP service

Prototype server for a **real**, read-only PubMed MCP integration. Uses NCBI E-utilities; no AI API key required. Two tools: `search_medical_literature` and `fetch_medical_article`.

## Run locally

```sh
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Test with MCP Inspector (Streamable HTTP): `http://127.0.0.1:8000/mcp`.

## Deploy

Host the server on a stable, public HTTPS service. Set `NCBI_CONTACT_EMAIL` to a developer contact address registered with NCBI if needed, and optionally `NCBI_API_KEY`. Use one worker process to respect the built-in request pacing. Do not commit secrets. Configure an infrastructure-level abuse rate limit and outbound connections restricted to NCBI before making the endpoint public.

When OpenAI asks for domain verification, set `OPENAI_APPS_CHALLENGE_TOKEN` to the exact token, restart the service, and check `https://YOUR-HOST/.well-known/openai-apps-challenge` (plain text). You should set it only when the portal has issued your token.

Update `hoc-y-plugin/mcp.json` to `https://YOUR-HOST/mcp` (with your actual host) and create a **new** With MCP plugin. You cannot add an MCP to an existing skills-only draft.

**Not submission-ready until** live deployment, real protocol integration testing, domain verification, tool scan, privacy policy and identity check, and human academic review. This package intentionally uses a placeholder hostname.

## Privacy and limitations

Do not send patient identifiers or protected medical data. Queries sent to NCBI are transmitted to a third party. The tools search PubMed metadata and abstracts; they do not access Cochrane full text, appraise risk of bias, perform GRADE, or guarantee guidelines are current. The NCBI public API without an API key is limited to 3 requests/second per originating IP. For multi-instance deployment use an infrastructure-wide limiter.

## Local tests

`python -m pytest -q tests` (tests use mocked PubMed XML; cannot prove live API or SDK interoperability).
