"""
SEO Cluster Prioritization
Применение X Algorithm архитектуры для приоритизации SEO-кластеров

Use case: Имеем 100+ кластеров, нужно понять какие оптимизировать первыми
на основе потенциала трафика, конверсий и текущего состояния.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.weighted_scorer import WeightedScorer, Signal, SignalType, get_seo_scorer_config
from core.candidate_pipeline import (
    Candidate, PipelineContext, Source, Hydrator, Filter, Scorer, Selector,
    CandidatePipeline, TopNSelector, DiversitySelector
)


@dataclass
class SEOCluster:
    """SEO-кластер для оптимизации"""
    id: str
    main_keyword: str
    keywords: List[str]
    search_volume: int
    current_position: Optional[int] = None
    target_url: Optional[str] = None
    intent: str = "unknown"  # commercial, informational, mixed
    competition: str = "medium"  # low, medium, high
    
    # Метрики эффективности
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    bounce_rate: float = 0.0
    avg_time_on_page: float = 0.0
    
    # Временные метки
    last_optimized: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


# === Sources ===

class WebmasterSource(Source):
    """
    Источник: данные из Яндекс.Вебмастера
    Аналог Thunder (in-network content) у X
    """
    
    def __init__(self, clusters: List[SEOCluster]):
        self._clusters = clusters
    
    @property
    def name(self) -> str:
        return "WebmasterSource"
    
    def fetch(self, context: PipelineContext, limit: int = 100) -> List[Candidate]:
        candidates = []
        
        for cluster in self._clusters[:limit]:
            candidate = Candidate(
                id=cluster.id,
                data=cluster,
                source=self.name,
                metadata={
                    'has_position': cluster.current_position is not None,
                    'has_traffic': cluster.impressions > 0,
                }
            )
            candidates.append(candidate)
        
        return candidates


class WordstatSource(Source):
    """
    Источник: новые кластеры из Wordstat
    Аналог Phoenix (out-of-network discovery) у X
    """
    
    def __init__(self, clusters: List[SEOCluster]):
        self._clusters = clusters
    
    @property
    def name(self) -> str:
        return "WordstatSource"
    
    def fetch(self, context: PipelineContext, limit: int = 100) -> List[Candidate]:
        # Фильтруем только новые кластеры без позиций
        new_clusters = [c for c in self._clusters if c.current_position is None]
        
        candidates = []
        for cluster in new_clusters[:limit]:
            candidate = Candidate(
                id=cluster.id,
                data=cluster,
                source=self.name,
                metadata={'is_new_opportunity': True}
            )
            candidates.append(candidate)
        
        return candidates


# === Hydrators ===

class MetricsHydrator(Hydrator):
    """Обогащение метриками из аналитики"""
    
    def __init__(self, metrics_data: Optional[Dict[str, Dict]] = None):
        self._metrics = metrics_data or {}
    
    @property
    def name(self) -> str:
        return "MetricsHydrator"
    
    def hydrate(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        for candidate in candidates:
            cluster_id = candidate.id
            if cluster_id in self._metrics:
                metrics = self._metrics[cluster_id]
                candidate.metadata['ctr'] = metrics.get('ctr', 0)
                candidate.metadata['conversion_rate'] = metrics.get('conversion_rate', 0)
                candidate.metadata['revenue'] = metrics.get('revenue', 0)
        
        return candidates


class CompetitorHydrator(Hydrator):
    """Обогащение данными о конкурентах"""
    
    def __init__(self, competitor_data: Optional[Dict[str, Dict]] = None):
        self._competitor_data = competitor_data or {}
    
    @property
    def name(self) -> str:
        return "CompetitorHydrator"
    
    def hydrate(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        for candidate in candidates:
            keyword = candidate.data.main_keyword
            if keyword in self._competitor_data:
                comp_data = self._competitor_data[keyword]
                candidate.metadata['competitor_count'] = comp_data.get('count', 0)
                candidate.metadata['top3_authority'] = comp_data.get('top3_authority', 0)
                candidate.metadata['content_gap'] = comp_data.get('content_gap', False)
        
        return candidates


# === Filters ===

class IntentFilter(Filter):
    """Фильтр по интенту (коммерческий vs информационный)"""
    
    def __init__(self, allowed_intents: List[str] = None):
        self.allowed_intents = allowed_intents or ['commercial', 'mixed']
    
    @property
    def name(self) -> str:
        return "IntentFilter"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        # Если в параметрах запроса указан фильтр интента — используем его
        filter_intent = context.request_params.get('intent_filter')
        if filter_intent:
            allowed = [filter_intent]
        else:
            allowed = self.allowed_intents
        
        return [c for c in candidates if c.data.intent in allowed]


class VolumeFilter(Filter):
    """Фильтр по минимальному объёму поиска"""
    
    def __init__(self, min_volume: int = 100):
        self.min_volume = min_volume
    
    @property
    def name(self) -> str:
        return f"VolumeFilter(min={self.min_volume})"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        return [c for c in candidates if c.data.search_volume >= self.min_volume]


class PositionOpportunityFilter(Filter):
    """
    Фильтр возможностей: позиции 4-20 (реально улучшить)
    или новые кластеры без позиций
    """
    
    @property
    def name(self) -> str:
        return "PositionOpportunityFilter"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        results = []
        for c in candidates:
            pos = c.data.current_position
            # Нет позиции (новая возможность) или позиция в зоне роста
            if pos is None or (4 <= pos <= 50):
                results.append(c)
        return results


# === Scorers ===

class SEOWeightedScorer(Scorer):
    """
    Главный скорер по принципу X Algorithm
    Weighted sum всех сигналов
    """
    
    def __init__(self):
        self._scorer = WeightedScorer(config=get_seo_scorer_config())
    
    @property
    def name(self) -> str:
        return "SEOWeightedScorer"
    
    def score(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        for candidate in candidates:
            signals = self._extract_signals(candidate)
            ctx = self._build_context(candidate)
            
            candidate.score = self._scorer.calculate_score(signals, ctx)
        
        return candidates
    
    def _extract_signals(self, candidate: Candidate) -> List[Signal]:
        """Извлечь сигналы из кластера"""
        cluster = candidate.data
        signals = []
        
        # Положительные сигналы
        if cluster.clicks > 0:
            # Нормализуем клики
            click_score = min(cluster.clicks / 1000, 1.0)  # max 1.0
            signals.append(Signal(SignalType.CLICK, click_score))
        
        if cluster.conversions > 0:
            # Конверсии — главный сигнал
            conv_score = min(cluster.conversions / 100, 1.0)
            signals.append(Signal(SignalType.CONVERSION, conv_score))
        
        if cluster.avg_time_on_page > 0:
            # Время на странице (нормализуем к 5 минутам = идеал)
            time_score = min(cluster.avg_time_on_page / 300, 1.0)
            signals.append(Signal(SignalType.TIME_SPENT, time_score))
        
        # Потенциал трафика
        if cluster.search_volume > 0:
            # Нормализуем volume (10000 = очень высокий)
            volume_score = min(cluster.search_volume / 10000, 1.0)
            signals.append(Signal(SignalType.AUTHORITY, volume_score, weight=0.5))
        
        # Отрицательные сигналы
        if cluster.bounce_rate > 0:
            # Высокий bounce = плохо
            bounce_score = cluster.bounce_rate  # уже 0-1
            signals.append(Signal(SignalType.BOUNCE, bounce_score))
        
        # Позиция как сигнал (близко к топу = меньше работы)
        if cluster.current_position:
            pos = cluster.current_position
            if pos <= 10:
                # Уже в топ-10 — меньший приоритет на рост
                signals.append(Signal(SignalType.SKIP, 0.3))
            elif pos <= 20:
                # Зона быстрого роста — бонус
                signals.append(Signal(SignalType.RETURN_VISIT, 0.5))
        
        return signals
    
    def _build_context(self, candidate: Candidate) -> Dict:
        """Построить контекст для скорера"""
        cluster = candidate.data
        return {
            'is_authoritative': cluster.competition == 'low',
            'is_recent': candidate.metadata.get('is_new_opportunity', False),
        }


class ROIScorer(Scorer):
    """
    Дополнительный скорер: ROI-потенциал
    Добавляет бонус за revenue potential
    """
    
    def __init__(self, revenue_weight: float = 0.3):
        self.revenue_weight = revenue_weight
    
    @property
    def name(self) -> str:
        return "ROIScorer"
    
    def score(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        for candidate in candidates:
            revenue = candidate.metadata.get('revenue', 0)
            if revenue > 0:
                # Добавляем revenue bonus к существующему score
                revenue_bonus = min(revenue / 100000, 1.0) * self.revenue_weight
                candidate.score += revenue_bonus
        
        return candidates


# === Factory ===

def create_seo_prioritization_pipeline(
    clusters: List[SEOCluster],
    metrics_data: Optional[Dict] = None,
    competitor_data: Optional[Dict] = None,
) -> CandidatePipeline:
    """
    Фабрика для создания SEO пайплайна приоритизации
    
    Args:
        clusters: список кластеров для приоритизации
        metrics_data: данные метрик из аналитики
        competitor_data: данные о конкурентах
    
    Returns:
        Готовый CandidatePipeline
    """
    # Разделяем кластеры на существующие и новые
    existing = [c for c in clusters if c.current_position is not None]
    new = [c for c in clusters if c.current_position is None]
    
    return CandidatePipeline(
        sources=[
            WebmasterSource(existing),
            WordstatSource(new),
        ],
        hydrators=[
            MetricsHydrator(metrics_data),
            CompetitorHydrator(competitor_data),
        ],
        filters=[
            VolumeFilter(min_volume=50),
            PositionOpportunityFilter(),
        ],
        scorers=[
            SEOWeightedScorer(),
            ROIScorer(),
        ],
        selectors=[
            DiversitySelector(max_per_source=10),  # Баланс между existing и new
            TopNSelector(),
        ],
    )
