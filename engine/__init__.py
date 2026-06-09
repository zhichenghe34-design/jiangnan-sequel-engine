"""江南续写引擎 (engine) — M0 脚手架。

知识层:schema(卡片) + structstore(SQLite 精确查询) + vectorstore(语义召回) +
quotefree(原文复制拦截)。生成层/校验层在后续 M2 接入。
"""
from .schema import (
    CardType,
    ForeshadowStatus,
    BaseCard,
    FingerprintCard,
    SettingCard,
    CharacterCard,
    CharacterState,
    ForeshadowLedger,
    ChapterSynopsis,
    CARD_CLASSES,
)
from .structstore import StructStore
from .vectorstore import VectorStore, InMemoryVectorStore
from . import quotefree
from .skilladapter import SkillAdapter
from .llm import LLMClient, StubLLM
from .deepseek_client import DeepSeekClient
from .pipeline import (
    RetrievedContext,
    EvalResult,
    retrieve,
    build_prompt,
    evaluate,
    writeback,
)
from .engine import ContinuationIntent, ContinuationResult, ContinuationEngine
from .ingest import IngestReport, card_from_dict, load_cards, ingest, ingest_path
from .writeback import cards_from_writeback
from .embedding import EmbeddingFunction, HashEmbedding, APIEmbedding, EmbeddingVectorStore

__all__ = [
    "CardType",
    "ForeshadowStatus",
    "BaseCard",
    "FingerprintCard",
    "SettingCard",
    "CharacterCard",
    "CharacterState",
    "ForeshadowLedger",
    "ChapterSynopsis",
    "CARD_CLASSES",
    "StructStore",
    "VectorStore",
    "InMemoryVectorStore",
    "quotefree",
    # M2
    "SkillAdapter",
    "LLMClient",
    "StubLLM",
    "DeepSeekClient",
    "RetrievedContext",
    "EvalResult",
    "retrieve",
    "build_prompt",
    "evaluate",
    "writeback",
    "ContinuationIntent",
    "ContinuationResult",
    "ContinuationEngine",
    # M1
    "IngestReport",
    "card_from_dict",
    "load_cards",
    "ingest",
    "ingest_path",
    # M3
    "cards_from_writeback",
    # M1c
    "EmbeddingFunction",
    "HashEmbedding",
    "APIEmbedding",
    "EmbeddingVectorStore",
]
