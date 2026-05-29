# Рекомендации по улучшению системы (на основе исследований 2026)

**Дата:** 2026-05-27  
**Источники:** Pin.com AI Guide, arXiv 2603.26710, Gem, DigitalApplied, AskPython

---

## 🚨 КРИТИЧНО: Compliance & Legal (EU AI Act, EEOC)

### Проблема:
- EU AI Act вступил в силу **август 2026**
- Обязательны **bias audits** (проверка дискриминации по расе, полу, возрасту)
- Обязателен **human-in-the-loop** для всех reject решений
- Обязателен **audit trail** - логирование ВСЕХ AI решений

### Что добавить:

#### 1. **Audit Logging (КРИТИЧНО)**
```python
# app/models.py - новая таблица
class AIDecisionLog(Base):
    """Логирование всех AI решений для compliance."""
    id = Column(UUID, primary_key=True)
    screening_id = Column(UUID, ForeignKey("screenings.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    decision_type = Column(String)  # "score", "reject", "forward"
    ai_score = Column(Integer)
    ai_reasoning = Column(Text)  # JSON с объяснением
    human_override = Column(Boolean, default=False)
    human_reviewer_id = Column(UUID, nullable=True)
    protected_class_data = Column(JSON)  # для bias audit
```

**Зачем:** EU AI Act требует audit trail для всех high-risk AI decisions.

#### 2. **Human-in-the-Loop для Reject**
```python
# app/routers/screenings.py
@router.post("/{screening_id}/reject")
async def reject_screening(
    screening_id: UUID,
    reason: RejectReason,  # NEW: обязательная причина
    human_reviewed: bool = False,  # NEW: флаг ручной проверки
    current_user: User = Depends(get_current_user)
):
    # Логируем решение
    await log_ai_decision(
        screening_id=screening_id,
        decision_type="reject",
        human_override=human_reviewed,
        reviewer_id=current_user.id if human_reviewed else None
    )
```

**Зачем:** EEOC требует human oversight для adverse decisions.

#### 3. **Bias Monitoring (Four-Fifths Rule)**
```python
# app/services/bias_audit.py
async def check_adverse_impact(agency_id: UUID):
    """
    Проверка на дискриминацию по защищенным классам.
    Four-fifths rule: selection rate для защищенной группы 
    должна быть >= 80% от selection rate основной группы.
    """
    # Пример:
    # Если 60% мужчин проходят скрининг, 
    # то минимум 48% (60% * 0.8) женщин должны проходить
    
    stats = await get_selection_rates_by_demographics(agency_id)
    
    if stats["female_rate"] < stats["male_rate"] * 0.8:
        # ALERT: Возможная дискриминация по полу
        await send_compliance_alert(agency_id, "gender_bias")
```

**Зачем:** Обязательно для NYC AEDT Law (с 2023) и EU AI Act.

---

## 🚀 Оптимизация #1: Rate Limiting (КРИТИЧНО для стабильности)

### Проблема:
**У нас НЕТ rate limiting** - кандидат может спамить бота и уронить систему.

### Решение (из DEV Community, production bot):
```python
# bot/middleware.py - НОВЫЙ ФАЙЛ
from aiogram import BaseMiddleware
from cachetools import TTLCache

class ThrottleMiddleware(BaseMiddleware):
    """
    Drop второго сообщения от юзера в течение N секунд.
    Без этого: burst traffic → burst API calls → Telegram flood control → crash.
    """
    def __init__(self, rate_limit: float = 1.0):
        self.cache = TTLCache(maxsize=10_000, ttl=rate_limit)
    
    async def __call__(self, handler, event, data):
        user_id = event.message.from_user.id if event.message else None
        if user_id and user_id in self.cache:
            return  # Silently drop - user over rate limit
        if user_id:
            self.cache[user_id] = True
        return await handler(event, data)
```

**Интеграция:**
```python
# bot/__main__.py
from bot.middleware import ThrottleMiddleware

dp.message.middleware(ThrottleMiddleware(rate_limit=1.0))  # 1 сообщение в секунду
```

**Эффект:**
- ✅ Bot не падает при спаме
- ✅ Нет Telegram `TelegramRetryAfter` errors
- ✅ Стабильная работа под нагрузкой

**Источник:** DEV Community - "Production bot crashing every 2 hours" (2026)

---

## 🚀 Оптимизация #2: Advanced AI Ranking (arXiv 2603.26710)

### Проблема:
Текущий scoring (0-100) - это простой single-pass LLM call.

### Решение: Active Listwise Tournament
```python
# app/services/advanced_ranking.py
from scipy.optimize import minimize

async def rank_candidates_tournament(
    vacancy_text: str,
    candidates: List[Candidate]
) -> List[Tuple[Candidate, float]]:
    """
    Active Listwise Tournament:
    1. LLM ranks mini-tournaments (3-5 candidates at a time)
    2. Plackett-Luce model aggregates results
    3. Active learning selects most informative subsets
    
    Результат: Globally coherent ranking, sample-efficient.
    """
    
    # Stage 1: Mini-tournaments
    tournaments = create_mini_tournaments(candidates, size=3)
    
    results = []
    for tournament in tournaments:
        # LLM ranks 3 candidates at once (listwise)
        ranking = await llm_rank_candidates(
            vacancy_text,
            tournament,
            mode="listwise"  # Not pairwise!
        )
        results.append(ranking)
    
    # Stage 2: Plackett-Luce aggregation
    global_scores = plackett_luce_aggregate(results)
    
    # Stage 3: Active learning (select uncertain pairs for re-ranking)
    if has_high_uncertainty(global_scores):
        uncertain_pairs = select_uncertain_pairs(global_scores)
        refined_results = await llm_rank_candidates(
            vacancy_text,
            uncertain_pairs,
            mode="listwise"
        )
        global_scores = update_scores(global_scores, refined_results)
    
    return sorted(zip(candidates, global_scores), key=lambda x: x[1], reverse=True)
```

**Преимущества:**
- ✅ Более стабильное сравнение (не pairwise noise)
- ✅ Sample-efficient (меньше LLM calls)
- ✅ Globally coherent (учитывает всех кандидатов)

**Источник:** EACL 2026 (European ACL Conference)

---

## 🚀 Оптимизация #3: Async Queue Architecture

### Проблема:
Сейчас `run_resume_pipeline` блокирует бота на ~60 секунд (LLM + API calls).

### Решение: Decoupling (из Serverless Bot guide):
```
Telegram → Handler (instant 200 OK) → Redis Queue → Worker → DB + Telegram API
```

**Архитектура:**
```python
# bot/handlers.py
async def handle_resume(update, ctx):
    # БЫСТРО: только валидация + push в queue
    await message.reply_text("Резюме получено!")  # Instant reply
    
    # Push в Redis queue
    await redis.lpush("resume_queue", json.dumps({
        "chat_id": chat_id,
        "resume_data": resume_input,
        "user_data": ctx.user_data
    }))
    
    return  # Handler завершился за <50ms

# bot/workers.py - ОТДЕЛЬНЫЙ ПРОЦЕСС
async def resume_worker():
    while True:
        # Pull из queue
        task = await redis.brpop("resume_queue", timeout=1)
        if task:
            # Long-running work (LLM, API calls)
            await run_resume_pipeline(**task)
```

**Преимущества:**
- ✅ Bot handler instant (не блокируется)
- ✅ Horizontal scaling (N workers)
- ✅ Resilience (если worker падает - task в queue)

**Источник:** Bayashat/serverless-tg-bot-starter, SmartHire-Showcase

---

## 🚀 Оптимизация #4: Multi-Agent Evaluation

### Проблема:
Один LLM call может галлюцинировать или быть inconsistent.

### Решение: Multi-Agent Architecture (arXiv 2603.26710)
```python
# app/services/multi_agent_scoring.py
async def multi_agent_screening(vacancy_text: str, resume_text: str) -> dict:
    """
    3 агента оценивают независимо, результаты агрегируются.
    """
    
    # Agent 1: Technical Skills
    technical_score = await llm_evaluate(
        prompt=f"Оцени ТОЛЬКО технические навыки...",
        resume=resume_text,
        vacancy=vacancy_text
    )
    
    # Agent 2: Experience & Projects
    experience_score = await llm_evaluate(
        prompt=f"Оцени ТОЛЬКО опыт и проекты...",
        resume=resume_text,
        vacancy=vacancy_text
    )
    
    # Agent 3: Cultural Fit & Motivation
    fit_score = await llm_evaluate(
        prompt=f"Оцени мотивацию и soft skills...",
        resume=resume_text,
        vacancy=vacancy_text
    )
    
    # Weighted average
    final_score = (
        technical_score * 0.5 +
        experience_score * 0.3 +
        fit_score * 0.2
    )
    
    return {
        "final_score": final_score,
        "breakdown": {
            "technical": technical_score,
            "experience": experience_score,
            "fit": fit_score
        }
    }
```

**Преимущества:**
- ✅ Более надежная оценка (consensus)
- ✅ Explainable (breakdown по критериям)
- ✅ Меньше галлюцинаций

---

## 📊 Приоритизация внедрения

| # | Улучшение | Критичность | Effort | Impact | Срок |
|---|-----------|-------------|--------|--------|------|
| 1 | **Rate Limiting** | 🔴 CRITICAL | Low (1h) | High | Сегодня |
| 2 | **Audit Logging** | 🔴 CRITICAL | Medium (4h) | High | 1-2 дня |
| 3 | **Human-in-the-loop** | 🟡 HIGH | Medium (4h) | High | 3-5 дней |
| 4 | **Async Queue** | 🟡 HIGH | High (8h) | Medium | 1-2 недели |
| 5 | **Bias Monitoring** | 🟡 MEDIUM | Medium (6h) | Medium | 2-3 недели |
| 6 | **Multi-Agent** | 🟢 LOW | High (12h) | Medium | Backlog |
| 7 | **Tournament Ranking** | 🟢 LOW | High (16h) | Low | Backlog |

---

## 🎯 Рекомендация: Quick Wins

**Внедрить СЕГОДНЯ (2-3 часа):**
1. ✅ **Rate Limiting** (ThrottleMiddleware) - 18 lines of code, huge stability win
2. ✅ **Basic Audit Logging** - create table + log AI decisions

**Внедрить на ЭТОЙ НЕДЕЛЕ:**
3. ✅ **Human-in-the-loop reject** - add `human_reviewed` flag
4. ✅ **Health checks** - простой `/health` endpoint

**Backlog (когда масштабируемся):**
5. Async queue architecture (Redis/SQS)
6. Multi-agent evaluation
7. Bias monitoring dashboard

---

## 📚 Источники

1. Pin.com - "AI Recruiting: The Complete 2026 Guide"
2. DigitalApplied - "Agentic AI HR Team Playbook 2026"
3. arXiv 2603.26710 - "LLM-Driven Candidate Assessment" (EACL 2026)
4. DEV Community - "Production Telegram Bot Crashing Fix" (2026)
5. SmartHire-Showcase - Multi-tenant aiogram 3.26 architecture
6. Serverless Telegram Bot Starter (AWS CDK + SQS)

---

**Итого:** Самые критичные - Rate Limiting и Audit Logging. Всё остальное - incremental improvements.
