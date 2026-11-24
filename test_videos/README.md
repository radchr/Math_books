# Archived Test Videos (`test_videos/`)

Усі відео та аудіо-артефакти у цій директорії (`test_videos/video_<topic>/`) позначені як **тестові** (згенеровані на етапі прототипування та налагодження пайплайну до `2026-11-24`).

- **`test_videos/video_free_throws/`** — тестовий еталон `free_throws.mp4` (69.6 с) з локальними ASR-квитанціями (`audio/qa/`) та транскриптами.
- **`test_videos/video_hothand/`** — тестовий рендер `hothand_basketball.mp4` (попередня ревізія сценарію).
- **`test_videos/video_moneybart/`** — тестовий рендер `moneybart_basketball.mp4` (до оновлення сценарію).
- **`test_videos/video_simpson/`** — тестовий рендер `simpson_basketball.mp4` (legacy TTS без provenance).
- **`test_videos/video_ahrens/`** — тестовий рендер `ahrens_basketball.mp4` (legacy TTS без provenance).
- **`test_videos/video_basketball/`** — тестовий рендер `basketball_triangles.mp4` (legacy TTS без provenance).

> [!IMPORTANT]
> Усі нові виробничі генерації (`math-books tts`, `math-books build`, `math-books verify`) працюють **з чистого аркуша** і записують артефакти у нову директорію `videos/video_<topic>/`, не змішуючись із цими тестовими файлами.
