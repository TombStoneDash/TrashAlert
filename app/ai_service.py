"""AI service for address interpretation using OpenAI or Anthropic."""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AddressInterpretation:
    """Structured result from AI address interpretation."""
    normalized_address: str
    confidence: float  # 0.0 to 1.0
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    house_number: Optional[str] = None
    street: Optional[str] = None
    reasoning: Optional[str] = None  # AI's explanation of interpretation


class AIAddressInterpreter:
    """
    AI-powered address interpretation service.

    Supports both OpenAI and Anthropic APIs with automatic fallback.
    Uses structured prompts to extract and normalize address components
    from freeform text input.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        cities_list: Optional[List[str]] = None,
        prefer_provider: str = "anthropic"  # "openai" or "anthropic"
    ):
        """
        Initialize the AI address interpreter.

        Args:
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            cities_list: List of supported city names for better matching
            prefer_provider: Which AI provider to prefer ("openai" or "anthropic")
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.cities_list = cities_list or []
        self.prefer_provider = prefer_provider

        # Lazy-load clients
        self._openai_client = None
        self._anthropic_client = None

    @property
    def openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None and self.openai_api_key:
            try:
                import openai
                self._openai_client = openai.OpenAI(api_key=self.openai_api_key)
            except ImportError:
                logger.error("OpenAI library not installed")
        return self._openai_client

    @property
    def anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None and self.anthropic_api_key:
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            except ImportError:
                logger.error("Anthropic library not installed")
        return self._anthropic_client

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI."""
        cities_context = ""
        if self.cities_list:
            cities_context = f"\n\nSupported cities (prioritize matching these):\n{', '.join(self.cities_list)}"

        return f"""You are an address parsing and normalization expert. Your task is to extract and normalize address information from freeform text.

Given freeform text that may contain an address, extract the following components:
- Full normalized address (standard format: house number, street name, city, state, ZIP)
- House number
- Street name
- City (prefer exact matches from supported cities list if available)
- State (2-letter abbreviation)
- ZIP code
- Confidence score (0.0 to 1.0) indicating how certain you are about the interpretation

Guidelines:
1. Normalize street abbreviations (St -> Street, Ave -> Avenue, Blvd -> Boulevard, Dr -> Drive, etc.)
2. Use proper capitalization (title case for street names and cities)
3. Handle incomplete addresses gracefully - extract what you can
4. If multiple possible interpretations exist, choose the most likely one
5. Be generous with partial addresses - even "123 Main, San Diego" should work
6. For ambiguous text, use context clues to infer the most likely address{cities_context}

Return your response as a JSON object with this exact structure:
{{
  "normalized_address": "123 Main Street, San Diego, CA 92101",
  "house_number": "123",
  "street": "Main Street",
  "city": "San Diego",
  "state": "CA",
  "zip_code": "92101",
  "confidence": 0.95,
  "reasoning": "Clear address with all components present"
}}

If you cannot extract a valid address, set confidence to 0.0 and explain why in the reasoning field."""

    def _build_user_prompt(self, text: str) -> str:
        """Build the user prompt with the text to interpret."""
        return f"""Parse and normalize this address:

"{text}"

Remember to return only valid JSON matching the specified structure."""

    async def interpret_with_anthropic(self, text: str) -> Optional[AddressInterpretation]:
        """
        Interpret address using Anthropic Claude.

        Args:
            text: Freeform text containing an address

        Returns:
            AddressInterpretation object or None if failed
        """
        if not self.anthropic_client:
            logger.warning("Anthropic client not available")
            return None

        try:
            logger.info(f"Interpreting address with Anthropic: {text[:100]}")

            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                system=self._build_system_prompt(),
                messages=[
                    {"role": "user", "content": self._build_user_prompt(text)}
                ]
            )

            # Extract text from response
            content = response.content[0].text

            # Parse JSON response
            result = json.loads(content)

            return AddressInterpretation(
                normalized_address=result.get("normalized_address", ""),
                confidence=float(result.get("confidence", 0.0)),
                city=result.get("city"),
                state=result.get("state"),
                zip_code=result.get("zip_code"),
                house_number=result.get("house_number"),
                street=result.get("street"),
                reasoning=result.get("reasoning")
            )

        except Exception as e:
            logger.error(f"Anthropic interpretation failed: {str(e)}")
            return None

    async def interpret_with_openai(self, text: str) -> Optional[AddressInterpretation]:
        """
        Interpret address using OpenAI GPT.

        Args:
            text: Freeform text containing an address

        Returns:
            AddressInterpretation object or None if failed
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available")
            return None

        try:
            logger.info(f"Interpreting address with OpenAI: {text[:100]}")

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": self._build_user_prompt(text)}
                ],
                temperature=0.1,  # Low temperature for more consistent parsing
                response_format={"type": "json_object"}
            )

            # Extract and parse JSON response
            content = response.choices[0].message.content
            result = json.loads(content)

            return AddressInterpretation(
                normalized_address=result.get("normalized_address", ""),
                confidence=float(result.get("confidence", 0.0)),
                city=result.get("city"),
                state=result.get("state"),
                zip_code=result.get("zip_code"),
                house_number=result.get("house_number"),
                street=result.get("street"),
                reasoning=result.get("reasoning")
            )

        except Exception as e:
            logger.error(f"OpenAI interpretation failed: {str(e)}")
            return None

    async def interpret(self, text: str) -> Optional[AddressInterpretation]:
        """
        Interpret address using available AI provider with automatic fallback.

        Tries the preferred provider first, then falls back to the alternative.

        Args:
            text: Freeform text containing an address

        Returns:
            AddressInterpretation object or None if all providers failed
        """
        providers = []

        # Set provider order based on preference
        if self.prefer_provider == "anthropic":
            providers = [
                ("anthropic", self.interpret_with_anthropic),
                ("openai", self.interpret_with_openai)
            ]
        else:
            providers = [
                ("openai", self.interpret_with_openai),
                ("anthropic", self.interpret_with_anthropic)
            ]

        # Try each provider
        for provider_name, interpret_func in providers:
            result = await interpret_func(text)
            if result and result.confidence > 0.0:
                logger.info(f"Successfully interpreted with {provider_name}: confidence={result.confidence}")
                return result

        logger.error("All AI providers failed to interpret address")
        return None


def create_ai_interpreter(cities_list: Optional[List[str]] = None) -> AIAddressInterpreter:
    """
    Factory function to create an AI interpreter with environment-based configuration.

    Args:
        cities_list: Optional list of supported cities

    Returns:
        Configured AIAddressInterpreter instance
    """
    return AIAddressInterpreter(
        cities_list=cities_list,
        prefer_provider=os.getenv("AI_PROVIDER_PREFERENCE", "anthropic")
    )
