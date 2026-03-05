from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api_routes import router


app = FastAPI(
    title="Personal Memory Assistant API",
    description="Backend API for indexing and retrieving personal memories",
    version="1.0"
)

# Allow frontend (Streamlit) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for MVP, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/")
def root():
    return {"message": "Personal Memory Assistant API is running"}