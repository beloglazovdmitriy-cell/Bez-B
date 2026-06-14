# «Без Б» — статус проекта (точка продолжения)

_Обновлено: 2026-06-14. Последний коммит: `f1a39ad`._
Связанные доки: `PLAN.md`, `ROADMAP_MINIAPP.md`, `AI_ARCHITECTURE.md`.
Память ассистента: `MEMORY.md` (раздел `bezb-content-vs-process` — подробный лог).

---

## 1. Что это
Telegram Mini App + бот «Без Б — инвестиции без буллшита». Публичный портфель
владельца + личные портфели юзеров + AI-аналитика + контент-конвейер в канал +
игры вовлечения. Бренд: прозрачность, дисциплина, анти-инфоцыган, НЕ сигналы.

## 2. Инфраструктура / деплой
- **VPS Beget** (OpenClaw), Ubuntu 24.04, IP `155.212.134.96`, root по паролю.
- Боевой адрес: `https://155.212.134.96.sslip.io/` (Mini App) + `/landing/` (лендинг).
- Код на сервере: `/opt/bezb` (git clone). Сервисы systemd: `bezb-api`
  (uvicorn 127.0.0.1:8000) и `bezb-bot` (polling). nginx: SPA из `/opt/bezb/dist`,
  `/api`→uvicorn, `/landing/`→`/opt/bezb/landing`. TLS Let's Encrypt.
- Репозиторий GitHub: `beloglazovdmitriy-cell/Bez-B` (main).
- Деплой-доступ локально: PuTTY `plink/pscp` (`C:\Program Files\PuTTY`),
  hostkey `SHA256:f9uwxAXPzT7/Q/PXF+OKB3lroVNZ9G4hapUxiIRNquQ`.
  Деплой-файлы: `C:\Users\belog\_deploy\` (deploy.sh, nginx_bezb.conf; .env.server вне репо).

### Передеплой (стандартная процедура)
```
# backend (api/bot/storage/…):
plink ... root@155.212.134.96 "cd /opt/bezb && git pull --ff-only && systemctl restart bezb-api bezb-bot"
# frontend (после npm run build в miniapp):
pscp ... -r dist/* root@155.212.134.96:/opt/bezb/dist/
```
Фронт: `cd miniapp && npm run build` → залить `dist/*`. ВАЖНО: Telegram кэширует
Mini App — после деплоя полностью закрыть/переоткрыть приложение.

## 3. Запуск локально
- API: `./.venv/Scripts/python.exe -m uvicorn api:app --port 8000`
- Фронт: `cd miniapp && npm run dev` (localhost:5173, vite-прокси /api→8000).
- Бот локально НЕ запускать одновременно с сервером (конфликт getUpdates).
- venv: `.venv` (Windows). Тесты бэка — через fastapi TestClient.

## 4. Ключи в `/opt/bezb/.env` (env-driven, активируются по ключу)
- `BOT_TOKEN`, `ADMIN_ID=503720103`, `CHANNEL_ID=-1003200932631` (@BezBlogfin) — заданы.
- `ANTHROPIC_API_KEY` (+ `ANTHROPIC_BASE_URL=https://api.tokenator.top/anthropic`,
  `AI_MODEL=gpt-5.5`, `AI_POST_MODEL=gpt-5.5`, `AI_REASONING=1`) — AI РАБОТАЕТ (прокси, не офиц. Claude).
- `FINNHUB_API_KEY` — ЗАДАН, цены акций США работают.
- `PAYMENT_PROVIDER_TOKEN` — **НЕ задан** (оплата ждёт токен Сбера из @BotFather).

## 5. ГОТОВО (всё задеплоено)
**Ядро:** Mini App (7 вкладок: Лента/Портфель/Динамика/Журнал/Расчёт/Сделки/Профиль),
мультипортфель (Без Б / Мой / 🏆 Фэнтези), бот, SQLite (`portfolio.db`).
**AI:** разбор портфеля, разбор сделки→канал, сценарии, дайджест (веб-поиск+фолбэк),
тон под живых блогеров.
**Контент-конвейер:** студия (рубрики→черновики→ревью→публикация с графиком/картинкой
+ опц. кнопка бота), планировщик (расписание рубрик), рубрики
digest/crowd/scenarios/edu/manifest/bullshit/**ta (теханализ)**.
**Данные:** крипта Binance, акции Finnhub, курс ЦБ РФ, Fear&Greed, своя история цен
(ежедневный снимок 23:50 MSK, копится вперёд).
**Вовлечение:** реакции в ленте, экран «Главная» (гейдж страха/жадности крипты +
дайджест + что сделал Без Б), стрик дисциплины DCA, DCA-песочница (бэктест),
онбординг 5 уроков, Q&A (AI + личный ответ автора).
**Игры:** 🔮 Прогноз недели (голос выше/ниже + лидерборд, авто-цикл Пн), 🎯 Квиз «Детектор
буллшита» (16 карточек, очки/серии/бейджи), 🏆 Сезон фэнтези-портфелей ($10k вирт.,
рейтинг vs Без Б).
**Монетизация:** оплата премиума через Telegram Payments (Сбер) — ОСНОВА готова
(ждёт токен); гейтинг фич за isPremium (AI по своему портфелю, пуши о сделках,
Q&A 10/день vs 1/день free).
**Контент-графики:** TA-график «карта уровней» (Хейкен Аши + авто-S/R), наш стиль.
**Прочее:** лендинг `/landing/` + форма обратной связи с согласиями 152-ФЗ;
мгновенные пуши подписчикам о сделках; доп-админы по @username (@GLBST1 = админ).

## 6. ОСТАЛОСЬ / приоритеты на продолжение
1. 💳 **Оплата** — получить `PAYMENT_PROVIDER_TOKEN` (СберБизнес эквайринг + @BotFather)
   → вставить в .env → restart. Нужна онлайн-касса для чеков 54-ФЗ.
2. 🔒 **Безопасность** — ротация засвеченных в чате: root-пароль VPS → SSH-ключ;
   токены бота/прокси/Finnhub. Сменить root-пароль Beget.
3. 💬 **Комментарии в ленте** (соц-слой, реакции уже есть).
4. 🏁 **Финал сезона фэнтези** — джоба закрытия + объявление победителей в канал.
5. Идеи игр: «пик Без Б» в Прогнозе (выбор автора после голосования), 🧠 сделка дня.
6. Контент/данные: TA по разным монетам + выбор ТФ; график акций США когда
   накопится своя история; свой «Индекс Без Б».
7. Мелочи: кнопка «О проекте» в Профиле; чистка старых ассетов в `/opt/bezb/dist`.
8. Фаза 3: OpenClaw чат-ассистент (нужен апгрейд VPS до 4ГБ) — премиум.

## 7. Действия владельца (вне кода)
- Привязать **группу обсуждений** к каналу @BezBlogfin (для комментариев под постами).
- Убедиться, что у @GLBST1 установлен **username** (права привязаны к нему).
- В `landing/privacy.html` добавить ИНН/адрес, если оформит ИП/самозанятость.
- Получить Сбер provider token (п.6.1). Finnhub-ключ уже выдан.

## 8. Тех-долг / заметки
- Публичный портфель Без Б на сервере ПУСТ → «что сделал Без Б», дайджест в ленте и
  bezb_start для фэнтези/сравнений = пустые/0, пока не наполнить реальными сделками.
- Гейтинг премиума «живой» только после подключения оплаты (сейчас премиум есть лишь
  у владельца/доп-админов).
- Референс-графики Эвана убраны из репо (.gitignore), остаются в истории коммита
  a2067d2; локально на диске сохранены.
- TZ сервера = Europe/Moscow (наивные времена джоб = MSK).
- Telegram тянет цифровые подписки на Stars (особенно iOS) — гейт держим мягким.

## 9. Карта файлов (бэкенд)
`api.py` (FastAPI, все эндпоинты) · `bot.py` (бот+джобы+платежи) · `storage.py`
(SQLite: портфели, drafts, reactions, subscribers, dca, qa, onboarding, premium,
price_history, pred_*, quiz, fantasy_*, feedback, extra_admins) · `portfolio.py`
(логика портфеля) · `quotes.py` (цены) · `charts.py` (графики, ta_chart) ·
`techa.py` (Хейкен Аши + уровни) · `sandbox.py` (DCA-бэктест) · `market_mood.py`
(Fear&Greed) · `ai.py` (Claude/прокси) · `quiz_data.py` (вопросы квиза) ·
`notify.py` (пуши о сделках) · `config.py` · `benchmark.py`.
Фронт: `miniapp/src/` — `screens/` (экраны вкладок), `components/` (HomeHeader,
PredictCard, QuizSheet, FantasyBanner, DcaStreak, Onboarding, ContentStudio,
QaSheet, SandboxDca, TradeSheet, …), `data.ts` (API-клиент), `useAppData.ts`,
`mock.ts`, `theme.css`. Лендинг: `landing/index.html`, `landing/privacy.html`.
