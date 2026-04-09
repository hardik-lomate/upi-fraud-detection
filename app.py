"""Root ASGI entrypoint for production process managers."""

from backend.app.main import app


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
