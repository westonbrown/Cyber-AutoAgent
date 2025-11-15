"""Models.dev API client with caching and fallback support.

This module provides a Python client for the models.dev API, which maintains
an authoritative database of AI model specifications, pricing, and capabilities
across 58+ providers and 500+ models.

Key Features:
- Automatic model limit detection (context window, max output tokens)
- Model capability detection (reasoning, tool calling, attachments, etc.)
- Pricing information per million tokens
- Three-tier fallback system: cache → live API → embedded snapshot
- Flexible model ID resolution (supports multiple formats)
- 24-hour cache TTL to minimize API calls

Usage:
    >>> from modules.config.models_dev_client import get_models_client
    >>>
    >>> client = get_models_client()
    >>> limits = client.get_limits("azure/gpt-5")
    >>> print(f"Context: {limits.context}, Output: {limits.output}")
    Context: 272000, Output: 128000

Architecture:
    ModelsDevClient
    ├─ _get_data() → [Cache → API → Snapshot]
    ├─ get_model_info() → ModelInfo
    ├─ get_limits() → ModelLimits
    ├─ get_capabilities() → ModelCapabilities
    └─ get_pricing() → ModelPricing

See: https://models.dev
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelLimits:
    """Model token limits.

    Attributes:
        context: Maximum input tokens (context window)
        output: Maximum output tokens (completion limit)
    """
    context: int
    output: int


@dataclass(frozen=True)
class ModelPricing:
    """Model pricing per million tokens in USD.

    Attributes:
        input: Cost per million input tokens
        output: Cost per million output tokens
        cache_read: Cost per million cached read tokens (optional)
        cache_write: Cost per million cached write tokens (optional)
        reasoning: Cost per million reasoning tokens (optional, for o1/o3 models)
    """
    input: float
    output: float
    cache_read: Optional[float] = None
    cache_write: Optional[float] = None
    reasoning: Optional[float] = None


@dataclass(frozen=True)
class ModelCapabilities:
    """Model capabilities and features.

    Attributes:
        name: Human-readable model name
        reasoning: Supports reasoning/chain-of-thought (o1, o3, Claude thinking)
        tool_call: Supports tool/function calling
        attachment: Supports file attachments
        temperature: Supports temperature parameter
        structured_output: Supports structured output feature (optional)
        knowledge: Knowledge cutoff date (YYYY-MM or YYYY-MM-DD format)
        release_date: First public release date
        last_updated: Most recent update date
        open_weights: Model weights are publicly available
        modalities_input: Supported input modalities (text, image, audio, video, pdf)
        modalities_output: Supported output modalities (text, image, audio)
    """
    name: str
    reasoning: bool
    tool_call: bool
    attachment: bool
    temperature: bool
    structured_output: Optional[bool]
    knowledge: Optional[str]
    release_date: Optional[str]
    last_updated: Optional[str]
    open_weights: bool
    modalities_input: List[str]
    modalities_output: List[str]


@dataclass(frozen=True)
class ModelInfo:
    """Complete model information.

    Attributes:
        provider: Provider ID (e.g., 'anthropic', 'azure', 'amazon-bedrock')
        model_id: Model identifier within provider
        full_id: Full model ID (provider/model_id)
        capabilities: Model capabilities and features
        limits: Token limits
        pricing: Pricing information (None if not available)
    """
    provider: str
    model_id: str
    full_id: str
    capabilities: ModelCapabilities
    limits: ModelLimits
    pricing: Optional[ModelPricing]


class ModelsDevClient:
    """Client for models.dev API with intelligent caching and fallback.

    This client fetches model metadata from models.dev with a three-tier approach:
    1. Local cache (~/.cache/cyber-autoagent/models.json) - 24h TTL
    2. Live API (https://models.dev/api.json) - if cache expired
    3. Embedded snapshot (models_snapshot.json) - if API unavailable

    The embedded snapshot is bundled with the application and updated weekly
    via CI/CD to ensure offline functionality.

    Example:
        >>> client = ModelsDevClient()
        >>>
        >>> # Get complete model info
        >>> info = client.get_model_info("azure/gpt-5")
        >>> print(f"{info.capabilities.name}: {info.limits.output} max tokens")
        GPT-5: 128000 max tokens
        >>>
        >>> # Get just limits
        >>> limits = client.get_limits("anthropic/claude-sonnet-4-5-20250929")
        >>> print(f"Context: {limits.context:,}")
        Context: 200,000
        >>>
        >>> # Check capabilities
        >>> caps = client.get_capabilities("moonshot/kimi-k2-thinking")
        >>> if caps.reasoning:
        ...     print("This model supports extended reasoning")
        This model supports extended reasoning
    """

    API_URL = "https://models.dev/api.json"
    CACHE_TTL = timedelta(hours=24)

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize models.dev client.

        Args:
            cache_dir: Custom cache directory (default: ~/.cache/cyber-autoagent)
        """
        self.cache_dir = cache_dir or Path.home() / ".cache" / "cyber-autoagent"
        self.cache_file = self.cache_dir / "models.json"
        self.snapshot_file = Path(__file__).parent / "models_snapshot.json"
        self._data: Optional[Dict] = None
        self._data_source: Optional[str] = None

    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Get complete model information.

        Supports multiple model ID formats:
        - "provider/model" (e.g., "azure/gpt-5")
        - "model" (searches across providers, e.g., "gpt-5")
        - Bedrock ARN format (e.g., "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

        Args:
            model_id: Model identifier in any supported format

        Returns:
            ModelInfo if found, None otherwise
        """
        data = self._get_data()

        # Try direct lookup
        info = self._lookup_model(data, model_id)
        if info:
            return info

        # Try fuzzy matching for common aliases
        info = self._fuzzy_lookup(data, model_id)
        if info:
            return info

        logger.debug(f"Model not found: {model_id}")
        return None

    def get_limits(self, model_id: str) -> Optional[ModelLimits]:
        """Get model token limits.

        Args:
            model_id: Model identifier

        Returns:
            ModelLimits with context and output token limits, or None if not found
        """
        info = self.get_model_info(model_id)
        return info.limits if info else None

    def get_capabilities(self, model_id: str) -> Optional[ModelCapabilities]:
        """Get model capabilities and features.

        Args:
            model_id: Model identifier

        Returns:
            ModelCapabilities with feature flags, or None if not found
        """
        info = self.get_model_info(model_id)
        return info.capabilities if info else None

    def get_pricing(self, model_id: str) -> Optional[ModelPricing]:
        """Get model pricing information.

        Args:
            model_id: Model identifier

        Returns:
            ModelPricing per million tokens (USD), or None if not available
        """
        info = self.get_model_info(model_id)
        return info.pricing if info else None

    def list_providers(self) -> List[str]:
        """Get list of all available providers.

        Returns:
            List of provider IDs
        """
        data = self._get_data()
        return sorted(data.keys())

    def list_models(self, provider: Optional[str] = None) -> List[str]:
        """Get list of available models.

        Args:
            provider: Filter by provider ID (optional)

        Returns:
            List of model IDs (or full IDs if no provider filter)
        """
        data = self._get_data()

        if provider:
            provider_data = data.get(provider, {})
            models_data = provider_data.get('models', {})
            return sorted(models_data.keys())

        # Return all models across all providers
        all_models = []
        for provider_id, provider_data in data.items():
            if 'models' in provider_data:
                for model_id in provider_data['models'].keys():
                    all_models.append(f"{provider_id}/{model_id}")
        return sorted(all_models)

    def get_data_source(self) -> str:
        """Get the source of current model data.

        Returns:
            "cache", "api", or "snapshot"
        """
        if self._data_source is None:
            self._get_data()
        return self._data_source or "unknown"

    def clear_cache(self):
        """Clear local cache to force fresh API fetch."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.info("Cache cleared")
        self._data = None
        self._data_source = None

    def _get_data(self) -> Dict:
        """Get models data from cache, API, or snapshot (in priority order).

        Priority:
        1. Memory cache (already loaded)
        2. Disk cache (if valid and not expired)
        3. Live API (https://models.dev/api.json)
        4. Embedded snapshot (bundled with application)

        Returns:
            Dictionary with provider → models → metadata structure
        """
        # Return cached data if already loaded
        if self._data:
            return self._data

        # Try disk cache
        if self._is_cache_valid():
            try:
                logger.debug(f"Loading models from cache: {self.cache_file}")
                with open(self.cache_file) as f:
                    self._data = json.load(f)
                    self._data_source = "cache"
                    logger.info(f"Loaded models from cache ({len(self._data)} providers)")
                    return self._data
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        # Try live API
        try:
            logger.info(f"Fetching models from API: {self.API_URL}")

            # Use httpx if available, fall back to urllib
            try:
                import httpx
                response = httpx.get(self.API_URL, timeout=10.0, follow_redirects=True)
                response.raise_for_status()
                self._data = response.json()
            except ImportError:
                import urllib.request
                with urllib.request.urlopen(self.API_URL, timeout=10) as response:
                    self._data = json.loads(response.read().decode())

            self._data_source = "api"
            logger.info(f"Fetched models from API ({len(self._data)} providers)")

            # Save to cache
            self._save_cache(self._data)
            return self._data

        except Exception as e:
            logger.warning(f"Failed to fetch from API: {e}")

        # Fallback to embedded snapshot
        if self.snapshot_file.exists():
            logger.info(f"Using embedded snapshot: {self.snapshot_file}")
            try:
                with open(self.snapshot_file) as f:
                    self._data = json.load(f)
                    self._data_source = "snapshot"
                    logger.info(f"Loaded models from snapshot ({len(self._data)} providers)")
                    return self._data
            except Exception as e:
                logger.error(f"Failed to load snapshot: {e}")
        else:
            logger.warning(f"Snapshot file not found: {self.snapshot_file}")

        # No data available
        logger.error("No model data available (cache, API, and snapshot all failed)")
        return {}

    def _is_cache_valid(self) -> bool:
        """Check if cache exists and is not expired.

        Returns:
            True if cache is valid and fresh
        """
        if not self.cache_file.exists():
            return False

        try:
            mtime = datetime.fromtimestamp(self.cache_file.stat().st_mtime)
            age = datetime.now() - mtime
            is_valid = age < self.CACHE_TTL

            if not is_valid:
                logger.debug(f"Cache expired (age: {age}, TTL: {self.CACHE_TTL})")

            return is_valid
        except Exception as e:
            logger.warning(f"Error checking cache validity: {e}")
            return False

    def _save_cache(self, data: Dict):
        """Save data to disk cache.

        Args:
            data: Models data to cache
        """
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved cache: {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _lookup_model(self, data: Dict, model_id: str) -> Optional[ModelInfo]:
        """Lookup model with exact matching.

        Args:
            data: Models data dictionary
            model_id: Model identifier to look up

        Returns:
            ModelInfo if found, None otherwise
        """
        # Handle provider/model format
        if '/' in model_id:
            parts = model_id.split('/', 1)
            if len(parts) == 2:
                provider, model = parts
                return self._parse_model(data, provider, model)

        # Search across all providers for exact match
        for provider_id, provider_data in data.items():
            if 'models' not in provider_data:
                continue

            if model_id in provider_data['models']:
                return self._parse_model(data, provider_id, model_id)

        return None

    def _fuzzy_lookup(self, data: Dict, model_id: str) -> Optional[ModelInfo]:
        """Fuzzy lookup with alias resolution and normalization.

        Handles:
        - Version normalization (3.5 → 3-5)
        - Bedrock ARN format (us.anthropic.claude-* → claude-*)
        - Provider aliases (moonshot → moonshotai)
        - Common aliases

        Args:
            data: Models data dictionary
            model_id: Model identifier to look up

        Returns:
            ModelInfo if found, None otherwise
        """
        # Provider aliases mapping
        provider_aliases = {
            'moonshot': 'moonshotai',
            'anthropic': 'amazon-bedrock',  # When used with ARN format
            'gemini': 'google',  # Gemini models are under google provider
        }

        # Handle provider/model format with alias resolution
        if '/' in model_id:
            parts = model_id.split('/', 1)
            if len(parts) == 2:
                provider, model = parts
                # Try with aliased provider
                if provider in provider_aliases:
                    aliased_id = f"{provider_aliases[provider]}/{model}"
                    info = self._lookup_model(data, aliased_id)
                    if info:
                        return info

        # Normalize dots to dashes (e.g., claude-3.5-haiku → claude-3-5-haiku)
        normalized = model_id.replace('.', '-')
        if normalized != model_id:
            info = self._lookup_model(data, normalized)
            if info:
                return info

        # Handle Bedrock ARN format (us.anthropic.claude-sonnet-4-5-20250929-v1:0)
        if model_id.startswith('us.') or model_id.startswith('anthropic.'):
            # Extract the actual model name
            parts = model_id.split('.')
            if len(parts) >= 2:
                # Try "anthropic/claude-sonnet-4-5-20250929"
                bedrock_model = '.'.join(parts[1:])
                info = self._lookup_model(data, f"amazon-bedrock/{bedrock_model}")
                if info:
                    return info

        # Try with -latest suffix removed
        if model_id.endswith('-latest'):
            base = model_id[:-7]
            info = self._lookup_model(data, base)
            if info:
                return info

        return None

    def _parse_model(self, data: Dict, provider: str, model: str) -> Optional[ModelInfo]:
        """Parse model data into ModelInfo.

        Args:
            data: Models data dictionary
            provider: Provider ID
            model: Model ID within provider

        Returns:
            ModelInfo with parsed data, or None if parsing fails
        """
        try:
            provider_data = data[provider]
            model_data = provider_data['models'][model]

            # Parse capabilities
            capabilities = ModelCapabilities(
                name=model_data.get('name', model),
                reasoning=model_data.get('reasoning', False),
                tool_call=model_data.get('tool_call', False),
                attachment=model_data.get('attachment', False),
                temperature=model_data.get('temperature', True),
                structured_output=model_data.get('structured_output'),
                knowledge=model_data.get('knowledge'),
                release_date=model_data.get('release_date'),
                last_updated=model_data.get('last_updated'),
                open_weights=model_data.get('open_weights', False),
                modalities_input=model_data.get('modalities', {}).get('input', ['text']),
                modalities_output=model_data.get('modalities', {}).get('output', ['text']),
            )

            # Parse limits
            limit_data = model_data.get('limit', {})
            limits = ModelLimits(
                context=limit_data.get('context', 0),
                output=limit_data.get('output', 0),
            )

            # Parse pricing (optional)
            pricing = None
            if 'cost' in model_data:
                cost_data = model_data['cost']
                pricing = ModelPricing(
                    input=cost_data.get('input', 0.0),
                    output=cost_data.get('output', 0.0),
                    cache_read=cost_data.get('cache_read'),
                    cache_write=cost_data.get('cache_write'),
                    reasoning=cost_data.get('reasoning'),
                )

            return ModelInfo(
                provider=provider,
                model_id=model,
                full_id=f"{provider}/{model}",
                capabilities=capabilities,
                limits=limits,
                pricing=pricing,
            )
        except (KeyError, TypeError) as e:
            logger.debug(f"Failed to parse model {provider}/{model}: {e}")
            return None


# Global singleton instance
_client: Optional[ModelsDevClient] = None


def get_models_client() -> ModelsDevClient:
    """Get global models.dev client instance (singleton pattern).

    Returns:
        Shared ModelsDevClient instance
    """
    global _client
    if _client is None:
        _client = ModelsDevClient()
    return _client


# Public API
__all__ = [
    'ModelLimits',
    'ModelPricing',
    'ModelCapabilities',
    'ModelInfo',
    'ModelsDevClient',
    'get_models_client',
]
