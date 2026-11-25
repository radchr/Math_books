# Модульна бібліотека візуальних заготовок, доменні пакети та банк сценаріїв

**Дата:** 2026-11-25
**Статус:** дизайн-специфікація на погодження
**Мета:** побудувати модульну, доменно-незалежну архітектуру для 9:16 тримовних (`uk`/`ru`/`en`) відео, щоб додавати нові предметні напрями (фізика, історія, програмування, біологія тощо) без переписування ядра, з єдиною бібліотекою візуальних заготовок та перевикористовуваним банком ідей і сценаріїв.

---

## 1. Архітектурні принципи та межі

1. **Ядро (`core`) vs. Доменні пакети (`packs`):**
   - **Ядро** не знає нічого специфічного про баскетбол чи конкретний шкільний предмет. Воно відповідає за:
     - 9:16 сітку та перевірку меж кадру (`|x| <= 4.35`, `y ∈ [-6.15, +7.45]`);
     - систему тем оформлення (`Theme`);
     - універсальні візуальні заготовки (`text_card`, `hook_choice`, `compare_bars`, `step_chain`, `challenge_card`, …);
     - локалізовані UI-рядки (`ui_strings.json` на `uk`/`ru`/`en`);
     - декларативний рендерер (`LocalizedLessonScene`) і синхронізацію `cue_timeline.py`;
     - розширюваний реєстр перевірок у `content_review.py`;
     - банк ідей/сценаріїв (`content/bank/`) + перезбираний SQLite-індекс.
   - **Доменні пакети (`src/math_books/packs/<pack_name>/`)** підключаються декларативно через спільний реєстр і додають:
     - спеціалізовані візуальні заготовки (наприклад, `packs/basketball/` → `half_court_diagram`, `scoreboard_duel`);
     - власні іменовані теми оформлення (наприклад, `basketball_dark`);
     - доменні чекери для редакційного гейту (наприклад, `independent_chain`, `expected_points` у математичному пакеті; у майбутньому — `timeline_order` для історії чи `unit_consistency` для фізики);
     - доменні локалізовані UI-рядки (`uk`/`ru`/`en`).
2. **Зворотна сумісність:**
   - 7 legacy-тем (`basketball`, `ahrens`, `simpson`, `moneybart`, `hothand`, `free_throws`, `buzzer`) не змінюються і не переробляються.
   - `content/lessons/language_demo.json` залишається повністю валідним: сцена без поля `visual` автоматично рендериться базовим блоком `text_card`.
   - Існуючі гарантії безпеки (секрети в заголовках, read-only `list`, атомарні sidecar-записи, мовний ASR + акустичний QA, обов'язковий `content_review`) зберігаються без послаблень.

---

## 2. Структура модулів (цільова)

```text
src/math_books/
  themes.py                     # Базова 9:16 дизайн-система + Theme registry (basketball_dark, science_lab, ...)
  ui_strings.json               # Спільні UI-підписи ядра на uk/ru/en (pause, answer, plan_a, ...)
  visual_blocks/
    __init__.py                 # VisualBlock протокол, VisualRegistry, валідація params & cue_targets
    text_card.py                # Стандартна картка (fallback для сцен без visual)
    hook_choice.py              # Вибір "А чи Б" (2 контрастні картки + підсвітка)
    compare_bars.py             # Стовпчики порівняння (точні Fraction-висоти + підсвітка лідера)
    step_chain.py               # Ланцюжок кроків A -> B -> C = результат
    challenge_card.py           # Умова -> пауза -> cue-розкриття відповіді + межа моделі
  packs/
    __init__.py                 # DomainPack протокол та авто-реєстрація пакетів
    basketball/
      __init__.py               # Тема basketball_dark, UI-рядки (ТАБЛО/SCOREBOARD), реєстрація блоків
      half_court_diagram.py     # Параметризований майданчик (гравці, стрілки, кути, зони)
      scoreboard_duel.py        # Табло з рахунком і таймером до сирени
  content_bank.py               # JSON-схема content/bank/, перезбираний SQLite-індекс, list/show/promote
  content_review.py             # Розширюваний check_registry + гнучка audience_age для нових уроків
  localized_lesson_scene.py     # Рендерить будь-який зареєстрований VisualBlock із прив'язкою до cues
```

---

## 3. Контракт візуальної заготовки (`VisualBlock`) і тем (`Theme`)

### 3.1. Тема оформлення (`Theme`)
Кожен урок (або доменний пакет) обирає іменовану тему (`"theme": "basketball_dark"` за замовчуванням для баскетболу або `"neutral_dark"` у ядрі):
- Кольори: `bg`, `card_bg`, `primary`, `secondary`, `accent_positive`, `accent_warning`, `text_primary`, `text_muted`.
- Незмінні інваріанти ядра: `1080×1920`, `30 fps`, шрифт `DejaVu Sans` (`FONT`), безпечна зона `|x| <= 4.35`, `y ∈ [-6.15, +7.45]`, фіксовані вертикальні слоти (`badge`, `subtitle`, `stage`, `caption`).

### 3.2. Контракт `VisualBlock`
Кожна заготовка описує себе декларативно (це одночасно використовується валідатором схеми, `cue_timeline.py` і промптом для `feynman-manim-composer`):
- `name: str` — унікальний ID (наприклад, `"compare_bars"`, `"basketball.half_court_diagram"`).
- `pack: str` — `"core"` або назва пакета (`"basketball"`).
- `cue_targets: frozenset[str]` — допустимі `target` для `cues` (наприклад, `{"title", "bar_1", "bar_2", "winner", "formula"}`).
- `validate_params(params: dict, translations: dict) -> None` — перевіряє точні числові дані (`Fraction`/рядки), межі та наявність обов'язкових локалізованих підписів для всіх 3 мов (`uk`, `ru`, `en`).
- `build(scene, theme, language, row) -> dict[str, Mobject]` — створює об'єкти Manim і повертає словник `target_name -> Mobject`, яким керує `LocalizedLessonScene` відповідно до замороженого `event_timeline`.

### 3.3. Приклад сцени в `content/lessons/<topic>.json` (зворотно сумісно)
```json
{
  "schema_version": 1,
  "topic": "example_topic",
  "domain": "basketball",
  "theme": "basketball_dark",
  "scenes": [
    {
      "id": "02_compare",
      "formula": "0.30 > 0.245",
      "visual": {
        "template": "compare_bars",
        "params": {
          "items": [
            {"id": "plan_a", "value": "3/10", "color": "primary"},
            {"id": "plan_b", "value": "49/200", "color": "secondary"}
          ],
          "winner": "plan_a"
        }
      },
      "cues": [
        {
          "id": "show_winner",
          "target": "winner",
          "anchor": "start",
          "occurrence": 1,
          "phrases": {"uk": "більше", "ru": "больше", "en": "higher"}
        }
      ],
      "translations": {
        "uk": {
          "text": "...",
          "title": "Порівняння шансів",
          "body": "Один кидок проти ланцюжка з трьох кроків.",
          "labels": {"plan_a": "План А (30%)", "plan_b": "План Б (24,5%)"}
        },
        "ru": { "text": "...", "title": "...", "body": "...", "labels": {"plan_a": "...", "plan_b": "..."} },
        "en": { "text": "...", "title": "...", "body": "...", "labels": {"plan_a": "...", "plan_b": "..."} }
      }
    }
  ]
}
```
- Якщо `visual` відсутній — використовується `text_card`, а `labels` не потрібні (`language_demo.json` працює без змін).
- Жодних захардкоджених слів у Python-коді заготовки; системні підписи беруться з `ui_strings.json` (`uk`/`ru`/`en`).

---

## 4. Банк ідей та сценаріїв (`content/bank/`) + SQLite-індекс

### 4.1. Зберігання та перевикористання
- **Джерело істини (в git):** `content/bank/<id>.json` — по одному JSON-файлу на ідею/сценарій.
- **Локальний індекс (ігнорується git):** `.cache/bank.sqlite` — автоматично перезбирається з `content/bank/*.json` при зміні mtime/хешу файлів (не потребує ручних міграцій і ніколи не конфліктує в git).

### 4.2. Поля запису в `content/bank/<id>.json`
- `schema_version`: `1`
- `id`: стабільний slug (`[a-z][a-z0-9_]*`)
- `status`: `"idea" | "draft" | "promoted" | "produced" | "parked"`
- `domain`: `"basketball" | "physics" | "history" | ...`
- `theme`: іменована тема (наприклад, `"basketball_dark"`)
- `audience`: `{"min_age": 12, "max_age": 12}` (або ширший діапазон для майбутніх тем)
- `tags`: список тегів (`["probability", "multiplication_rule", "endgame"]`)
- `source`: `{"title": "...", "locator": "...", "url": "..."}` (необов'язково для ранньої `idea`, обов'язково перед `promote`)
- `core_concept`: незалежне від «обгортки» ядро (наприклад, математична/фізична модель + список `templates_used`), що дозволяє перевикористовувати структуру під інший домен.
- `alt_hooks`: список альтернативних хуків (`uk`/`ru`/`en`), щоб не викидати сильні варіанти.
- `promoted_lesson`: `null` або `{"topic": "<topic>", "path": "content/lessons/<topic>.json", "promoted_at": "..."}`
- `lesson_draft`: повна 3-мовна структура сцен (`scenes`, `visual`, `cues`, `translations`) — обов'язкова для `status >= "draft"`.

### 4.3. CLI-команди банку (`math-books bank ...`)
- `uv run math-books bank list [--status ...] [--domain ...] [--tag ...] [--template ...]` — швидка фільтрація через SQLite-індекс.
- `uv run math-books bank show <id>` — детальний перегляд картки, шаблонів, `alt_hooks` і статусу.
- `uv run math-books bank promote <id> [--topic <new_topic>]` — **експортує** валідну чернетку у `content/lessons/<topic>.json`, залишаючи оригінал у `content/bank/<id>.json` (оновлює `status: "promoted"` і `promoted_lesson` атомарно через `atomic_json`, щоб запис можна було перевикористовувати для реміксів або нових обгорток). Ніколи не перезаписує існуючий `content/lessons/<topic>.json` без явної помилки і ніколи не фабрикує `content_reviews/`.
- `uv run math-books bank catalog` — виводить машиночитаний або табличний каталог усіх доступних `VisualBlock` (назва, пакет, параметри, `cue_targets`), який напряму використовується при генерації сценаріїв.

---

## 5. Модульний редакційний гейт (`content_review.py`)

- Вводимо реєстр перевірок `CHECK_REGISTRY: dict[str, Callable[[dict], dict]]`:
  - Базові математичні перевірки (`independent_attempts`, `expected_points`, `fair_coin_followups`, `independent_chain`) реєструються через реєстр, а не хардкодяться в `if`-ланцюжку.
  - Нові доменні пакети можуть додавати власні детерміновані чекери в `CHECK_REGISTRY` без редагування ядра `content_review.py`.
- Поле `pedagogy.audience_age`:
  - Для legacy-тем зберігається поточна перевірка `audience_age == 12`.
  - Для нових декларативних уроків підтримується додатне ціле число (наприклад, `12`, `16`) або діапазон (`{"min": 10, "max": 14}`).

---

## 6. Візуальна гарантія (3-мовний Showcase)

- Автоматичний тест/команда перевірки шаблонів рендерить або збирає кожен зареєстрований `VisualBlock` для всіх 3 мов (`uk`, `ru`, `en`) із реалістичними довгими рядками й проганяє `check_frame_bounds()` (перевірка меж 9:16 без виходу за `|x| <= 4.35`, `y ∈ [-6.15, +7.45]`).
- Дозволяє відловлювати наїзди тексту чи переповнення українських/англійських підписів ще на етапі розробки шаблону, до створення реального уроку.

---

## 7. Обсяг першої ітерації (MVP)

1. **Ядро тем і UI-рядків:** `themes.py` (`neutral_dark`, `basketball_dark`) + `ui_strings.json` (`uk`/`ru`/`en`).
2. **Реєстр і 5 універсальних блоків ядра:** `text_card`, `hook_choice`, `compare_bars`, `step_chain`, `challenge_card`.
3. **Перший доменний пакет `packs/basketball/`:** 2 доменні блоки (`half_court_diagram`, `scoreboard_duel`) + підключення через `DomainPack`.
4. **Інтеграція з уроками та `cue_timeline.py`:** зворотна сумісність із `language_demo.json`, підтримка `visual.template`, `labels` і блокових `cue_targets` у `lessons.py`, `cue_timeline.py`, `localized_lesson_scene.py`, `video_builder.py` (включення файлів блоків/тем у `render_fingerprint`).
5. **Розширюваний `content_review.py`:** `CHECK_REGISTRY` + гнучка `audience_age` для нових уроків.
6. **Банк сценаріїв:** `content_bank.py` + `content/bank/` (1–2 прикладні записи `idea` і `draft`) + `.cache/bank.sqlite` + CLI `math-books bank list / show / promote / catalog`.
7. **Тести та 3-мовний 9:16 showcase:** unit/regression тести для реєстру блоків, тем, банку, `promote`, `CHECK_REGISTRY` і меж кадру 9:16 на `uk`/`ru`/`en`.
