"""Provider selection by configuration.

The one place that decides which implementation backs each Protocol. Call sites depend on
the Protocol, never on a concrete class, so flipping ``HOLOFY_PRICING_PROVIDER`` from
``mock`` to ``tcgdex`` swaps the real Cardmarket path in with no code change elsewhere.

The TCGdex provider owns a pooled HTTP client, so it is built once per process and closed
on shutdown; the factory returns that singleton rather than a fresh client per request.

Each ``match`` has an explicit ``case _:`` that raises on an unhandled backend rather than
falling through to ``None`` — adding a backend enum value without wiring it here is then a
loud failure at startup, not a confusing ``NoneType`` later.
"""

from __future__ import annotations

from app.config import (
    AuthenticityBackend,
    CatalogBackend,
    GradingBackend,
    PricingBackend,
    RecognitionBackend,
    Settings,
)
from app.providers.authenticity.mock import MockAuthenticityProvider
from app.providers.base import (
    AuthenticityProvider,
    GradingProvider,
    PricingProvider,
    RecognitionProvider,
)
from app.grading.capture_store import CaptureStore
from app.providers.grading.mock import MockGradingProvider
from app.providers.pricing.mock import MockPricingProvider
from app.providers.pricing.tcgdex import TcgdexClient
from app.providers.pricing.tcgdex_provider import TcgdexPricingProvider
from app.providers.recognition.mock import MockRecognitionProvider


def build_catalog_index(settings: Settings) -> tuple["CatalogIndex", TcgdexClient | None]:
    """Return the catalog the in-house recognizer resolves against, and the HTTP client it
    owns (if any) for the caller to close on shutdown — mirroring ``build_pricing_provider``.
    """
    from app.identify.catalog import CatalogIndex, InMemoryCatalogIndex

    match settings.catalog_provider:
        case CatalogBackend.INMEMORY:
            return InMemoryCatalogIndex(), None
        case CatalogBackend.TCGDEX:
            from app.identify.catalog_name_index import CatalogNameIndex
            from app.identify.tcgdex_catalog import TcgdexCatalogIndex

            client = TcgdexClient(
                api_root=settings.tcgdex_api_root,
                locale=settings.tcgdex_locale,
                timeout_seconds=settings.tcgdex_timeout_seconds,
            )
            # Accent-insensitive recall over the same catalog: TCGdex's name search is
            # accent-sensitive, so an OCR read that drops a diacritic ("Salameche") needs the
            # de-accented index to recover the card ("Salamèche"). Warmed at startup.
            name_index = CatalogNameIndex(client, locales=settings.tcgdex_recognition_locales)
            return (
                TcgdexCatalogIndex(
                    client,
                    locales=settings.tcgdex_recognition_locales,
                    name_index=name_index,
                ),
                client,
            )
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported catalog backend: {unknown}")


def build_recognition_provider(
    settings: Settings, capture_store: CaptureStore
) -> tuple[RecognitionProvider, TcgdexClient | None]:
    """Return the recognition provider and the catalog HTTP client it owns (if any).

    The mock owns nothing (``None``); the in-house recognizer may own a TCGdex catalog client
    the caller (app lifespan) closes on shutdown, exactly like the pricing client.
    """
    match settings.recognition_provider:
        case RecognitionBackend.MOCK:
            return MockRecognitionProvider(), None
        case RecognitionBackend.INHOUSE:
            # Imported lazily: the OCR stack (onnxruntime) is only needed for this backend, so
            # mock/test runs never pay its import cost. The provider reads the uploaded stills
            # from the same capture store the pre-grade uses.
            from app.identify.embedding_index import (
                embeddings_path_for,
                load_embedding_index,
            )
            from app.identify.image_index import load_image_index
            from app.identify.presence import HeuristicCardPresence
            from app.identify.provider import InHouseRecognitionProvider
            from app.identify.resolver import CardResolver
            from app.identify.vision.ocr import RapidOcrEngine
            from app.identify.vision.reader import VisionCardReader
            from app.identify.visual_provider import VisualRecognitionProvider
            from app.identify.visual_resolver import VisualCardResolver

            catalog, catalog_client = build_catalog_index(settings)
            reader = VisionCardReader(RapidOcrEngine())
            # The OCR-against-TCGdex text recognizer: the fallback for cards not yet fingerprinted
            # in the artwork index (and the whole recognizer when no index is deployed).
            text_provider = InHouseRecognitionProvider(
                store=capture_store,
                reader=reader,
                resolver=CardResolver(catalog),
                presence=HeuristicCardPresence(),
            )
            # Visual-first when an artwork index is present; a missing/empty index makes the
            # wrapper a transparent pass-through to the text provider (see VisualRecognitionProvider).
            # The embedding index (learned descriptor) is primary; the perceptual-hash index is the
            # fallback for a partial deploy. Both are loaded from build artefacts that degrade to
            # empty when undeployed, so this is a data step, not a code switch.
            image_index = load_image_index(settings.image_index_path)
            embeddings_path = settings.image_embeddings_path or str(
                embeddings_path_for(settings.image_index_path)
            )
            embedding_index = load_embedding_index(settings.image_index_path, embeddings_path)
            provider = VisualRecognitionProvider(
                store=capture_store,
                reader=reader,
                image_index=image_index,
                visual_resolver=VisualCardResolver(),
                fallback=text_provider,
                embedding_index=embedding_index,
                model_path=settings.recognition_model_path,
                min_similarity=settings.recognition_visual_min_similarity,
                max_match_distance=settings.recognition_visual_max_distance,
            )
            # Surface the accent-insensitive name index so the app lifespan can warm it at
            # startup (the bulk catalog fetch is too slow to first pay on a user's scan).
            provider.catalog_name_index = getattr(catalog, "_name_index", None)
            return provider, catalog_client
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported recognition backend: {unknown}")


class _CloseAll:
    """Close several HTTP clients as one — the lifespan only knows to ``aclose`` the single handle
    the factory returns, but the pokémontcg provider owns its own client *and* a TCGdex fallback."""

    def __init__(self, *closeables: object) -> None:
        self._closeables = closeables

    async def aclose(self) -> None:
        for c in self._closeables:
            closer = getattr(c, "aclose", None)
            if closer is not None:
                await closer()


def build_pricing_provider(
    settings: Settings,
) -> tuple[PricingProvider, object | None]:
    """Return the configured pricing provider and the HTTP client(s) it owns, if any.

    The caller (app lifespan) keeps the handle to ``aclose`` it on shutdown; for the mock there
    is nothing to close, hence ``None``.
    """
    match settings.pricing_provider:
        case PricingBackend.MOCK:
            return MockPricingProvider(), None
        case PricingBackend.TCGDEX:
            client = TcgdexClient(
                api_root=settings.tcgdex_api_root,
                locale=settings.tcgdex_locale,
                timeout_seconds=settings.tcgdex_timeout_seconds,
            )
            return _cached(TcgdexPricingProvider(client), settings), client
        case PricingBackend.POKEMONTCG:
            from app.providers.pricing.pokemontcg import PokemonTcgClient
            from app.providers.pricing.pokemontcg_provider import PokemonTcgPricingProvider

            pt_client = PokemonTcgClient(
                api_root=settings.pokemontcg_api_root,
                api_key=settings.pokemontcg_api_key,
                timeout_seconds=settings.pokemontcg_timeout_seconds,
            )
            # Cardmarket-EUR fallback for cards pokémontcg.io doesn't carry, so EUR coverage never
            # drops below the TCGdex baseline while USD is added for everything it does carry.
            tcgdex_client = TcgdexClient(
                api_root=settings.tcgdex_api_root,
                locale=settings.tcgdex_locale,
                timeout_seconds=settings.tcgdex_timeout_seconds,
            )
            provider = PokemonTcgPricingProvider(
                pt_client, fallback=TcgdexPricingProvider(tcgdex_client)
            )
            # A TTL cache fronts the network sources so the Vault's per-card pricing doesn't fan out
            # to dozens of upstream calls per view (or trip a keyless rate limit).
            return _cached(provider, settings), _CloseAll(pt_client, tcgdex_client)
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported pricing backend: {unknown}")


def _cached(provider: PricingProvider, settings: Settings) -> PricingProvider:
    """Front a network pricing provider with the in-memory TTL read-through cache."""
    from app.providers.pricing.cache import CachedPricingProvider

    return CachedPricingProvider(provider, ttl_seconds=settings.pricing_cache_ttl_seconds)


def build_grading_provider(
    settings: Settings, capture_store: CaptureStore
) -> GradingProvider:
    """Return the configured grading provider for the corners/edges/surface scores.

    Centering is not selected here — it is measured in-house by the pre-grade service. The
    in-house grader reads the capture's bytes from the same store the recognizer uses.
    """
    match settings.grading_provider:
        case GradingBackend.MOCK:
            return MockGradingProvider()
        case GradingBackend.INHOUSE:
            from app.providers.grading.inhouse import InHouseGradingProvider

            return InHouseGradingProvider(capture_store)
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported grading backend: {unknown}")


def build_authenticity_provider(
    settings: Settings, capture_store: CaptureStore
) -> AuthenticityProvider:
    """Return the configured provider for the per-signal authenticity reads.

    The catalog-existence cross-check is not selected here — it is a deterministic
    reference-DB lookup the authenticity service owns, not a model behind this seam. The
    in-house provider reads the capture's bytes from the same store the recognizer/grader use.
    """
    match settings.authenticity_provider:
        case AuthenticityBackend.MOCK:
            return MockAuthenticityProvider()
        case AuthenticityBackend.INHOUSE:
            from app.identify.embedding_index import (
                embeddings_path_for,
                load_embedding_index,
            )
            from app.providers.authenticity.inhouse import InHouseAuthenticityProvider

            # Share the recognizer's embedding index + model for the artwork-reference signal; a
            # missing/undeployed pair degrades the provider to its visual+catalog reads (the index
            # loads empty and the signal is simply skipped).
            embeddings_path = settings.image_embeddings_path or str(
                embeddings_path_for(settings.image_index_path)
            )
            embedding_index = load_embedding_index(settings.image_index_path, embeddings_path)
            return InHouseAuthenticityProvider(
                capture_store,
                embedding_index=embedding_index,
                model_path=settings.recognition_model_path,
            )
        case unknown:  # pragma: no cover - guards an unwired enum value
            raise ValueError(f"unsupported authenticity backend: {unknown}")
