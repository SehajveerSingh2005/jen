"""Tool registry: every action Jen can take, defined as schema + executor.

Adding a tool = one Tool entry. The LLM sees the schemas; the agent loop
dispatches to the executors. Rules for executors:

  - Signature: fn(ctx: ExecutorContext, **args) -> ToolResult
  - Third-party OS libs (pyautogui, pygetwindow, sbc) are imported LAZILY
    inside the function, after the dry_run check — keeps this module
    importable on CI and in tests.
  - ctx.dry_run means: report what you WOULD do, touch nothing.
  - ctx.emit sends protocol events to the Rust host (e.g. media_control,
    blocked_sensitive, hide) — in dry-run/simulate these are captured.
"""

import json
import logging
import os
import re
import subprocess
import time
import webbrowser
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html import unescape
from typing import Callable

from config import SidecarConfig
from memory import MemoryStore

log = logging.getLogger("jen.tools")


@dataclass
class ToolResult:
    ok: bool
    message: str = ""       # short result / confirmation text
    speak: bool = False     # always speak (answers, errors), even in minimal mode
    needs_llm: bool = False # message is data for the model to summarize, not a spoken line


@dataclass
class ExecutorContext:
    config: SidecarConfig
    memory: MemoryStore | None
    emit: Callable[[dict], None]
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------

_APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "spotify": "spotify",
    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "file explorer": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "command prompt": "cmd",
    "cmd": "cmd",
    "windows settings": "ms-settings:",
    "settings": "ms-settings:",
    "snipping tool": "snippingtool",
    "calculator": "calc",
    "calc": "calc",
    "notepad": "notepad",
    "paint": "mspaint",
}


def _known_app_paths() -> dict[str, list[str]]:
    """Common install locations for apps that are not always registered in
    App Paths (observed: Chrome installed but ShellExecute can't find it)."""
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    return {
        "chrome": [
            os.path.join(pf, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(pf86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(local, r"Google\Chrome\Application\chrome.exe"),
        ],
        "edge": [
            os.path.join(pf86, r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(pf, r"Microsoft\Edge\Application\msedge.exe"),
        ],
        "firefox": [
            os.path.join(pf, r"Mozilla Firefox\firefox.exe"),
            os.path.join(pf86, r"Mozilla Firefox\firefox.exe"),
        ],
        "spotify": [os.path.join(roaming, r"Spotify\Spotify.exe")],
        "code": [
            os.path.join(local, r"Programs\Microsoft VS Code\Code.exe"),
            os.path.join(pf, r"Microsoft VS Code\Code.exe"),
        ],
    }


def _resolve_app_candidates(app: str) -> list[str]:
    """Ordered list of launch targets: verified install paths first, then the
    aliased name, then the raw name."""
    key = _APP_ALIASES.get(app.lower(), app)
    candidates = [p for p in _known_app_paths().get(key, []) if os.path.exists(p)]
    candidates.append(key)
    candidates.append(app)
    return list(dict.fromkeys(candidates))


def _open_app(ctx: ExecutorContext, app: str = "") -> ToolResult:
    app = app.strip()
    if not app:
        return ToolResult(ok=False, message="No app name given.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would open {app}.")

    # os.startfile = ShellExecute: verifiable (raises OSError when it can't
    # resolve) and it doesn't touch the keyboard or steal focus.
    for candidate in _resolve_app_candidates(app):
        try:
            os.startfile(candidate)
            return ToolResult(ok=True, message=f"Opening {app}.")
        except OSError:
            continue

    # Last resort for Store/UWP apps and unusual names: Start menu search
    try:
        import pyautogui

        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.write(app, interval=0.05)
        time.sleep(0.4)
        pyautogui.press("enter")
        return ToolResult(ok=True, message=f"Opening {app}.")
    except Exception as e:
        log.warning("open_app failed for %r: %s", app, e)
        return ToolResult(ok=False, message=f"Couldn't open {app}.", speak=True)


def _google_search(ctx: ExecutorContext, query: str = "") -> ToolResult:
    query = query.strip()
    if not query:
        return ToolResult(ok=False, message="Nothing to search for.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would search Google for {query}.")
    webbrowser.open(f"https://www.google.com/search?q={query}")
    return ToolResult(ok=True, message=f"Searching for {query}.")


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _strip_tags(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


def _fetch_search_results(query: str, limit: int = 5) -> list[dict]:
    """Network seam for web_search — tests monkeypatch this."""
    import httpx

    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": _UA},
        timeout=10,
        follow_redirects=True,
    )
    resp.raise_for_status()
    text = resp.text
    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', text, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', text, re.S)

    results = []
    for i, title in enumerate(titles[:limit]):
        snippet = snippets[i] if i < len(snippets) else ""
        title_clean = _strip_tags(title)
        snippet_clean = _strip_tags(snippet)
        if title_clean or snippet_clean:
            results.append({"title": title_clean, "snippet": snippet_clean})
    return results


def _web_search(ctx: ExecutorContext, query: str = "") -> ToolResult:
    query = query.strip()
    if not query:
        return ToolResult(ok=False, message="Nothing to search for.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would search the web for {query}.")
    try:
        results = _fetch_search_results(query)
    except Exception as e:
        log.warning("web search failed: %s", e)
        return ToolResult(ok=False, message="I couldn't search the web right now.", speak=True)
    if not results:
        return ToolResult(ok=False, message="I couldn't find anything for that.", speak=True)
    lines = [f"- {r['title']}: {r['snippet']}" for r in results]
    return ToolResult(
        ok=True,
        message=f"Web results for {query}:\n" + "\n".join(lines),
        needs_llm=True,
    )


def _play_music(ctx: ExecutorContext, song: str = "") -> ToolResult:
    song = song.strip()
    if not song:
        return ToolResult(ok=False, message="No song given.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would play {song}.")
    search_query = f"site:youtube.com {song} official audio"
    webbrowser.open(f"https://www.google.com/search?q={search_query}&btnI=1&autoplay=1&mute=0")
    return ToolResult(ok=True, message=f"Playing {song}.")


_MEDIA_ACTIONS = ("play", "pause", "next", "prev", "toggle")


def _media_control(ctx: ExecutorContext, action: str = "toggle") -> ToolResult:
    action = action.strip().lower()
    aliases = {"previous": "prev", "skip": "next", "resume": "play", "stop": "pause"}
    action = aliases.get(action, action)
    if action not in _MEDIA_ACTIONS:
        action = "toggle"
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would send media command: {action}.")
    # Actual playback control happens in Rust (Windows GSMTC)
    ctx.emit({"status": "media_control", "command": action})
    return ToolResult(ok=True, message="Done.")


def _volume_control(ctx: ExecutorContext, action: str = "up") -> ToolResult:
    action = action.strip().lower()
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would set volume: {action}.")
    import pyautogui

    if action in ("up", "increase"):
        pyautogui.press("volumeup")
    elif action in ("down", "decrease"):
        pyautogui.press("volumedown")
    else:
        pyautogui.press("volumemute")
    return ToolResult(ok=True, message="Done.")


def _brightness_control(ctx: ExecutorContext, direction: str = "up") -> ToolResult:
    direction = direction.strip().lower()
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would adjust brightness: {direction}.")
    try:
        import screen_brightness_control as sbc
    except ImportError:
        return ToolResult(ok=False, message="Brightness control is not available on this system.", speak=True)
    try:
        current = sbc.get_brightness(display=0)
        if isinstance(current, list):
            current = current[0]
        delta = 10 if direction in ("up", "increase", "brighter") else -10
        sbc.set_brightness(max(0, min(100, current + delta)), display=0)
        return ToolResult(ok=True, message="Done.")
    except Exception as e:
        log.warning("brightness failed: %s", e)
        return ToolResult(ok=False, message="Couldn't adjust brightness.", speak=True)


def _best_title_match(query: str, titles: list[str]) -> tuple[str | None, float]:
    """Match an app name against open window titles (stdlib fuzzy)."""
    query = query.strip().lower()
    if not query:
        return None, 0.0
    best_title, best_score = None, 0.0
    for title in titles:
        t = title.lower()
        score = 0.95 if query in t else SequenceMatcher(None, query, t).ratio()
        if score > best_score:
            best_title, best_score = title, score
    return best_title, best_score


def _window_control(ctx: ExecutorContext, action: str = "focus", app: str = "") -> ToolResult:
    action = action.strip().lower()
    app = (app or "").strip()
    if action not in ("focus", "minimize", "maximize", "close"):
        action = "focus"
    if ctx.dry_run:
        target = f" on {app}" if app else ""
        return ToolResult(ok=True, message=f"Would {action} window{target}.")
    import pyautogui
    import pygetwindow as gw

    target_win = None
    if app:
        windows = [w for w in gw.getWindowsWithTitle("") if w.title.strip() and w.width > 0 and w.height > 0]
        title, score = _best_title_match(app, [w.title for w in windows])
        if title and score > 0.45:
            target_win = next((w for w in windows if w.title == title), None)

    if not target_win:
        ctx.emit({"status": "hide"})
        time.sleep(0.3)
        active = gw.getActiveWindow()
        if active and "jen" not in active.title.lower():
            target_win = active

    if not target_win:
        return ToolResult(ok=False, message="Couldn't find that window.", speak=True)

    if action == "close":
        target_win.close()
    elif action == "minimize":
        target_win.minimize()
    elif action == "maximize":
        if target_win.isMinimized:
            target_win.restore()
        target_win.maximize()
        target_win.activate()
    else:  # focus
        if target_win.isMinimized:
            target_win.restore()
        pyautogui.press("alt")
        target_win.activate()
    return ToolResult(ok=True, message="Done.")


def _screenshot(ctx: ExecutorContext) -> ToolResult:
    if ctx.dry_run:
        return ToolResult(ok=True, message="Would take a screenshot.")
    import pyautogui

    pyautogui.hotkey("win", "prtsc")
    return ToolResult(ok=True, message="Screenshot saved.")


_CLIPBOARD_KEYS = {"copy": ("ctrl", "c"), "paste": ("ctrl", "v"), "cut": ("ctrl", "x")}


def _clipboard(ctx: ExecutorContext, action: str = "copy") -> ToolResult:
    action = action.strip().lower()
    keys = _CLIPBOARD_KEYS.get(action, _CLIPBOARD_KEYS["copy"])
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would {action}.")
    import pyautogui

    pyautogui.hotkey(*keys)
    return ToolResult(ok=True, message="Done.")


_SHORTCUTS: dict[str, tuple[str, ...]] = {
    "undo": ("ctrl", "z"),
    "redo": ("ctrl", "y"),
    "save": ("ctrl", "s"),
    "select all": ("ctrl", "a"),
    "new tab": ("ctrl", "t"),
    "close tab": ("ctrl", "w"),
    "reopen tab": ("ctrl", "shift", "t"),
    "new window": ("ctrl", "n"),
    "close application": ("alt", "f4"),
    "refresh": ("f5",),
    "find": ("ctrl", "f"),
    "zoom in": ("ctrl", "+"),
    "zoom out": ("ctrl", "-"),
    "reset zoom": ("ctrl", "0"),
    "go back": ("alt", "left"),
    "go forward": ("alt", "right"),
    "task manager": ("ctrl", "shift", "esc"),
    "run dialog": ("win", "r"),
    "show desktop": ("win", "d"),
    "settings": ("win", "i"),
    "next tab": ("ctrl", "tab"),
    "previous tab": ("ctrl", "shift", "tab"),
}


def _keyboard_shortcut(ctx: ExecutorContext, shortcut: str = "") -> ToolResult:
    shortcut = " ".join(shortcut.strip().lower().split())
    keys = _SHORTCUTS.get(shortcut)
    if not keys and len(shortcut) >= 3:
        # Tolerate small phrasing differences: containment match in either direction
        for known in _SHORTCUTS:
            if shortcut in known or known in shortcut:
                keys = _SHORTCUTS[known]
                break
    if not keys:
        return ToolResult(ok=False, message=f"I don't know the shortcut '{shortcut}'.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would press {'+'.join(keys)}.")
    import pyautogui

    pyautogui.hotkey(*keys)
    return ToolResult(ok=True, message="Done.")


def _dictate(ctx: ExecutorContext, text: str = "") -> ToolResult:
    text = text.strip()
    if not text:
        return ToolResult(ok=False, message="Nothing to type.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would type: {text[:50]}.")
    import pyautogui

    ctx.emit({"status": "hide"})
    time.sleep(0.15)
    pyautogui.write(text, interval=0.01)
    return ToolResult(ok=True, message="Done.")


_KEY_MAP = {
    "enter": "enter", "space": "space", "tab": "tab", "escape": "escape", "esc": "escape",
    "backspace": "backspace", "delete": "delete",
    "up": "up", "down": "down", "left": "left", "right": "right",
}


def _press_key(ctx: ExecutorContext, key: str = "") -> ToolResult:
    key = key.strip().lower()
    mapped = _KEY_MAP.get(key)
    if not mapped:
        return ToolResult(ok=False, message=f"I can't press '{key}'.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would press {mapped}.")
    import pyautogui

    ctx.emit({"status": "hide"})
    time.sleep(0.15)
    pyautogui.press(mapped)
    return ToolResult(ok=True, message="Done.")


_POWER_COMMANDS: dict[str, list[str]] = {
    "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"],
    "hibernate": ["shutdown.exe", "/h"],
    "restart": ["shutdown.exe", "/r", "/t", "5"],
    "shutdown": ["shutdown.exe", "/s", "/t", "5"],
}


def _power_control(ctx: ExecutorContext, action: str = "lock") -> ToolResult:
    action = action.strip().lower()
    if ctx.config.protect_sensitive:
        ctx.emit({"status": "blocked_sensitive", "intent": "power_control", "text": action})
        return ToolResult(ok=False, message="Power commands are blocked by sensitive protection.")
    cmd = _POWER_COMMANDS.get(action)
    if not cmd:
        return ToolResult(ok=False, message=f"Unknown power action '{action}'.", speak=True)
    if ctx.dry_run:
        return ToolResult(ok=True, message=f"Would run power action: {action}.")
    subprocess.Popen(cmd)
    return ToolResult(ok=True, message="Done.")


_WMO_CONDITIONS = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "light showers",
    81: "showers", 82: "heavy showers", 95: "thunderstorm",
}

_location_cache: dict = {}


def _loc_via_ip_api() -> dict:
    import httpx

    data = httpx.get("http://ip-api.com/json/?fields=lat,lon,city", timeout=8).json()
    return {"lat": data["lat"], "lon": data["lon"], "city": data.get("city", "your area")}


def _loc_via_ipapi_co() -> dict:
    import httpx

    data = httpx.get("https://ipapi.co/json/", timeout=8).json()
    return {"lat": data["latitude"], "lon": data["longitude"], "city": data.get("city", "your area")}


def _fetch_weather_data() -> dict:
    """Network seam for the weather tool — tests monkeypatch this."""
    import httpx

    if not _location_cache:
        last_err: Exception | None = None
        for provider in (_loc_via_ip_api, _loc_via_ipapi_co):
            try:
                _location_cache.update(provider())
                break
            except Exception as e:
                last_err = e
                log.warning("geolocation provider failed: %s", e)
        if not _location_cache:
            raise RuntimeError(f"could not determine location: {last_err}")

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={_location_cache['lat']}&longitude={_location_cache['lon']}"
        "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
        "&temperature_unit=celsius&windspeed_unit=kmh"
    )
    current = None
    for attempt in range(3):
        try:
            current = httpx.get(url, timeout=8).json()["current"]
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.5)
    return {
        "city": _location_cache.get("city", "your area"),
        "temp": round(current["temperature_2m"]),
        "humidity": current["relative_humidity_2m"],
        "wind": round(current["wind_speed_10m"]),
        "condition": _WMO_CONDITIONS.get(current["weather_code"], "unknown"),
    }


def _weather(ctx: ExecutorContext) -> ToolResult:
    if ctx.dry_run:
        return ToolResult(ok=True, message="Would fetch the weather.", speak=True)
    try:
        w = _fetch_weather_data()
    except Exception as e:
        log.warning("weather failed: %s", e)
        return ToolResult(ok=False, message="Sorry, I couldn't get the weather right now.", speak=True)
    msg = (
        f"In {w['city']}, it's {w['temp']} degrees Celsius and {w['condition']}. "
        f"Humidity is {w['humidity']} percent with wind at {w['wind']} kilometers per hour."
    )
    return ToolResult(ok=True, message=msg, speak=True)


def _remember_fact(ctx: ExecutorContext, key: str = "", value: str = "") -> ToolResult:
    if ctx.memory is None:
        return ToolResult(ok=False, message="Memory is not available.", speak=True)
    try:
        norm = ctx.memory.add_fact(key, value)
    except ValueError as e:
        return ToolResult(ok=False, message=str(e), speak=True)
    return ToolResult(ok=True, message=f"Got it, I'll remember your {norm}.")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    executor: Callable[..., ToolResult]


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


def _str(desc: str, enum: list[str] | None = None) -> dict:
    s: dict = {"type": "string", "description": desc}
    if enum:
        s["enum"] = enum
    return s


TOOLS: list[Tool] = [
    Tool(
        name="open_app",
        description="Open or launch an application on the user's Windows PC by name.",
        parameters=_obj({"app": _str("Application name, e.g. 'chrome', 'notepad', 'spotify'")}, ["app"]),
        executor=_open_app,
    ),
    Tool(
        name="google_search",
        description=(
            "Open Google search results in the browser so the USER can read them. "
            "Use only when they want to see results themselves ('google it'). "
            "To answer a question yourself, use web_search."
        ),
        parameters=_obj({"query": _str("The search query")}, ["query"]),
        executor=_google_search,
    ),
    Tool(
        name="web_search",
        description=(
            "Search the web and get results to answer with. Use for weather, news, "
            "places, distances, prices, sports, or any current/factual question you "
            "are not certain about."
        ),
        parameters=_obj({"query": _str("The search query")}, ["query"]),
        executor=_web_search,
    ),
    Tool(
        name="play_music",
        description=(
            "Start playing a specific song, artist, album, or playlist on YouTube. "
            "Use ONLY when the user names what to play (e.g. 'play Bohemian Rhapsody'). "
            "For controlling media that is already playing (pause, resume, skip, stop), "
            "use media_control instead."
        ),
        parameters=_obj({"song": _str("Song / artist / music query to play")}, ["song"]),
        executor=_play_music,
    ),
    Tool(
        name="media_control",
        description=(
            "Pause, resume, stop, or skip (next/previous) the media that is ALREADY "
            "playing (Spotify, YouTube, browser). Use for 'pause', 'pause the music', "
            "'stop the music', 'resume', 'next song', 'previous track', 'skip'. "
            "Do NOT use play_music for these."
        ),
        parameters=_obj({"action": _str("Playback action", list(_MEDIA_ACTIONS))}, ["action"]),
        executor=_media_control,
    ),
    Tool(
        name="volume_control",
        description="Adjust system volume.",
        parameters=_obj({"action": _str("Volume action", ["up", "down", "mute", "unmute"])}, ["action"]),
        executor=_volume_control,
    ),
    Tool(
        name="brightness_control",
        description="Change screen brightness. Use for 'brightness up/down', 'brighter', 'dimmer'.",
        parameters=_obj({"direction": _str("Direction", ["up", "down"])}, ["direction"]),
        executor=_brightness_control,
    ),
    Tool(
        name="window_control",
        description="Focus, minimize, maximize, or close a window, optionally naming the app.",
        parameters=_obj({
            "action": _str("Window action", ["focus", "minimize", "maximize", "close"]),
            "app": _str("Optional app/window name to target; omit for the active window"),
        }, ["action"]),
        executor=_window_control,
    ),
    Tool(
        name="screenshot",
        description="Take a screenshot of the screen.",
        parameters=_obj({}),
        executor=_screenshot,
    ),
    Tool(
        name="clipboard",
        description="Copy, paste, or cut using the clipboard.",
        parameters=_obj({"action": _str("Clipboard action", ["copy", "paste", "cut"])}, ["action"]),
        executor=_clipboard,
    ),
    Tool(
        name="keyboard_shortcut",
        description="Trigger a common keyboard shortcut (undo, save, new tab, refresh, etc.).",
        parameters=_obj({"shortcut": _str("Shortcut name, e.g. 'undo', 'save', 'new tab'")}, ["shortcut"]),
        executor=_keyboard_shortcut,
    ),
    Tool(
        name="dictate",
        description="Type text into the currently focused application.",
        parameters=_obj({"text": _str("The exact text to type")}, ["text"]),
        executor=_dictate,
    ),
    Tool(
        name="press_key",
        description="Press a single key like enter, space, tab, escape, backspace, or an arrow key.",
        parameters=_obj({"key": _str("Key name, e.g. 'enter', 'space', 'up'")}, ["key"]),
        executor=_press_key,
    ),
    Tool(
        name="power_control",
        description="Lock, sleep, hibernate, restart, or shut down the PC. Sensitive: may be blocked by user settings.",
        parameters=_obj({"action": _str("Power action", list(_POWER_COMMANDS.keys()))}, ["action"]),
        executor=_power_control,
    ),
    Tool(
        name="weather",
        description="Get the current weather for the user's location.",
        parameters=_obj({}),
        executor=_weather,
    ),
    Tool(
        name="remember_fact",
        description="Store a durable fact about the user (name, preferences, app aliases, habits) for future conversations.",
        parameters=_obj({
            "key": _str("Short fact label, e.g. 'name', 'favorite editor', 'music taste'"),
            "value": _str("The fact value, e.g. 'Sehaj', 'VS Code', 'lo-fi'"),
        }, ["key", "value"]),
        executor=_remember_fact,
    ),
]

_BY_NAME = {t.name: t for t in TOOLS}


def tool_schemas() -> list[dict]:
    """OpenAI-format tools array for the chat completions API."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS
    ]


def execute(ctx: ExecutorContext, name: str, arguments: dict | None) -> ToolResult:
    """Dispatch a tool call by name. Never raises."""
    tool = _BY_NAME.get(name)
    if tool is None:
        log.warning("unknown tool called: %s", name)
        return ToolResult(ok=False, message=f"I don't know how to '{name}'.", speak=True)

    args = dict(arguments or {})
    allowed = set(tool.parameters.get("properties", {}).keys())
    args = {k: v for k, v in args.items() if k in allowed}

    try:
        return tool.executor(ctx, **args)
    except TypeError as e:
        log.warning("bad args for %s: %s (%s)", name, e, json.dumps(args))
        return ToolResult(ok=False, message=f"Couldn't run {name}: bad arguments.", speak=True)
    except Exception as e:
        log.exception("tool %s failed", name)
        return ToolResult(ok=False, message=f"Something went wrong running {name}.", speak=True)
