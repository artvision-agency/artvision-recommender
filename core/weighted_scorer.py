"""
Artvision Weighted Scorer
Адаптация X Algorithm scoring logic для SEO и клиентских проектов

Принцип: каждый элемент (кластер, задача, контент) получает score на основе
взвешенной суммы положительных и отрицательных сигналов.

Вдохновлено: https://github.com/xai-org/x-algorithm
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import math
from datetime import datetime, timedelta


class SignalType(Enum):
    """Типы сигналов по аналогии с X Algorithm"""
    # Положительные
    CLICK = "click"
    CONVERSION = "conversion"
    TIME_SPENT = "time_spent"
    SHARE = "share"
    SAVE = "save"
    RETURN_VISIT = "return_visit"
    
    # Отрицательные
    BOUNCE = "bounce"
    SKIP = "skip"
    HIDE = "hide"
    REPORT = "report"
    
    # Нейтральные/контекстные
    IMPRESSION = "impression"
    RECENCY = "recency"
    AUTHORITY = "authority"


@dataclass
class Signal:
    """Сигнал взаимодействия"""
    type: SignalType
    value: float  # probability или raw value
    weight: float = 1.0
    timestamp: Optional[datetime] = None


@dataclass
class ScoringConfig:
    """
    Конфигурация весов скоринга
    Полностью настраиваемая под разные use cases
    """
    # Положительные веса (как у X: like, repost, share имеют positive weights)
    positive_weights: Dict[SignalType, float] = field(default_factory=lambda: {
        SignalType.CLICK: 1.0,
        SignalType.CONVERSION: 5.0,
        SignalType.TIME_SPENT: 0.5,
        SignalType.SHARE: 3.0,
        SignalType.SAVE: 2.0,
        SignalType.RETURN_VISIT: 2.5,
    })
    
    # Отрицательные веса (как у X: block, mute, report have negative weights)
    negative_weights: Dict[SignalType, float] = field(default_factory=lambda: {
        SignalType.BOUNCE: -1.0,
        SignalType.SKIP: -0.5,
        SignalType.HIDE: -2.0,
        SignalType.REPORT: -5.0,
    })
    
    # Time decay factor (свежий контент важнее)
    time_decay_half_life_days: float = 7.0
    
    # Boosters
    authority_boost: float = 1.5
    recency_boost: float = 1.2


class WeightedScorer:
    """
    Взвешенный скорер по принципу X Algorithm
    
    Final score = Σ(positive_weights × P(action)) + Σ(negative_weights × P(action))
    
    Где P(action) — вероятность или нормализованное значение сигнала
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
    
    def calculate_score(
        self,
        signals: List[Signal],
        context: Optional[Dict] = None
    ) -> float:
        """
        Рассчитать итоговый score для элемента
        
        Args:
            signals: список сигналов
            context: дополнительный контекст (authority, recency и т.д.)
        
        Returns:
            Итоговый weighted score
        """
        score = 0.0
        
        for signal in signals:
            weight = self._get_weight(signal.type)
            value = signal.value * signal.weight
            
            # Time decay
            if signal.timestamp:
                value *= self._calculate_time_decay(signal.timestamp)
            
            score += weight * value
        
        # Apply context boosters
        if context:
            if context.get('is_authoritative'):
                score *= self.config.authority_boost
            if context.get('is_recent'):
                score *= self.config.recency_boost
        
        return score
    
    def _get_weight(self, signal_type: SignalType) -> float:
        """Получить вес для типа сигнала"""
        if signal_type in self.config.positive_weights:
            return self.config.positive_weights[signal_type]
        if signal_type in self.config.negative_weights:
            return self.config.negative_weights[signal_type]
        return 0.0
    
    def _calculate_time_decay(self, timestamp: datetime) -> float:
        """
        Exponential time decay
        Сигналы старее half_life теряют половину веса
        """
        age_days = (datetime.now() - timestamp).days
        half_life = self.config.time_decay_half_life_days
        return math.exp(-0.693 * age_days / half_life)
    
    def rank(
        self,
        items: List[Dict],
        get_signals: Callable[[Dict], List[Signal]],
        get_context: Optional[Callable[[Dict], Dict]] = None
    ) -> List[Dict]:
        """
        Отранжировать список элементов по score
        
        Args:
            items: список элементов для ранжирования
            get_signals: функция извлечения сигналов из элемента
            get_context: функция извлечения контекста
        
        Returns:
            Отсортированный список с добавленным полем '_score'
        """
        scored_items = []
        
        for item in items:
            signals = get_signals(item)
            context = get_context(item) if get_context else None
            score = self.calculate_score(signals, context)
            
            scored_item = {**item, '_score': score}
            scored_items.append(scored_item)
        
        # Sort descending by score
        scored_items.sort(key=lambda x: x['_score'], reverse=True)
        
        return scored_items


# === Preset configurations for different use cases ===

def get_seo_scorer_config() -> ScoringConfig:
    """Конфигурация для SEO-приоритизации кластеров"""
    return ScoringConfig(
        positive_weights={
            SignalType.CLICK: 1.0,       # CTR из выдачи
            SignalType.CONVERSION: 10.0,  # Конверсии (главный приоритет)
            SignalType.TIME_SPENT: 0.8,   # Время на странице
            SignalType.RETURN_VISIT: 3.0, # Возвраты = лояльность
            SignalType.AUTHORITY: 2.0,    # Авторитетность источника
        },
        negative_weights={
            SignalType.BOUNCE: -1.5,      # Отказы
            SignalType.SKIP: -0.3,        # Пропуск в SERP
        },
        time_decay_half_life_days=30.0,   # SEO = долгосрочная игра
    )


def get_content_scorer_config() -> ScoringConfig:
    """Конфигурация для контент-рекомендаций"""
    return ScoringConfig(
        positive_weights={
            SignalType.CLICK: 1.0,
            SignalType.TIME_SPENT: 2.0,   # Читают = ценно
            SignalType.SHARE: 5.0,        # Шерят = очень ценно
            SignalType.SAVE: 3.0,
        },
        negative_weights={
            SignalType.BOUNCE: -2.0,
            SignalType.SKIP: -0.5,
            SignalType.HIDE: -3.0,
        },
        time_decay_half_life_days=7.0,    # Контент быстрее устаревает
        recency_boost=1.5,
    )


def get_task_scorer_config() -> ScoringConfig:
    """Конфигурация для приоритизации задач"""
    return ScoringConfig(
        positive_weights={
            SignalType.CONVERSION: 5.0,   # Влияние на бизнес
            SignalType.AUTHORITY: 3.0,    # Важность клиента
            SignalType.CLICK: 0.5,        # Частота обращений
        },
        negative_weights={
            SignalType.SKIP: -2.0,        # Откладывание = деприоритизация
            SignalType.HIDE: -1.0,
        },
        time_decay_half_life_days=3.0,    # Задачи = срочность
        recency_boost=2.0,                # Свежие задачи важнее
    )
