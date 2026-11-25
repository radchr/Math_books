# Math_books

Інструменти та автоматизовані пайплайни для двох напрямів:

1. **Науково-популярні вертикальні відео (`9:16`, `1080×1920`, `30 fps`)** — короткі освітні ролики (YouTube Shorts / TikTok / Reels) із математики, фізики, хімії, біології та баскетбольної аналітики на базі **Manim + TTS / фонова музика + `ffmpeg`**.
   - **Нові багатомовні уроки (`uk` / `ru` / `en`)** будуються декларативно з банку сценаріїв (`content/bank/` → `content/lessons/`) та модульної бібліотеки візуальних блоків (`visual_blocks/`).
   - Підтримуються два режими звуку: **`voiceover`** (озвучка + локальна ASR-перевірка) та **`music_only`** (фонова музика з бази `assets/music/` + наекранні титри й схеми).
   - **7 базових російськомовних сцен** про баскетбол і математику збережено без змін як legacy-пайплайн; ранні тестові збірки заархівовано в [`test_videos/`](test_videos/README.md), а нові продакшн-відео збираються в `videos/video_<topic>/`.
2. **Оцифрування математичних книг** — локальний прототип (`math-books digitize`), який об'єднує HTML/скани з `mathedu.ru` та JSON-розмітку **MinerU**, вирізає ілюстрації й збирає чистий Markdown.

---

## Ключові можливості

- **Банк сценаріїв (`content/bank/`):** Git-версіоновані ідеї та чернетки уроків із тегами, доменами, першоджерелами та перебудовуваним SQLite-індексом пошуку (`.cache/bank.sqlite`). Промоція в урок однією командою (`math-books bank promote`).
- **Модульні візуальні блоки (`src/math_books/visual_blocks/`):** перевикористовувані 9:16-компоненти (`text_card`, `hook_choice`, `compare_bars`, `step_chain`, `challenge_card`, `image_stage` для SVG/PNG-схем, а також доменний пак `packs/basketball/`) і теми оформлення (`neutral_dark`, `science_lab`, `basketball_dark`).
- **Озвучка (`voiceover`) + локальний контроль якості:**
  - За замовчуванням для всіх мов (`uk`, `ru`, `en`) використовується **Gemini TTS**.
  - Для української мови (`--lang uk`) при недоступності Gemini автоматично вмикається резервний ланцюжок: **StyleTTS2 → локальний Piper → Edge TTS** (із фіксацією єдиного голосу на весь ролик і нормалізацією до 24 kHz mono PCM WAV).
  - Кожен кліп автоматично перевіряється локальним **`faster-whisper`** (`voiceover_qa.py`) на збіг чисел, заперечень, термінів, відсутність дублів і промпт-витоків + проходить акустичний скринінг (`audio_quality.py`).
- **Режим без голосу (`music_only`) і перевикористовувана музична база (`assets/music/`):**
  - Короткі 20–45-секундні ролики з наекранними титрами, формулами й схемами (`image_stage`) та фоновою музикою.
  - Команда `math-books music` керує каталогом треків: локальна процедурна генерація (`procedural`), опційні AI-бекенди (`lyria`, `musicgen`, `ace_step`) та імпорт готових CC0 / royalty-free треків через `ffmpeg`.
- **Обов'язковий науково-педагогічний гейт (`content_review.py`):**
  - Жоден ролик — **ні `voiceover`, ні `music_only`** — не може перейти до озвучки чи рендеру без схваленого досьє в `content_reviews/<lang>/<topic>.json`.
  - Перевіряються точні обчислення (`CHECK_REGISTRY`), припущення, межі моделі (`limitations`), відповідність цитат (`script_quote`) і прив'язка схвалення до хешу поточної версії сценарію.

---

## Встановлення та налаштування

```bash
uv sync
cp .env.example .env
# Додайте GEMINI_API_KEY у .env для Gemini TTS (та опційної генерації музики Lyria).
# Ніколи не комітьте .env і не публікуйте ключі.
```

**Системні вимоги:** Python `>= 3.13`, `uv`, `ffmpeg`, `ffprobe` та `pdflatex` (для формул Manim `MathTex`).

---

## Використання CLI (`math-books`)

### 1. Огляд проєкту та банк сценаріїв

```bash
# Швидкий read-only список усіх тем і статусів рев'ю/медіа
uv run math-books list

# Пошук і перегляд ідей у банку сценаріїв
uv run math-books bank list
uv run math-books bank search --domain physics --tag acoustics
uv run math-books bank show perelman_echo_distance

# Промоція сценарію з банку в декларативний тримовний урок (content/lessons/<topic>.json)
uv run math-books bank promote perelman_echo_distance
```

### 2. Науково-педагогічне рев'ю (обов'язково перед виробництвом)

```bash
# Створити шаблон досьє для нового уроку (не перезаписує існуючий файл)
uv run math-books review hack_a_shaq_math --lang uk --init

# Перевірити досьє (має повернути ok: true)
uv run math-books review hack_a_shaq_math --lang uk

# Перевірити всі теми одразу
uv run math-books review all
```

### 3. Озвучка (`voiceover`) або музична база (`music_only`)

```bash
# Режим voiceover: Gemini TTS за замовчуванням (для --lang uk є авто-fallback на uk-ланцюжок)
uv run math-books tts hack_a_shaq_math --lang uk --trim-edges

# Примусово використати український fallback-ланцюжок (StyleTTS2 -> Piper -> Edge TTS)
uv run math-books tts hack_a_shaq_math --lang uk --provider uk --uk-profile tyshyn --trim-edges

# Явна перевірка аудіо та локальних ASR-квитанцій
uv run math-books verify-audio hack_a_shaq_math --lang uk

# Режим music_only: перегляд, генерація або імпорт фонової музики в assets/music/
uv run math-books music list
uv run math-books music generate my_beat --backend procedural --style energetic --bpm 124 --duration 32
uv run math-books music import /path/to/track.mp3 --id upbeat_cc0 --license "CC0-1.0" --source "https://..."
```

### 4. Збірка та верифікація відео

```bash
# Зібрати відео (рендер тихого Manim + аудіодоріжка / музична підкладка + mux + перевірка)
uv run math-books build hack_a_shaq_math --lang uk
uv run math-books build perelman_echo_distance --lang uk

# Повна верифікація потоків, тривалості, provenance та витяг прев'ю-кадрів (preview_frames/)
uv run math-books verify hack_a_shaq_math --lang uk --frames
uv run math-books verify perelman_echo_distance --lang uk --frames
```

### 5. Оцифрування книг (`digitize`)

```bash
# Збірка Markdown + вирізані рисунки з локальних HTML (mathedu.ru) та MinerU JSON
uv run math-books digitize --pages 13-16

# Вибір окремої сторінки без порушення нумерації вхідного MinerU JSON
uv run math-books digitize --pages 14 --source-pages 13-16 --out-dir /tmp/page-14
```

---

## Надійність, синхронізація та контроль походження

- **Незмінні аудіокліпи та кеш:** нові WAV-файли зберігаються в `videos/video_<topic>/<lang>/audio/clips/` із хешем тексту, голосу, моделі та вмісту файлу. Старі версії не перезаписуються; провалена генерація не ламає попередній `manifest.json`.
- **Атомарність і блокування:** `tts`, `build` і `verify` беруть per-topic lock, щоб паралельні процеси не пошкодили артефакти.
- **Контроль кадру `9:16` та таймінгу:** `VerticalShortScene._pad()` вимірює реальний час рендерера (блокує перевищення тривалості сцени) й автоматично перевіряє межі кадру (`|x| <= 4.35`, `y ∈ [-6.15, +7.45]`).
- **Синхронізація появ:** декларативні уроки використовують явні `cues` ([`cue_timeline.py`](src/math_books/cue_timeline.py)) — за словами диктора (`voiceover`) або за секундами (`music_only`).
- **Повний ланцюжок довіри (`provenance`):** `.render.json` і `.build.json` зв'язують хеші коду/уроку, аудіо й фінального `.mp4`. `--skip-render` спрацює лише за повного збігу вхідних даних. `math-books list` є суворо read-only і не сертифікує медіа — остаточним доказом готовності є `verify --frames` та візуальна інспекція кадрів.
- **Рев'ю неможливо обійти:** ані `--force`, ані `--skip-render`, ані кеш аудіо не пропускають `content_review.py`. Схвалення не переноситься між мовами.

---

## Розробка та CI

```bash
# Повний набір перевірок якості (або `just ci`)
uv run ruff format --check src tests
uv run ruff check src tests
uv run ty check
uv run python -m unittest discover -s tests -v
uv lock --check
```

Pre-commit хуки (`.pre-commit-config.yaml`) та GitHub Actions (`.github/workflows/ci.yml`) автоматично перевіряють форматування, лінтинг (`ruff`), типи (`ty`) та всі тести (`unittest` + `hypothesis`).

---

## Структура проєкту

```text
src/math_books/
├── cli.py                       # Єдиний CLI `math-books`
├── content_bank.py              # Банк сценаріїв + SQLite-індекс пошуку
├── content_review.py            # Науково-педагогічний гейт і CHECK_REGISTRY
├── lessons.py                   # Декларативні тримовні уроки (voiceover / music_only)
├── localized_lesson_scene.py    # Універсальний Manim-рендерер модульних уроків
├── cue_timeline.py              # Таймлайни підказок (word cues / timed cues)
├── visual_blocks/               # Перевикористовувані 9:16 блоки, теми, ui_strings.json
├── music_tracks.py              # Музична база (procedural / AI / import) та music bed
├── tts_engine.py                # Gemini TTS + український fallback + кешування
├── uk_tts_providers.py          # StyleTTS2 -> Piper -> Edge TTS + voice_profiles.toml
├── voiceover_qa.py              # Локальна ASR-перевірка (faster-whisper) та acoustic QA
├── video_builder.py             # Рендер Manim, збірка WAV, ffmpeg mux, verify, frames
├── video_ui.py                  # Базова 9:16 сцена VerticalShortScene та UI-компоненти
├── build_sample_md.py           # Прототип оцифрування книг (mathedu + MinerU -> Markdown)
└── *_scene.py / generate_*      # 7 legacy-сцен про баскетбол і математику

content/
├── bank/                        # Банк ідей і чернеток сценаріїв (*.json)
└── lessons/                     # Декларативні багатомовні уроки (*.json)

content_reviews/                 # Версіоновані досьє наукового й педагогічного рев'ю
assets/
├── music/                       # База фонових треків (manifest.json + CC0 WAV)
└── diagrams/                    # SVG/PNG-схеми для блоку image_stage

.agents/skills/                  # Скіли для агентів (композиція, anti-slop аудит, продакшн)
```

---

## Документація

- [Тримовні декларативні уроки (`uk` / `ru` / `en`)](docs/three-language-videos.md)
- [Процедура наукового та педагогічного рев'ю](docs/scenario-review.md)
- [Наукові припущення та перевірені приклади](docs/content-review.md)
- [Надійність пайплайну та статус артефактів](docs/review-hardening.md)
- [Специфікація модульних блоків і банку сценаріїв](docs/superpowers/specs/2026-11-25-modular-visual-blocks-and-bank-design.md)
- [Архів тестових відео (`test_videos/`)](test_videos/README.md)
