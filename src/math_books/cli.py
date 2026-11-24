"""Unified CLI entry point for Math_books."""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

import httpx

from math_books.build_sample_md import build_markdown, parse_page_spec
from math_books.content_review import check_content_review, make_review_template, require_content_review
from math_books.tts_engine import generate_topic_tts
from math_books.video_builder import (
    VIDEO_TOPICS,
    build_video,
    extract_preview_frames,
    project_root,
    topic_status_summary,
    verify_topic_audio,
    verify_topic_video,
)


def cmd_list(_args: argparse.Namespace) -> int:
    root = project_root()
    for key, topic in VIDEO_TOPICS.items():
        summary = topic_status_summary(topic, root)
        state = f"review:{summary['review']} | audio:{summary['audio']} | video:{summary['video']}"
        test_note = f" | archived test: {summary['test_archive']}" if summary["test_archive"] else ""
        print(f"- {key:12s} | {topic.scene_class:22s} | {summary['output']} ({state}){test_note}")
    return 0


def cmd_tts(args: argparse.Namespace) -> int:
    if args.topic not in VIDEO_TOPICS:
        print(f"Unknown topic '{args.topic}'. Available: {', '.join(VIDEO_TOPICS)}", file=sys.stderr)
        return 2
    topic = VIDEO_TOPICS[args.topic]
    mod = importlib.import_module(topic.tts_module)
    require_content_review(mod.SCENES, topic.video_dir, project_root(), expected_scene_file=topic.scene_file)
    generate_topic_tts(
        mod.SCENES,
        topic.video_dir,
        force=args.force,
        trim_edges=args.trim_edges,
        provider=args.provider,
        uk_profile=args.uk_profile,
    )
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    root = project_root()
    if args.init and args.topic == "all":
        raise ValueError("Choose one topic with --init")
    targets = VIDEO_TOPICS.values() if args.topic == "all" else [VIDEO_TOPICS[args.topic]]
    all_ok = True
    for topic in targets:
        scenes = importlib.import_module(topic.tts_module).SCENES
        if args.init:
            dossier = make_review_template(topic.key, scenes, topic.scene_file, root)
            path = root / "content_reviews" / f"{topic.key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as output:
                json.dump(dossier, output, ensure_ascii=False, indent=2)
                output.write("\n")
            print(json.dumps({"topic": topic.key, "created": str(path), "status": "pending", "ok": False}))
        else:
            report = check_content_review(scenes, topic.video_dir, root, expected_scene_file=topic.scene_file)
            print(json.dumps(report, ensure_ascii=False))
            all_ok = all_ok and report["ok"]
    return 0 if all_ok else 1


def cmd_verify_audio(args: argparse.Namespace) -> int:
    root = project_root()
    targets = list(VIDEO_TOPICS.keys()) if args.topic == "all" else [args.topic]
    all_ok = True
    for key in targets:
        if key not in VIDEO_TOPICS:
            print(f"Unknown topic '{key}'.", file=sys.stderr)
            return 2
        report = verify_topic_audio(VIDEO_TOPICS[key], root, refresh=args.refresh)
        print(f"[{key}] {json.dumps(report, ensure_ascii=False)}")
        all_ok = all_ok and report["ok"]
    return 0 if all_ok else 1


def cmd_build(args: argparse.Namespace) -> int:
    report = build_video(args.topic, skip_render=args.skip_render)
    return 0 if report["ok"] else 1


def cmd_verify(args: argparse.Namespace) -> int:
    root = project_root()
    targets = list(VIDEO_TOPICS.keys()) if args.topic == "all" else [args.topic]
    all_ok = True
    for key in targets:
        if key not in VIDEO_TOPICS:
            print(f"Unknown topic '{key}'.", file=sys.stderr)
            return 2
        topic = VIDEO_TOPICS[key]
        mp4 = root / topic.video_dir / topic.output_name
        try:
            report = verify_topic_video(topic, root, check_silence=not args.no_silence)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            report = {"path": str(mp4), "ok": False, "issues": [str(error)]}
        print(f"[{key}] {json.dumps(report, ensure_ascii=False)}")
        if args.frames and report["ok"]:
            manifest = root / topic.video_dir / "audio" / "manifest.json"
            out_dir = root / topic.video_dir / "preview_frames"
            frames = extract_preview_frames(mp4, manifest, out_dir)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="math-books", description="Math_books STEM-Basketball & Digitization CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List registered STEM-Basketball video topics")
    p_list.set_defaults(func=cmd_list)

    p_review = sub.add_parser(
        "review", help="Check mandatory scientific and pedagogical approval of the current script"
    )
    p_review.add_argument("topic", choices=["all", *sorted(VIDEO_TOPICS)])
    p_review.add_argument(
        "--init", action="store_true", help="Create a pending review template; never overwrite or approve"
    )
    p_review.set_defaults(func=cmd_review)

    p_tts = sub.add_parser("tts", help="Generate TTS audio clips and manifest.json (Gemini or Ukrainian fallback)")
    p_tts.add_argument("topic", choices=sorted(VIDEO_TOPICS.keys()))
    p_tts.add_argument("--force", action="store_true", help="Regenerate existing WAV files")
    p_tts.add_argument("--trim-edges", action="store_true", help="Trim leading/trailing silence (reuses valid audio)")
    p_tts.add_argument(
        "--provider",
        choices=("gemini", "uk"),
        default="gemini",
        help="TTS backend: 'gemini' (default) or 'uk' (StyleTTS2 -> Piper -> Edge TTS)",
    )
    p_tts.add_argument("--uk-profile", default=None, help="Profile name in voice_profiles.toml when --provider uk")
    p_tts.set_defaults(func=cmd_tts)

    p_build = sub.add_parser("build", help="Render silent Manim video, concat audio, mux, and verify")
    p_build.add_argument("topic", choices=sorted(VIDEO_TOPICS.keys()))
    p_build.add_argument("--skip-render", action="store_true", help="Reuse existing silent MP4 and only re-mux audio")
    p_build.set_defaults(func=cmd_build)

    p_verify = sub.add_parser("verify", help="Verify video resolution, audio/video sync, and silence gaps")
    p_verify.add_argument("topic", choices=["all", *sorted(VIDEO_TOPICS.keys())], default="all", nargs="?")
    p_verify.add_argument("--no-silence", action="store_true", help="Skip ffmpeg silencedetect check")
    p_verify.add_argument("--frames", action="store_true", help="Extract midpoint preview PNGs per scene")
    p_verify.set_defaults(func=cmd_verify)

    p_vaudio = sub.add_parser("verify-audio", help="Verify synthesized voiceover audio against script via local ASR")
    p_vaudio.add_argument("topic", choices=["all", *sorted(VIDEO_TOPICS.keys())], default="all", nargs="?")
    p_vaudio.add_argument("--refresh", action="store_true", help="Re-run local ASR even if cached receipt exists")
    p_vaudio.set_defaults(func=cmd_verify_audio)

    p_dig = sub.add_parser("digitize", help="Merge mathedu HTML with MinerU figure crops into Markdown")
    p_dig.add_argument("--pages", default="13-16", help="Page range/list, e.g. '13-16' or '13,14,16'")
    p_dig.add_argument("--source-pages", help="Original MinerU source pages in page_idx order")
    p_dig.add_argument("--html", default=None, help="Path to mathedu htmldoc.html")
    p_dig.add_argument("--mineru-json", default=None, help="Path to MinerU JSON output")
    p_dig.add_argument("--jpg-dir", default=None, help="Directory with scanned page JPGs")
    p_dig.add_argument("--out-dir", default=None, help="Output directory for Markdown and images")
    p_dig.add_argument("--output-name", default=None, help="Output Markdown filename")
    p_dig.set_defaults(func=cmd_digitize)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status = args.func(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, httpx.HTTPError) as error:
        print(f"Error: {error}", file=sys.stderr)
        status = 1
    raise SystemExit(status)


if __name__ == "__main__":
    main()
