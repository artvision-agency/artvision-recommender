#!/usr/bin/env python3
"""
Demo: SEO Cluster Prioritization
Демонстрация работы рекомендательного движка на реальных данных

Запуск:
    python demo_seo_prioritizer.py
"""

import sys
sys.path.insert(0, '/home/claude/artvision-recommender')

from datetime import datetime, timedelta
from typing import List
import json

from seo.cluster_prioritizer import (
    SEOCluster, 
    create_seo_prioritization_pipeline,
    PipelineContext
)


def create_sample_clusters() -> List[SEOCluster]:
    """Создаём тестовые кластеры (типичные для dental/legal ниш)"""
    
    clusters = [
        # === Высокий приоритет: коммерческие с хорошим потенциалом ===
        SEOCluster(
            id="cluster_001",
            main_keyword="имплантация зубов цена",
            keywords=["имплантация зубов стоимость", "сколько стоит имплант зуба", "цены на импланты"],
            search_volume=8500,
            current_position=12,
            intent="commercial",
            competition="high",
            impressions=15000,
            clicks=450,
            conversions=23,
            bounce_rate=0.35,
            avg_time_on_page=180,
        ),
        SEOCluster(
            id="cluster_002",
            main_keyword="виниры на зубы",
            keywords=["виниры цена", "керамические виниры", "виниры спб"],
            search_volume=6200,
            current_position=8,
            intent="commercial",
            competition="medium",
            impressions=22000,
            clicks=1200,
            conversions=45,
            bounce_rate=0.28,
            avg_time_on_page=240,
        ),
        
        # === Средний приоритет: информационные с потенциалом конверсии ===
        SEOCluster(
            id="cluster_003",
            main_keyword="больно ли ставить импланты",
            keywords=["имплантация зубов больно или нет", "больно удалять имплант"],
            search_volume=3200,
            current_position=15,
            intent="informational",
            competition="low",
            impressions=8000,
            clicks=600,
            conversions=5,
            bounce_rate=0.42,
            avg_time_on_page=320,
        ),
        SEOCluster(
            id="cluster_004",
            main_keyword="сколько служат импланты",
            keywords=["срок службы зубных имплантов", "как долго стоят импланты"],
            search_volume=2100,
            current_position=22,
            intent="informational",
            competition="low",
            impressions=4500,
            clicks=280,
            conversions=2,
            bounce_rate=0.38,
            avg_time_on_page=280,
        ),
        
        # === Низкий приоритет: уже в топе ===
        SEOCluster(
            id="cluster_005",
            main_keyword="стоматология спб",
            keywords=["стоматологическая клиника спб", "стоматология петербург"],
            search_volume=12000,
            current_position=3,  # Уже в топе!
            intent="commercial",
            competition="high",
            impressions=50000,
            clicks=8000,
            conversions=120,
            bounce_rate=0.25,
            avg_time_on_page=150,
        ),
        
        # === Новые возможности (без позиций) ===
        SEOCluster(
            id="cluster_006",
            main_keyword="all on 4 имплантация",
            keywords=["имплантация all on 4 цена", "all on 4 спб", "все на четырех имплантах"],
            search_volume=4500,
            current_position=None,  # Новый кластер!
            intent="commercial",
            competition="medium",
            impressions=0,
            clicks=0,
            conversions=0,
        ),
        SEOCluster(
            id="cluster_007",
            main_keyword="имплантация под ключ",
            keywords=["имплант зуба под ключ цена", "установка импланта под ключ"],
            search_volume=3800,
            current_position=None,
            intent="commercial",
            competition="medium",
            impressions=0,
            clicks=0,
            conversions=0,
        ),
        
        # === Legal ниша ===
        SEOCluster(
            id="cluster_008",
            main_keyword="юрист по недвижимости",
            keywords=["юрист по сделкам с недвижимостью", "адвокат по недвижимости спб"],
            search_volume=2900,
            current_position=18,
            intent="commercial",
            competition="medium",
            impressions=6000,
            clicks=320,
            conversions=15,
            bounce_rate=0.32,
            avg_time_on_page=200,
        ),
        SEOCluster(
            id="cluster_009",
            main_keyword="банкротство физических лиц",
            keywords=["банкротство физ лиц цена", "банкротство физлица спб"],
            search_volume=7500,
            current_position=25,
            intent="commercial",
            competition="high",
            impressions=12000,
            clicks=450,
            conversions=18,
            bounce_rate=0.40,
            avg_time_on_page=260,
        ),
        
        # === Низкочастотка ===
        SEOCluster(
            id="cluster_010",
            main_keyword="реставрация зубов фотополимером",
            keywords=["фотополимерная реставрация", "реставрация зубов композитом"],
            search_volume=45,  # Очень низкая частотность!
            current_position=5,
            intent="commercial",
            competition="low",
            impressions=200,
            clicks=15,
            conversions=1,
        ),
    ]
    
    return clusters


def create_sample_metrics() -> dict:
    """Дополнительные метрики из аналитики"""
    return {
        "cluster_001": {"ctr": 0.03, "conversion_rate": 0.051, "revenue": 230000},
        "cluster_002": {"ctr": 0.055, "conversion_rate": 0.0375, "revenue": 450000},
        "cluster_005": {"ctr": 0.16, "conversion_rate": 0.015, "revenue": 1200000},
        "cluster_008": {"ctr": 0.053, "conversion_rate": 0.047, "revenue": 150000},
        "cluster_009": {"ctr": 0.0375, "conversion_rate": 0.04, "revenue": 180000},
    }


def main():
    print("=" * 60)
    print("🚀 Artvision SEO Cluster Prioritizer")
    print("   На базе архитектуры X Algorithm")
    print("=" * 60)
    print()
    
    # Создаём тестовые данные
    clusters = create_sample_clusters()
    metrics = create_sample_metrics()
    
    print(f"📊 Загружено кластеров: {len(clusters)}")
    print(f"   - С позициями: {sum(1 for c in clusters if c.current_position)}")
    print(f"   - Новые возможности: {sum(1 for c in clusters if not c.current_position)}")
    print()
    
    # Создаём пайплайн
    pipeline = create_seo_prioritization_pipeline(
        clusters=clusters,
        metrics_data=metrics,
    )
    
    # Контекст запроса
    context = PipelineContext(
        user_id="artvision_team",
        request_params={
            'focus': 'commercial',  # Фокус на коммерческих кластерах
        }
    )
    
    # Выполняем приоритизацию
    print("⚙️  Запуск пайплайна...")
    print("-" * 60)
    
    results = pipeline.execute(context, limit=7)
    
    print()
    print("=" * 60)
    print("📈 РЕЗУЛЬТАТ ПРИОРИТИЗАЦИИ")
    print("=" * 60)
    print()
    
    for i, candidate in enumerate(results, 1):
        cluster = candidate.data
        score = candidate.score
        source = candidate.source
        
        # Определяем статус
        if cluster.current_position is None:
            pos_str = "🆕 NEW"
        elif cluster.current_position <= 3:
            pos_str = f"🏆 #{cluster.current_position}"
        elif cluster.current_position <= 10:
            pos_str = f"✅ #{cluster.current_position}"
        else:
            pos_str = f"📍 #{cluster.current_position}"
        
        # Форматируем intent
        intent_emoji = "💰" if cluster.intent == "commercial" else "📖"
        
        print(f"{i}. [{score:.2f}] {cluster.main_keyword}")
        print(f"   {pos_str} | {intent_emoji} {cluster.intent} | 🔍 {cluster.search_volume:,}/мес")
        print(f"   Источник: {source}")
        
        if cluster.conversions > 0:
            print(f"   💵 Конверсии: {cluster.conversions} | Bounce: {cluster.bounce_rate:.0%}")
        
        if candidate.id in metrics:
            rev = metrics[candidate.id].get('revenue', 0)
            if rev:
                print(f"   💰 Revenue: {rev:,.0f} ₽")
        
        print()
    
    print("=" * 60)
    print("📋 РЕКОМЕНДАЦИИ ПО ПРИОРИТЕТАМ")
    print("=" * 60)
    print()
    
    # Анализ результатов
    top3 = results[:3]
    print("🎯 TOP-3 для немедленной оптимизации:")
    for c in top3:
        print(f"   • {c.data.main_keyword}")
    
    print()
    
    new_opportunities = [r for r in results if r.data.current_position is None]
    if new_opportunities:
        print("🆕 Новые возможности для контента:")
        for c in new_opportunities:
            print(f"   • {c.data.main_keyword} ({c.data.search_volume:,}/мес)")
    
    print()
    print("✅ Приоритизация завершена!")
    
    # Возвращаем для дальнейшего использования
    return results


if __name__ == "__main__":
    main()
