from typing import cast
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
from utils.start_up import lifespan_start_up
from configs.endpoints_base_models import AppState, StfRequest
from manager import run_stf_agent_stream


app = FastAPI(lifespan=lifespan_start_up)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/extract-sequence-function")
async def extract_sequence_function(request: StfRequest):
    """
    Extract protein/gene sequence-to-function relationships from a research article.
    
    Args:
        request: Contains article_link and optional session_id and model configuration
        
    Returns:
        Streaming response with extraction progress and results
    """
    return StreamingResponse(
        run_stf_agent_stream(request, cast(AppState, app.state)),
        media_type="text/plain"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

    # Run: 
    # uvicorn app:app --host 0.0.0.0 --port 8080