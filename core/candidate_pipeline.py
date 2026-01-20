"""
Artvision Candidate Pipeline
Адаптация X Algorithm candidate-pipeline для рекомендательных систем

Архитектура (как у X):
1. Sources → собирают кандидатов
2. Hydrators → обогащают данными
3. Filters → отсеивают неподходящих
4. Scorers → скорят кандидатов
5. Selectors → выбирают top-N

Вдохновлено: https://github.com/xai-org/x-algorithm/candidate-pipeline
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TypeVar, Generic
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class Candidate(Generic[T]):
    """Кандидат для рекомендации"""
    id: str
    data: T
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    source: str = "unknown"


@dataclass
class PipelineContext:
    """Контекст выполнения пайплайна"""
    user_id: Optional[str] = None
    user_history: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    request_params: Dict[str, Any] = field(default_factory=dict)


# === Abstract Base Classes (как trait-ы в Rust у X) ===

class Source(ABC):
    """
    Source - источник кандидатов
    Аналог Thunder (in-network) и Phoenix (out-of-network) у X
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def fetch(self, context: PipelineContext, limit: int = 100) -> List[Candidate]:
        """Получить кандидатов из источника"""
        pass


class Hydrator(ABC):
    """
    Hydrator - обогащение данных
    Добавляет метаданные к кандидатам (engagement history, user data и т.д.)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def hydrate(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        """Обогатить кандидатов данными"""
        pass


class Filter(ABC):
    """
    Filter - фильтрация кандидатов
    Убирает неподходящих (уже просмотренные, заблокированные и т.д.)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        """Отфильтровать кандидатов"""
        pass


class Scorer(ABC):
    """
    Scorer - скоринг кандидатов
    Рассчитывает weighted score по сигналам
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def score(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        """Проставить score кандидатам"""
        pass


class Selector(ABC):
    """
    Selector - финальный отбор
    Выбирает top-N с учётом diversity и других факторов
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def select(self, candidates: List[Candidate], context: PipelineContext, limit: int) -> List[Candidate]:
        """Выбрать финальных кандидатов"""
        pass


# === Pipeline Executor ===

class CandidatePipeline:
    """
    Исполнитель пайплайна рекомендаций
    
    Запускает sources и hydrators параллельно где возможно,
    с настраиваемой обработкой ошибок и логированием.
    """
    
    def __init__(
        self,
        sources: List[Source],
        hydrators: List[Hydrator],
        filters: List[Filter],
        scorers: List[Scorer],
        selectors: List[Selector],
        max_workers: int = 4,
        fail_open: bool = True  # продолжать при ошибках отдельных компонентов
    ):
        self.sources = sources
        self.hydrators = hydrators
        self.filters = filters
        self.scorers = scorers
        self.selectors = selectors
        self.max_workers = max_workers
        self.fail_open = fail_open
    
    def execute(self, context: PipelineContext, limit: int = 10) -> List[Candidate]:
        """
        Выполнить полный пайплайн рекомендаций
        
        Args:
            context: контекст пользователя и запроса
            limit: количество результатов
        
        Returns:
            Список рекомендованных кандидатов
        """
        logger.info(f"Starting pipeline execution for user={context.user_id}, limit={limit}")
        
        # 1. Fetch candidates from all sources (parallel)
        candidates = self._fetch_from_sources(context)
        logger.info(f"Fetched {len(candidates)} candidates from {len(self.sources)} sources")
        
        if not candidates:
            logger.warning("No candidates fetched from sources")
            return []
        
        # 2. Hydrate with additional data (parallel)
        candidates = self._hydrate_candidates(candidates, context)
        logger.info(f"Hydrated {len(candidates)} candidates")
        
        # 3. Apply filters (sequential - order matters)
        for filt in self.filters:
            before = len(candidates)
            candidates = self._safe_execute(
                lambda: filt.filter(candidates, context),
                candidates,
                f"Filter:{filt.name}"
            )
            logger.info(f"Filter {filt.name}: {before} → {len(candidates)}")
        
        if not candidates:
            logger.warning("All candidates filtered out")
            return []
        
        # 4. Score candidates (sequential - may depend on each other)
        for scorer in self.scorers:
            candidates = self._safe_execute(
                lambda: scorer.score(candidates, context),
                candidates,
                f"Scorer:{scorer.name}"
            )
        logger.info(f"Scored {len(candidates)} candidates")
        
        # 5. Select final results
        for selector in self.selectors:
            candidates = self._safe_execute(
                lambda: selector.select(candidates, context, limit),
                candidates,
                f"Selector:{selector.name}"
            )
        
        logger.info(f"Pipeline complete: returning {len(candidates)} recommendations")
        return candidates
    
    def _fetch_from_sources(self, context: PipelineContext) -> List[Candidate]:
        """Параллельный fetch из всех sources"""
        all_candidates = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(source.fetch, context): source 
                for source in self.sources
            }
            
            for future in as_completed(futures):
                source = futures[future]
                try:
                    candidates = future.result()
                    all_candidates.extend(candidates)
                except Exception as e:
                    logger.error(f"Source {source.name} failed: {e}")
                    if not self.fail_open:
                        raise
        
        return all_candidates
    
    def _hydrate_candidates(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        """Параллельная гидрация (где возможно)"""
        # В базовой версии - последовательно
        # TODO: добавить dependency graph для параллельной гидрации
        for hydrator in self.hydrators:
            candidates = self._safe_execute(
                lambda: hydrator.hydrate(candidates, context),
                candidates,
                f"Hydrator:{hydrator.name}"
            )
        return candidates
    
    def _safe_execute(self, fn, fallback, component_name: str):
        """Безопасное выполнение с fallback"""
        try:
            return fn()
        except Exception as e:
            logger.error(f"{component_name} failed: {e}")
            if self.fail_open:
                return fallback
            raise


# === Готовые реализации ===

class TopNSelector(Selector):
    """Простой селектор top-N по score"""
    
    @property
    def name(self) -> str:
        return "TopNSelector"
    
    def select(self, candidates: List[Candidate], context: PipelineContext, limit: int) -> List[Candidate]:
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
        return sorted_candidates[:limit]


class DiversitySelector(Selector):
    """
    Селектор с учётом разнообразия
    Не даёт одному источнику доминировать
    """
    
    def __init__(self, max_per_source: int = 3):
        self.max_per_source = max_per_source
    
    @property
    def name(self) -> str:
        return "DiversitySelector"
    
    def select(self, candidates: List[Candidate], context: PipelineContext, limit: int) -> List[Candidate]:
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
        
        selected = []
        source_counts: Dict[str, int] = {}
        
        for candidate in sorted_candidates:
            if len(selected) >= limit:
                break
            
            source = candidate.source
            current_count = source_counts.get(source, 0)
            
            if current_count < self.max_per_source:
                selected.append(candidate)
                source_counts[source] = current_count + 1
        
        return selected


class SeenFilter(Filter):
    """Фильтр уже просмотренного контента"""
    
    @property
    def name(self) -> str:
        return "SeenFilter"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        seen_ids = set(context.user_history)
        return [c for c in candidates if c.id not in seen_ids]


class MinScoreFilter(Filter):
    """Фильтр по минимальному score"""
    
    def __init__(self, min_score: float = 0.0):
        self.min_score = min_score
    
    @property
    def name(self) -> str:
        return f"MinScoreFilter(min={self.min_score})"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        return [c for c in candidates if c.score >= self.min_score]
