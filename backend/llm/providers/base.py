from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    async def validate(self) -> None: ...
