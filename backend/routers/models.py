from fastapi import APIRouter
from models import ModelInfo

router = APIRouter()

# Available models configuration
AVAILABLE_MODELS = [
    ModelInfo(
        id="gemma-4b",
        name="Gemma 4B",
        provider="local",
        description="Fast local inference via Ollama",
        available=True,
    ),
    ModelInfo(
        id="gemma-27b",
        name="Gemma 27B",
        provider="local",
        description="High-quality local inference",
        available=True,
    ),
    ModelInfo(
        id="qwen-32b",
        name="Qwen 32B",
        provider="local",
        description="Best local model (M4 96GB)",
        available=True,
    ),
    ModelInfo(
        id="kimi-k2.5",
        name="Kimi K2.5",
        provider="cloud",
        description="OpenRouter cloud fallback",
        available=True,
    ),
]


@router.get("/models", response_model=list[ModelInfo])
async def list_models():
    # TODO: Check Ollama availability dynamically
    return AVAILABLE_MODELS
