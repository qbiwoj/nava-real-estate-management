from openai import AsyncOpenAI

from app.config import settings

# Module-level client — patch target in tests: app.services.embeddings.openai_client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_embedding(text: str) -> list[float]:
    """
    Call OpenAI text-embedding-3-small for `text`.
    Returns a list of 1536 floats.
    """
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
