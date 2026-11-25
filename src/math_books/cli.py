"""Unified CLI entry point for Math_books."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import httpx

from math_books.build_sample_md import build_markdown, parse_page_spec
from math_books.content_bank import BANK_STATUSES, load_bank_entry, promote_bank_entry, query_bank
from math_books.content_review import check_content_review, make_review_template, require_content_review, review_path
from math_books.languages import SUPPORTED_LANGUAGES
from math_books.music_tracks import (
    MUSIC_BACKENDS,
    PROCEDURAL_PRESETS,
    generate_music_track,
    import_music_track,
    query_music_catalog,
)
from math_books.tts_engine import generate_topic_tts
from math_books.video_builder import (
    available_topics,
    build_video,
    extract_preview_frames,
    get_topic,
    project_root,
    topic_scenes,
    topic_status_summary,
    verify_topic_audio,
    verify_topic_video,
)
from math_books.visual_blocks import visual_block_catalog


def cmd_list(_args: argparse.Namespace) -> int:
    root = project_root()
    for key, topic in available_topics(root, getattr(_args, "lang", "ru")).items():
        summary = topic_status_summary(topic, root)
        state = f"review:{summary['review']} | audio:{summary['audio']} | video:{summary['video']}"
        test_note = f" | archived test: {summary['test_archive']}" if summary["test_archive"] else ""
        print(f"- {key:12s} | {topic.scene_class:22s} | {summary['output']} ({state}){test_note}")
    return 0


def cmd_tts(args: argparse.Namespace) -> int:
    root = project_root()
    language = getattr(args, "lang", "ru")
    topic = get_topic(args.topic, language, root)
    scenes = topic_scenes(topic, root)
    if scenes and scenes[0].get("audio_mode") == "music_only":
        raise ValueError(f"Topic {topic.key!r} uses audio_mode='music_only'; run math-books build directly")
    require_content_review(scenes, topic.video_dir, root, expected_scene_file=topic.scene_file, language=language)
    generate_topic_tts(
        scenes,
        topic.video_dir,
        force=args.force,
        trim_edges=args.trim_edges,
        provider=args.provider or "gemini",
        uk_profile=args.uk_profile,
        language=language,
        voice=args.voice,
        pin_model=topic.lesson_file is not None,
        fallback_to_uk=args.provider is None and language == "uk",
    )
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    root = project_root()
    if args.init and args.topic == "all":
        raise ValueError("Choose one topic with --init")
    language = getattr(args, "lang", "ru")
    targets = (
        available_topics(root, language).values() if args.topic == "all" else [get_topic(args.topic, language, root)]
    )
    all_ok = True
    for topic in targets:
        scenes = topic_scenes(topic, root)
        if args.init:
            dossier = make_review_template(topic.key, scenes, topic.scene_file, root, language=language)
            path = review_path(root, topic.key, language)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as output:
                json.dump(dossier, output, ensure_ascii=False, indent=2)
                output.write("\n")
            print(json.dumps({"topic": topic.key, "created": str(path), "status": "pending", "ok": False}))
        else:
            report = check_content_review(
                scenes, topic.video_dir, root, expected_scene_file=topic.scene_file, language=language
            )
            print(json.dumps(report, ensure_ascii=False))
            all_ok = all_ok and report["ok"]
    return 0 if all_ok else 1


def cmd_verify_audio(args: argparse.Namespace) -> int:
    root = project_root()
    language = getattr(args, "lang", "ru")
    targets = list(available_topics(root, language)) if args.topic == "all" else [args.topic]
    all_ok = True
    for key in targets:
        try:
            report = verify_topic_audio(get_topic(key, language, root), root, refresh=args.refresh)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report = {"topic": key, "ok": False, "issues": [str(error)]}
        print(f"[{key}] {json.dumps(report, ensure_ascii=False)}")
        all_ok = all_ok and report["ok"]
    return 0 if all_ok else 1


def cmd_build(args: argparse.Namespace) -> int:
    report = build_video(args.topic, skip_render=args.skip_render, language=getattr(args, "lang", "ru"))
    return 0 if report["ok"] else 1


def cmd_verify(args: argparse.Namespace) -> int:
    root = project_root()
    language = getattr(args, "lang", "ru")
    targets = list(available_topics(root, language)) if args.topic == "all" else [args.topic]
    all_ok = True
    for key in targets:
        topic = get_topic(key, language, root)
        mp4 = root / topic.video_dir / topic.output_name
        try:
            report = verify_topic_video(topic, root, check_silence=not args.no_silence)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report = {"path": str(mp4), "ok": False, "issues": [str(error)]}
        print(f"[{key}] {json.dumps(report, ensure_ascii=False)}")
        if args.frames and report["ok"]:
            manifest = root / topic.video_dir / "audio" / "manifest.json"
            out_dir = root / topic.video_dir / "preview_frames"
            frames = extract_preview_frames(mp4, manifest, out_dir, scenes=topic_scenes(topic, root))
            print(f"  Extracted {len(frames)} frames -> {out_dir}")
        all_ok = all_ok and report["ok"]
    return 0 if all_ok else 1


def cmd_digitize(args: argparse.Namespace) -> int:
    root = project_root()
    pages = parse_page_spec(args.pages)
    md_path, images = build_markdown(
        html_path=Path(args.html) if args.html else root / "data" / "htmldoc.html",
        mineru_json_path=Path(args.mineru_json)
        if args.mineru_json
        else root / "data" / "mineru_test" / "res7_json.json",
        jpg_dir=Path(args.jpg_dir) if args.jpg_dir else root / "data" / "sample_jpgs",
        out_dir=Path(args.out_dir) if args.out_dir else root / "data" / "sample_md",
        page_numbers=pages,
        output_filename=args.output_name,
        source_page_numbers=parse_page_spec(args.source_pages, preserve_order=True) if args.source_pages else None,
    )
    print(f"Wrote {md_path} ({md_path.stat().st_size} bytes)")
    print("Images:", images)
    return 0


def cmd_bank(args: argparse.Namespace) -> int:
    root = project_root()
    if args.bank_command == "list":
        entries = query_bank(root, status=args.status, domain=args.domain, tag=args.tag, template=args.template)
        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
            return 0
        if not entries:
            print("(no matching bank entries)")
            return 0
        for item in entries:
            tags = ", ".join(item["tags"])
            templates = ", ".join(item["templates"])
            print(
                f"- {item['id']:30s} | {item['status']:8s} | {item['domain']:10s} | "
                f"templates:[{templates}] | tags:[{tags}]"
            )
        return 0
    if args.bank_command == "show":
        entry = load_bank_entry(root, args.id)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    if args.bank_command == "promote":
        result = promote_bank_entry(root, args.id, topic=args.topic)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.bank_command == "catalog":
        print(json.dumps(visual_block_catalog(), ensure_ascii=False, indent=2))
        return 0
    raise ValueError(f"Unknown bank action: {args.bank_command}")


def cmd_music(args: argparse.Namespace) -> int:
    root = project_root()
    if args.music_command == "list":
        tracks = query_music_catalog(root, mood=args.mood, tag=args.tag, source=args.source)
        if args.json:
            print(json.dumps(tracks, ensure_ascii=False, indent=2))
            return 0
        if not tracks:
            print("(no matching music tracks)")
            return 0
        for item in tracks:
            tags = ", ".join(item.get("tags", []))
            print(
                f"- {item['id']:22s} | {item.get('source', '?'):10s} | {item.get('mood', '-'):10s} | "
                f"{item['license']:14s} | tags:[{tags}]"
            )
        return 0
    if args.music_command == "generate":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
        entry = generate_music_track(
            root,
            track_id=args.id,
            backend=args.backend,
            title=args.title,
            prompt=args.prompt,
            preset=args.preset,
            bpm=args.bpm,
            duration_s=args.duration,
            mood=args.mood,
            tags=tags,
            overwrite=args.overwrite,
        )
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    if args.music_command == "import":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
        entry = import_music_track(
            root,
            Path(args.file),
            track_id=args.id,
            title=args.title,
            license_str=args.license,
            author=args.author,
            mood=args.mood,
            bpm=args.bpm,
            tags=tags,
            overwrite=args.overwrite,
        )
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(f"Unknown music action: {args.music_command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="math-books", description="Math_books STEM-Basketball & Digitization CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List registered STEM-Basketball video topics")
    p_list.set_defaults(func=cmd_list)

    p_review = sub.add_parser(
        "review", help="Check mandatory scientific and pedagogical approval of the current script"
    )
    p_review.add_argument("topic")
    p_review.add_argument(
        "--init", action="store_true", help="Create a pending review template; never overwrite or approve"
    )
    p_review.set_defaults(func=cmd_review)

    p_tts = sub.add_parser("tts", help="Generate TTS audio clips and manifest.json (Gemini or Ukrainian fallback)")
    p_tts.add_argument("topic")
    p_tts.add_argument("--force", action="store_true", help="Regenerate existing WAV files")
    p_tts.add_argument("--trim-edges", action="store_true", help="Trim leading/trailing silence (reuses valid audio)")
    p_tts.add_argument(
        "--provider",
        choices=("gemini", "uk"),
        default=None,
        help="TTS backend (default: gemini; auto-falls back to uk chain for Ukrainian if unavailable)",
    )
    p_tts.add_argument("--uk-profile", default=None, help="Profile name in voice_profiles.toml when --provider uk")
    p_tts.add_argument("--voice", default="Puck", help="Gemini voice name")
    p_tts.set_defaults(func=cmd_tts)

    p_build = sub.add_parser("build", help="Render silent Manim video, concat audio, mux, and verify")
    p_build.add_argument("topic")
    p_build.add_argument("--skip-render", action="store_true", help="Reuse existing silent MP4 and only re-mux audio")
    p_build.set_defaults(func=cmd_build)

    p_verify = sub.add_parser("verify", help="Verify video resolution, audio/video sync, and silence gaps")
    p_verify.add_argument("topic", default="all", nargs="?")
    p_verify.add_argument("--no-silence", action="store_true", help="Skip ffmpeg silencedetect check")
    p_verify.add_argument("--frames", action="store_true", help="Extract midpoint preview PNGs per scene")
    p_verify.set_defaults(func=cmd_verify)

    p_vaudio = sub.add_parser("verify-audio", help="Verify synthesized voiceover audio against script via local ASR")
    p_vaudio.add_argument("topic", default="all", nargs="?")
    p_vaudio.add_argument("--refresh", action="store_true", help="Re-run local ASR even if cached receipt exists")
    p_vaudio.set_defaults(func=cmd_verify_audio)

    for command_parser in (p_list, p_review, p_tts, p_build, p_verify, p_vaudio):
        command_parser.add_argument(
            "--lang",
            choices=SUPPORTED_LANGUAGES,
            default="ru",
            help="Lesson language (default: ru; legacy topics remain Russian only)",
        )

    p_dig = sub.add_parser("digitize", help="Merge mathedu HTML with MinerU figure crops into Markdown")
    p_dig.add_argument("--pages", default="13-16", help="Page range/list, e.g. '13-16' or '13,14,16'")
    p_dig.add_argument("--source-pages", help="Original MinerU source pages in page_idx order")
    p_dig.add_argument("--html", default=None, help="Path to mathedu htmldoc.html")
    p_dig.add_argument("--mineru-json", default=None, help="Path to MinerU JSON output")
    p_dig.add_argument("--jpg-dir", default=None, help="Directory with scanned page JPGs")
    p_dig.add_argument("--out-dir", default=None, help="Output directory for Markdown and images")
    p_dig.add_argument("--output-name", default=None, help="Output Markdown filename")
    p_dig.set_defaults(func=cmd_digitize)

    p_bank = sub.add_parser("bank", help="Manage reusable scenario/idea bank and visual block catalog")
    bank_sub = p_bank.add_subparsers(dest="bank_command", required=True)

    p_bank_list = bank_sub.add_parser("list", help="Query bank entries via rebuildable SQLite index")
    p_bank_list.add_argument("--status", choices=BANK_STATUSES, default=None)
    p_bank_list.add_argument("--domain", default=None)
    p_bank_list.add_argument("--tag", default=None)
    p_bank_list.add_argument("--template", default=None)
    p_bank_list.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_bank_list.set_defaults(func=cmd_bank)

    p_bank_show = bank_sub.add_parser("show", help="Display a single bank entry JSON")
    p_bank_show.add_argument("id")
    p_bank_show.set_defaults(func=cmd_bank)

    p_bank_promote = bank_sub.add_parser(
        "promote", help="Export a bank draft to content/lessons/<topic>.json while keeping the bank record"
    )
    p_bank_promote.add_argument("id")
    p_bank_promote.add_argument("--topic", default=None, help="Target lesson topic slug (defaults to draft topic)")
    p_bank_promote.set_defaults(func=cmd_bank)

    p_bank_catalog = bank_sub.add_parser("catalog", help="Print the JSON catalog of all registered visual blocks")
    p_bank_catalog.set_defaults(func=cmd_bank)

    p_music = sub.add_parser("music", help="Manage reusable background music bank (procedural, AI model, or import)")
    music_sub = p_music.add_subparsers(dest="music_command", required=True)

    p_music_list = music_sub.add_parser("list", help="List reusable tracks in assets/music/manifest.json")
    p_music_list.add_argument("--mood", default=None)
    p_music_list.add_argument("--tag", default=None)
    p_music_list.add_argument("--source", default=None)
    p_music_list.add_argument("--json", action="store_true")
    p_music_list.set_defaults(func=cmd_music)

    p_music_gen = music_sub.add_parser("generate", help="Generate a new reusable track via code or AI model")
    p_music_gen.add_argument("--id", required=True, help="Track slug, e.g. live_upbeat_science")
    p_music_gen.add_argument("--backend", choices=MUSIC_BACKENDS, default="musicgen")
    p_music_gen.add_argument("--title", default=None)
    p_music_gen.add_argument("--prompt", default="", help="Style/instrument prompt for ace_step or lyria")
    p_music_gen.add_argument("--preset", choices=PROCEDURAL_PRESETS, default="energetic")
    p_music_gen.add_argument("--bpm", type=float, default=124.0)
    p_music_gen.add_argument("--duration", type=float, default=30.0)
    p_music_gen.add_argument("--mood", default="energetic")
    p_music_gen.add_argument("--tags", default=None, help="Comma-separated tags")
    p_music_gen.add_argument("--overwrite", action="store_true")
    p_music_gen.set_defaults(func=cmd_music)

    p_music_imp = music_sub.add_parser("import", help="Import an external CC0/royalty-free audio file into the bank")
    p_music_imp.add_argument("file", help="Path to local MP3/WAV/OGG/FLAC track")
    p_music_imp.add_argument("--id", required=True)
    p_music_imp.add_argument("--title", required=True)
    p_music_imp.add_argument("--license", required=True)
    p_music_imp.add_argument("--author", required=True)
    p_music_imp.add_argument("--mood", default="energetic")
    p_music_imp.add_argument("--bpm", type=int, default=None)
    p_music_imp.add_argument("--tags", default=None)
    p_music_imp.add_argument("--overwrite", action="store_true")
    p_music_imp.set_defaults(func=cmd_music)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status = args.func(args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, httpx.HTTPError) as error:
        print(f"Error: {error}", file=sys.stderr)
        status = 1
    raise SystemExit(status)


if __name__ == "__main__":
    main()
