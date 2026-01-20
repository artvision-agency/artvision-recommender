# Artvision Recommender Engine

**Рекомендательный движок на базе архитектуры X Algorithm**

Адаптация открытого алгоритма X (github.com/xai-org/x-algorithm) для задач SEO-агентства.

## 🏗 Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANDIDATE PIPELINE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌───────────┐    ┌─────────┐    ┌──────────┐  │
│  │ SOURCES  │───▶│ HYDRATORS │───▶│ FILTERS │───▶│ SCORERS  │  │
│  └──────────┘    └───────────┘    └─────────┘    └──────────┘  │
│       │                                               │         │
│       │              Parallel execution               │         │
│       ▼                                               ▼         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    WEIGHTED SCORER                        │  │
│  │  Score = Σ(positive_weights × P) + Σ(negative_weights × P)│  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│                       ┌───────────┐                             │
│                       │ SELECTORS │──▶ Top-N Results            │
│                       └───────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Модули

### Core (`/core`)

**weighted_scorer.py** — Взвешенный скорер
- Positive/negative weights по типам сигналов
- Time decay (экспоненциальное затухание)
- Context boosters (authority, recency)

**candidate_pipeline.py** — Фреймворк пайплайна
- Sources → Hydrators → Filters → Scorers → Selectors
- Параллельное выполнение sources и hydrators
- Graceful error handling (fail_open mode)

### SEO (`/seo`)

**cluster_prioritizer.py** — Приоритизация SEO-кластеров
- Какие кластеры оптимизировать первыми
- Учёт: volume, position, conversions, bounce rate
- Баланс между existing и new opportunities

### Portal (`/portal`)

**feed_prioritizer.py** — Умная лента клиентского портала
- Персонализация по истории engagement
- Приоритизация action_required уведомлений
- Балансировка типов уведомлений

## 🚀 Быстрый старт

```python
from seo.cluster_prioritizer import (
    SEOCluster, 
    create_seo_prioritization_pipeline,
    PipelineContext
)

# Создаём кластеры
clusters = [
    SEOCluster(
        id="1",
        main_keyword="имплантация зубов",
        keywords=["импланты", "имплант зуба"],
        search_volume=8500,
        current_position=12,
        intent="commercial",
    ),
    # ... больше кластеров
]

# Создаём пайплайн
pipeline = create_seo_prioritization_pipeline(clusters)

# Выполняем
context = PipelineContext(user_id="team")
results = pipeline.execute(context, limit=10)

# Получаем top-10 приоритетных кластеров
for r in results:
    print(f"{r.score:.2f} | {r.data.main_keyword}")
```

## 🔧 Кастомизация

### Свои веса для скорера

```python
from core.weighted_scorer import ScoringConfig, SignalType

my_config = ScoringConfig(
    positive_weights={
        SignalType.CONVERSION: 10.0,  # Конверсии важнее всего
        SignalType.CLICK: 1.0,
    },
    negative_weights={
        SignalType.BOUNCE: -2.0,
    },
    time_decay_half_life_days=14.0,  # Медленное затухание
)
```

### Свой Source

```python
from core.candidate_pipeline import Source, Candidate

class MySource(Source):
    @property
    def name(self) -> str:
        return "MySource"
    
    def fetch(self, context, limit=100):
        # Ваша логика получения кандидатов
        return [Candidate(id="1", data=my_data, source=self.name)]
```

### Свой Filter

```python
from core.candidate_pipeline import Filter

class MyFilter(Filter):
    @property
    def name(self) -> str:
        return "MyFilter"
    
    def filter(self, candidates, context):
        return [c for c in candidates if self._should_keep(c)]
```

## 📊 Сигналы (по аналогии с X)

| Сигнал | Тип | Описание |
|--------|-----|----------|
| CLICK | + | Клик/переход |
| CONVERSION | + | Конверсия/целевое действие |
| TIME_SPENT | + | Время взаимодействия |
| SHARE | + | Поделились |
| SAVE | + | Сохранили |
| RETURN_VISIT | + | Вернулись |
| BOUNCE | - | Отказ |
| SKIP | - | Пропустили |
| HIDE | - | Скрыли |
| REPORT | - | Пожаловались |

## 🎯 Use Cases для Artvision

1. **SEO Cluster Prioritization** — какие кластеры оптимизировать первыми
2. **Client Portal Feed** — персонализированная лента уведомлений
3. **Content Recommendations** — что читать дальше на сайте клиента
4. **Task Prioritization** — приоритизация задач в Asana
5. **Lead Scoring** — оценка лидов по потенциалу

## 📁 Структура проекта

```
artvision-recommender/
├── core/
│   ├── __init__.py
│   ├── weighted_scorer.py    # Weighted scoring engine
│   └── candidate_pipeline.py # Pipeline framework
├── seo/
│   ├── __init__.py
│   └── cluster_prioritizer.py
├── portal/
│   ├── __init__.py
│   └── feed_prioritizer.py
├── demo_seo_prioritizer.py   # Demo script
└── README.md
```

## 🔗 Источники

- [X Algorithm (xai-org)](https://github.com/xai-org/x-algorithm) — оригинальный алгоритм
- [Phoenix Recommender](https://github.com/xai-org/x-algorithm/blob/main/phoenix/README.md) — ML-ранжирование
- [Candidate Pipeline](https://github.com/xai-org/x-algorithm/tree/main/candidate-pipeline) — фреймворк

## 📝 Лицензия

Apache 2.0 (как у оригинального X Algorithm)

---

*Artvision Agency © 2025*
