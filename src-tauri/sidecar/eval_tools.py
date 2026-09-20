"""Tool-selection eval: run representative voice commands through the model.

Requires a running llama-server (the app or a manual run).

Usage:
    python src-tauri/sidecar/eval_tools.py
    python src-tauri/sidecar/eval_tools.py --url http://127.0.0.1:58931/v1

Each case expects exactly one tool call. The fast paths (weather/search) are
exercised too: their expected tool is what would actually run.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CASES: list[tuple[str, str]] = [
    # media control vs play music (the classic confusion)
    ("pause the music", "media_control"),
    ("pause", "media_control"),
    ("resume the song", "media_control"),
    ("next song", "media_control"),
    ("previous track", "media_control"),
    ("skip this song", "media_control"),
    ("stop the music", "media_control"),
    ("play Bohemian Rhapsody", "play_music"),
    ("play some lofi beats", "play_music"),
    # apps
    ("open chrome", "open_app"),
    ("launch notepad", "open_app"),
    ("open spotify", "open_app"),
    # system
    ("take a screenshot", "screenshot"),
    ("copy that", "clipboard"),
    ("paste", "clipboard"),
    ("undo", "keyboard_shortcut"),
    ("save the file", "keyboard_shortcut"),
    ("volume up", "volume_control"),
    ("mute", "volume_control"),
    ("brightness down", "brightness_control"),
    ("minimize chrome", "window_control"),
    ("close notepad", "window_control"),
    ("type hello world", "dictate"),
    ("press enter", "press_key"),
    ("lock the pc", "power_control"),
    # memory + info
    ("remember that I like lofi", "remember_fact"),
    ("how is the weather", "weather"),
    ("what's the weather tomorrow", "weather"),
    ("how far is Chandigarh from Delhi", "web_search"),
    ("who won the cricket world cup", "web_search"),
]


def main() -> int:
    from agent import Agent
    from config import SidecarConfig
    from memory import MemoryStore

    ap = argparse.ArgumentParser(description="Tool-selection eval")
    ap.add_argument("--url", default="http://127.0.0.1:58931/v1", help="llama-server base URL")
    ap.add_argument("--model", default="jen-local")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cfg = SidecarConfig()
    cfg.set_ai_mode("local")
    cfg.local_base_url = args.url
    cfg.local_model = args.model

    mem = MemoryStore(":memory:")
    agent = Agent(config=cfg, memory=mem, emit=lambda e: None, dry_run=True)

    passed = 0
    failures: list[tuple[str, str, str]] = []
    for text, expected in CASES:
        mem.clear_history()  # each case is judged on its own, like one command
        try:
            result = agent.process(text)
        except Exception as e:
            failures.append((text, expected, f"error: {e}"))
            print(f"  ERROR  {text!r}: {e}")
            continue
        got = result.tools_run[0] if result.tools_run else (result.spoken or "<text>")
        ok = expected in result.tools_run
        if ok:
            passed += 1
            if args.verbose:
                print(f"  ok     {text!r} -> {result.tools_run}")
        else:
            failures.append((text, expected, str(got)))
            print(f"  FAIL   {text!r}: expected {expected}, got {got!r}")

    total = len(CASES)
    print(f"\ntool selection: {passed}/{total} ({100 * passed // total}%)")
    if failures:
        print("failures:")
        for text, expected, got in failures:
            print(f"  {text!r}: expected {expected}, got {got}")

    mem.close()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
