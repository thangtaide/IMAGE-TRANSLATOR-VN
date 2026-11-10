from __future__ import annotations

from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    online = False

    @property
    @abstractmethod
    def identity(self) -> str:
        """Include model/endpoint version in cache identity."""

    @abstractmethod
    def translate(self, text: str, source: str, target: str = "vi") -> str:
        pass

    def translate_batch(self, texts: list[str], source: str, target: str = "vi") -> list[str]:
        return [self.translate(text, source, target) for text in texts]


class OfflineTranslationProvider(TranslationProvider):
    online = False
