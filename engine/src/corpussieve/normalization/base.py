from typing import Any, NamedTuple, Protocol

from corpussieve.contracts.corpus import CorpusRecord
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode


class NormalizedDoc(NamedTuple):
    title: str
    frontmatter: dict[str, Any]
    markdown: str
    warnings: list[str]


class Normalizer(Protocol):
    """Protocol for corpus normalizers."""

    def normalize(self, record: CorpusRecord) -> NormalizedDoc: ...


_NORMALIZERS: dict[str, type[Normalizer]] = {}


def register_normalizer(name: str, cls: type[Normalizer]) -> None:
    """Register normalizer class under name."""
    _NORMALIZERS[name] = cls


def get_normalizer(name: str = "wikitext-md-v1") -> Normalizer:
    """Get instantiated normalizer by registered name."""
    if name not in _NORMALIZERS:
        from corpussieve.normalization.wikitext_md import WikitextMarkdownNormalizer

        register_normalizer("wikitext-md-v1", WikitextMarkdownNormalizer)

    cls = _NORMALIZERS.get(name)
    if not cls:
        raise CorpusSieveError(
            ErrorCode.INTERNAL_ERROR,
            f"Unknown normalizer '{name}'",
        )
    return cls()
