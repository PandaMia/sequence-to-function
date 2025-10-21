import logging
from typing import List, Optional
from openai import AsyncOpenAI


logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using OpenAI API"""

    def __init__(self, openai_client: AsyncOpenAI):
        self.client = openai_client
        self.model = "text-embedding-3-small"  # 1536 dimensions, cost-effective

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding, or None if failed
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return None

            response = await self.client.embeddings.create(
                model=self.model,
                input=text.strip()
            )

            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding with {len(embedding)} dimensions")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings (or None for failed items)
        """
        try:
            if not texts:
                return []

            # Filter out empty texts but keep track of indices
            valid_texts = []
            valid_indices = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_texts.append(text.strip())
                    valid_indices.append(i)

            if not valid_texts:
                return [None] * len(texts)

            # Generate embeddings for valid texts
            response = await self.client.embeddings.create(
                model=self.model,
                input=valid_texts
            )

            # Map results back to original indices
            results = [None] * len(texts)
            for i, embedding_data in enumerate(response.data):
                original_index = valid_indices[i]
                results[original_index] = embedding_data.embedding

            logger.debug(f"Generated {len(valid_texts)} embeddings in batch")
            return results

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {str(e)}")
            return [None] * len(texts)


def create_search_text(
    gene: str,
    function: str,
    effect: str,
    longevity_association: str
) -> str:
    """
    Create searchable text from sequence data fields.

    Combines gene name, function, effect, and longevity association
    into a single text suitable for embedding.

    Args:
        gene: Gene name
        function: Function description
        effect: Effect description
        longevity_association: Longevity association description

    Returns:
        Combined text string
    """
    parts = []

    if gene:
        parts.append(f"Gene: {gene}")

    if function:
        parts.append(f"Function: {function}")

    if effect:
        parts.append(f"Effect: {effect}")

    if longevity_association:
        parts.append(f"Longevity: {longevity_association}")

    return " | ".join(parts) if parts else ""
