"""Sequence-to-Function FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app_startup.lifespan import lifespan
from api.stf.router import router as stf_router
from testing_endpoints.router import get_testing_router

# Create FastAPI app with lifespan management
app = FastAPI(lifespan=lifespan)
testing_router = get_testing_router(lambda: app.state)
app.include_router(stf_router)
app.include_router(testing_router)


@app.get("/")
async def serve_chat_ui():
    """Serve the chat UI interface."""
    return FileResponse("chat_ui.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from app_startup.lifespan import configure_logging

    configure_logging()
    uvicorn.run(app, host="0.0.0.0", port=8080, use_colors=True)
