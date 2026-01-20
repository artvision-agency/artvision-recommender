"""
Client Portal Feed Prioritizer
Умная лента для avportal_bot — какие метрики/уведомления показывать первыми

Аналогия с X Algorithm:
- Клиенты = пользователи
- Метрики/отчёты = посты
- Engagement = просмотры, клики, вопросы по отчётам
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

from core.weighted_scorer import WeightedScorer, Signal, SignalType, ScoringConfig
from core.candidate_pipeline import (
    Candidate, PipelineContext, Source, Hydrator, Filter, Scorer, Selector,
    CandidatePipeline, TopNSelector, SeenFilter
)


class NotificationType(Enum):
    """Типы уведомлений в портале"""
    POSITION_CHANGE = "position_change"
    TRAFFIC_SPIKE = "traffic_spike"
    TRAFFIC_DROP = "traffic_drop"
    NEW_KEYWORDS = "new_keywords"
    REPORT_READY = "report_ready"
    ACTION_REQUIRED = "action_required"
    MILESTONE = "milestone"


@dataclass
class PortalNotification:
    """Уведомление для клиента"""
    id: str
    type: NotificationType
    title: str
    description: str
    priority: str = "normal"  # low, normal, high, critical
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    # Engagement metrics
    viewed: bool = False
    clicked: bool = False
    dismissed: bool = False
    asked_question: bool = False


@dataclass
class ClientProfile:
    """Профиль клиента для персонализации"""
    client_id: str
    company_name: str
    industry: str
    engagement_level: str = "medium"  # low, medium, high
    preferences: Dict[str, Any] = field(default_factory=dict)
    notification_history: List[str] = field(default_factory=list)


# === Scoring Config для портала ===

def get_portal_scorer_config() -> ScoringConfig:
    """Конфигурация скорера для клиентского портала"""
    return ScoringConfig(
        positive_weights={
            SignalType.CLICK: 2.0,        # Клиент кликал на похожие
            SignalType.CONVERSION: 5.0,   # Привело к действию
            SignalType.TIME_SPENT: 1.0,   # Читал внимательно
            SignalType.SHARE: 3.0,        # Переслал коллегам
            SignalType.AUTHORITY: 2.0,    # Важность для бизнеса
        },
        negative_weights={
            SignalType.SKIP: -1.0,        # Пропускал похожие
            SignalType.HIDE: -3.0,        # Скрывал похожие
            SignalType.BOUNCE: -0.5,      # Быстро закрыл
        },
        time_decay_half_life_days=1.0,    # Свежесть критична
        recency_boost=2.0,
    )


# === Sources ===

class PositionChangesSource(Source):
    """Источник: изменения позиций из мониторинга"""
    
    def __init__(self, notifications: List[PortalNotification]):
        self._notifications = [
            n for n in notifications 
            if n.type == NotificationType.POSITION_CHANGE
        ]
    
    @property
    def name(self) -> str:
        return "PositionChangesSource"
    
    def fetch(self, context: PipelineContext, limit: int = 50) -> List[Candidate]:
        return [
            Candidate(id=n.id, data=n, source=self.name)
            for n in self._notifications[:limit]
        ]


class TrafficAlertsSource(Source):
    """Источник: алерты по трафику"""
    
    def __init__(self, notifications: List[PortalNotification]):
        self._notifications = [
            n for n in notifications 
            if n.type in [NotificationType.TRAFFIC_SPIKE, NotificationType.TRAFFIC_DROP]
        ]
    
    @property
    def name(self) -> str:
        return "TrafficAlertsSource"
    
    def fetch(self, context: PipelineContext, limit: int = 50) -> List[Candidate]:
        return [
            Candidate(id=n.id, data=n, source=self.name)
            for n in self._notifications[:limit]
        ]


class ActionRequiredSource(Source):
    """Источник: требуется действие клиента"""
    
    def __init__(self, notifications: List[PortalNotification]):
        self._notifications = [
            n for n in notifications 
            if n.type == NotificationType.ACTION_REQUIRED
        ]
    
    @property
    def name(self) -> str:
        return "ActionRequiredSource"
    
    def fetch(self, context: PipelineContext, limit: int = 50) -> List[Candidate]:
        return [
            Candidate(
                id=n.id, 
                data=n, 
                source=self.name,
                metadata={'requires_action': True}
            )
            for n in self._notifications[:limit]
        ]


class ReportsSource(Source):
    """Источник: готовые отчёты"""
    
    def __init__(self, notifications: List[PortalNotification]):
        self._notifications = [
            n for n in notifications 
            if n.type == NotificationType.REPORT_READY
        ]
    
    @property
    def name(self) -> str:
        return "ReportsSource"
    
    def fetch(self, context: PipelineContext, limit: int = 50) -> List[Candidate]:
        return [
            Candidate(id=n.id, data=n, source=self.name)
            for n in self._notifications[:limit]
        ]


# === Hydrators ===

class ClientPreferencesHydrator(Hydrator):
    """Обогащение предпочтениями клиента"""
    
    def __init__(self, client_profiles: Dict[str, ClientProfile]):
        self._profiles = client_profiles
    
    @property
    def name(self) -> str:
        return "ClientPreferencesHydrator"
    
    def hydrate(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        client_id = context.user_id
        profile = self._profiles.get(client_id)
        
        if not profile:
            return candidates
        
        for candidate in candidates:
            notification = candidate.data
            
            # Проверяем предпочтения клиента
            prefs = profile.preferences
            
            # Например: клиент хочет видеть только critical уведомления
            if prefs.get('only_critical') and notification.priority != 'critical':
                candidate.metadata['deprioritize'] = True
            
            # Или: клиент любит отчёты по трафику
            if prefs.get('loves_traffic_reports'):
                if notification.type in [NotificationType.TRAFFIC_SPIKE, NotificationType.TRAFFIC_DROP]:
                    candidate.metadata['preference_boost'] = True
            
            # Engagement level влияет на количество уведомлений
            candidate.metadata['client_engagement'] = profile.engagement_level
        
        return candidates


class EngagementHistoryHydrator(Hydrator):
    """Обогащение историей взаимодействия"""
    
    def __init__(self, engagement_data: Dict[str, Dict]):
        self._engagement = engagement_data
    
    @property
    def name(self) -> str:
        return "EngagementHistoryHydrator"
    
    def hydrate(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        client_id = context.user_id
        history = self._engagement.get(client_id, {})
        
        for candidate in candidates:
            notification = candidate.data
            notif_type = notification.type.value
            
            # Статистика по типу уведомлений
            type_stats = history.get(notif_type, {})
            candidate.metadata['type_click_rate'] = type_stats.get('click_rate', 0.5)
            candidate.metadata['type_dismiss_rate'] = type_stats.get('dismiss_rate', 0.1)
        
        return candidates


# === Filters ===

class AlreadySeenFilter(Filter):
    """Фильтр уже просмотренных уведомлений"""
    
    @property
    def name(self) -> str:
        return "AlreadySeenFilter"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        return [c for c in candidates if not c.data.viewed]


class DismissedTypeFilter(Filter):
    """Фильтр типов, которые клиент часто dismiss-ит"""
    
    def __init__(self, dismiss_threshold: float = 0.7):
        self.dismiss_threshold = dismiss_threshold
    
    @property
    def name(self) -> str:
        return "DismissedTypeFilter"
    
    def filter(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        results = []
        for c in candidates:
            dismiss_rate = c.metadata.get('type_dismiss_rate', 0)
            # Не фильтруем critical и action_required даже если часто dismiss-ят
            if c.data.priority == 'critical' or c.data.type == NotificationType.ACTION_REQUIRED:
                results.append(c)
            elif dismiss_rate < self.dismiss_threshold:
                results.append(c)
        return results


# === Scorers ===

class PortalWeightedScorer(Scorer):
    """Главный скорер для портала"""
    
    def __init__(self):
        self._scorer = WeightedScorer(config=get_portal_scorer_config())
    
    @property
    def name(self) -> str:
        return "PortalWeightedScorer"
    
    def score(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        for candidate in candidates:
            signals = self._extract_signals(candidate)
            ctx = self._build_context(candidate)
            candidate.score = self._scorer.calculate_score(signals, ctx)
        return candidates
    
    def _extract_signals(self, candidate: Candidate) -> List[Signal]:
        notification = candidate.data
        signals = []
        
        # Базовый приоритет
        priority_scores = {'critical': 1.0, 'high': 0.7, 'normal': 0.4, 'low': 0.1}
        signals.append(Signal(
            SignalType.AUTHORITY, 
            priority_scores.get(notification.priority, 0.4)
        ))
        
        # История кликов по типу
        click_rate = candidate.metadata.get('type_click_rate', 0.5)
        signals.append(Signal(SignalType.CLICK, click_rate))
        
        # Dismiss rate как негативный сигнал
        dismiss_rate = candidate.metadata.get('type_dismiss_rate', 0)
        if dismiss_rate > 0:
            signals.append(Signal(SignalType.SKIP, dismiss_rate))
        
        # Бонус за preference match
        if candidate.metadata.get('preference_boost'):
            signals.append(Signal(SignalType.CONVERSION, 0.5))
        
        # Депиоритизация
        if candidate.metadata.get('deprioritize'):
            signals.append(Signal(SignalType.HIDE, 0.5))
        
        # Свежесть
        age_hours = (datetime.now() - notification.created_at).total_seconds() / 3600
        if age_hours < 1:
            signals.append(Signal(SignalType.RETURN_VISIT, 0.3))  # Очень свежее
        
        return signals
    
    def _build_context(self, candidate: Candidate) -> Dict:
        notification = candidate.data
        return {
            'is_authoritative': notification.priority in ['critical', 'high'],
            'is_recent': (datetime.now() - notification.created_at).total_seconds() < 3600,
        }


class ActionRequiredBooster(Scorer):
    """Бустер для уведомлений, требующих действия"""
    
    def __init__(self, boost_factor: float = 2.0):
        self.boost_factor = boost_factor
    
    @property
    def name(self) -> str:
        return "ActionRequiredBooster"
    
    def score(self, candidates: List[Candidate], context: PipelineContext) -> List[Candidate]:
        for candidate in candidates:
            if candidate.metadata.get('requires_action'):
                candidate.score *= self.boost_factor
        return candidates


# === Selectors ===

class BalancedSelector(Selector):
    """
    Балансировка между типами уведомлений
    Не даём одному типу заполнить всю ленту
    """
    
    def __init__(self, max_per_type: int = 3):
        self.max_per_type = max_per_type
    
    @property
    def name(self) -> str:
        return "BalancedSelector"
    
    def select(self, candidates: List[Candidate], context: PipelineContext, limit: int) -> List[Candidate]:
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
        
        selected = []
        type_counts: Dict[NotificationType, int] = {}
        
        for candidate in sorted_candidates:
            if len(selected) >= limit:
                break
            
            notif_type = candidate.data.type
            current_count = type_counts.get(notif_type, 0)
            
            # Action required всегда пропускаем
            if candidate.data.type == NotificationType.ACTION_REQUIRED:
                selected.append(candidate)
                type_counts[notif_type] = current_count + 1
            elif current_count < self.max_per_type:
                selected.append(candidate)
                type_counts[notif_type] = current_count + 1
        
        return selected


# === Factory ===

def create_portal_feed_pipeline(
    notifications: List[PortalNotification],
    client_profiles: Dict[str, ClientProfile],
    engagement_data: Optional[Dict] = None,
) -> CandidatePipeline:
    """
    Создать пайплайн умной ленты для клиентского портала
    """
    return CandidatePipeline(
        sources=[
            ActionRequiredSource(notifications),  # Приоритет
            TrafficAlertsSource(notifications),
            PositionChangesSource(notifications),
            ReportsSource(notifications),
        ],
        hydrators=[
            ClientPreferencesHydrator(client_profiles),
            EngagementHistoryHydrator(engagement_data or {}),
        ],
        filters=[
            AlreadySeenFilter(),
            DismissedTypeFilter(dismiss_threshold=0.8),
        ],
        scorers=[
            PortalWeightedScorer(),
            ActionRequiredBooster(boost_factor=1.5),
        ],
        selectors=[
            BalancedSelector(max_per_type=3),
            TopNSelector(),
        ],
    )


# === Demo ===

def demo():
    """Демонстрация работы портального фида"""
    
    # Создаём тестовые уведомления
    now = datetime.now()
    notifications = [
        PortalNotification(
            id="n1",
            type=NotificationType.POSITION_CHANGE,
            title="Рост позиций: +5 мест",
            description="Кластер 'имплантация зубов' вырос с #15 на #10",
            priority="high",
            created_at=now - timedelta(hours=2),
        ),
        PortalNotification(
            id="n2",
            type=NotificationType.TRAFFIC_SPIKE,
            title="🚀 Трафик +45%",
            description="Органический трафик вырос на 45% за неделю",
            priority="high",
            created_at=now - timedelta(hours=1),
        ),
        PortalNotification(
            id="n3",
            type=NotificationType.ACTION_REQUIRED,
            title="⚠️ Требуется согласование",
            description="Новый контент-план на январь готов к утверждению",
            priority="critical",
            created_at=now - timedelta(minutes=30),
        ),
        PortalNotification(
            id="n4",
            type=NotificationType.REPORT_READY,
            title="📊 Отчёт за декабрь",
            description="Ежемесячный SEO-отчёт готов",
            priority="normal",
            created_at=now - timedelta(hours=5),
        ),
        PortalNotification(
            id="n5",
            type=NotificationType.TRAFFIC_DROP,
            title="⬇️ Падение трафика -12%",
            description="Обнаружено снижение трафика на странице услуг",
            priority="high",
            created_at=now - timedelta(hours=3),
        ),
    ]
    
    # Профиль клиента
    profiles = {
        "client_dental": ClientProfile(
            client_id="client_dental",
            company_name="Стоматология Улыбка",
            industry="dental",
            engagement_level="high",
            preferences={'loves_traffic_reports': True},
        )
    }
    
    # История engagement
    engagement = {
        "client_dental": {
            "position_change": {"click_rate": 0.8, "dismiss_rate": 0.1},
            "traffic_spike": {"click_rate": 0.9, "dismiss_rate": 0.05},
            "report_ready": {"click_rate": 0.6, "dismiss_rate": 0.2},
        }
    }
    
    # Создаём пайплайн
    pipeline = create_portal_feed_pipeline(
        notifications=notifications,
        client_profiles=profiles,
        engagement_data=engagement,
    )
    
    # Контекст
    context = PipelineContext(user_id="client_dental")
    
    # Выполняем
    results = pipeline.execute(context, limit=5)
    
    print("\n" + "=" * 50)
    print("📱 УМНАЯ ЛЕНТА КЛИЕНТА")
    print("=" * 50 + "\n")
    
    for i, c in enumerate(results, 1):
        n = c.data
        print(f"{i}. [{c.score:.2f}] {n.title}")
        print(f"   {n.description}")
        print(f"   Приоритет: {n.priority} | Тип: {n.type.value}")
        print()
    
    return results


if __name__ == "__main__":
    demo()
