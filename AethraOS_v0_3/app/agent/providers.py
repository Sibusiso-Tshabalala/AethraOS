from openai import OpenAI
from app.config import settings

def create_client():
    if settings.ai_provider == "lmstudio":
        return OpenAI(base_url=settings.ai_base_url or "http://localhost:1234/v1",
                      api_key=settings.ai_api_key or "lm-studio-local")
    if settings.ai_provider == "ollama":
        return OpenAI(base_url=settings.ai_base_url or "http://localhost:11434/v1",
                      api_key=settings.ai_api_key or "ollama-local")
    if settings.ai_provider == "openai":
        if not settings.ai_api_key:
            raise RuntimeError("AI_PROVIDER=openai requires AI_API_KEY.")
        return OpenAI(base_url=settings.ai_base_url or "https://api.openai.com/v1",
                      api_key=settings.ai_api_key)
    raise RuntimeError("Unsupported AI_PROVIDER. Use lmstudio, ollama, or openai.")

def resolve_model(client):
    if settings.ai_model and settings.ai_model.lower() != "auto":
        return settings.ai_model
    models = client.models.list().data
    if not models:
        raise RuntimeError("No model is available. Load a model and start the local server.")
    return models[0].id
