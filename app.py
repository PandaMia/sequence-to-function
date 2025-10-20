from typing import cast
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, FileResponse
from utils.start_up import lifespan_start_up
from configs.endpoints_base_models import AppState, StfRequest
from manager import run_stf_agent_stream


app = FastAPI(lifespan=lifespan_start_up)


@app.get("/")
async def serve_chat_ui():
    """Serve the chat UI interface."""
    return FileResponse("chat_ui.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/extract-sequence-function")
async def extract_sequence_function(
    request: StfRequest,
    session_id: str = Query(..., alias="session-id"),
):
    """
    Extract protein/gene sequence-to-function relationships from a research article.
    
    Args:
        request: Contains article_link and optional session_id and model configuration
        
    Returns:
        Streaming response with extraction progress and results
    """
    return StreamingResponse(
        run_stf_agent_stream(request, cast(AppState, app.state), session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


if __name__ == "__main__":
    import uvicorn
    from utils.start_up import configure_logging
    configure_logging()
    uvicorn.run(app, host="0.0.0.0", port=8080)

    # Run: 
    # uvicorn app:app --host 0.0.0.0 --port 8080