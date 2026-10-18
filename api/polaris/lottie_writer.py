"""The Lottie animation writer (experiment, branch feat/lottie-experiment).

A Claude agent turns a brief into a Lottie video: a few Lottie scenes that
Polaris plays one after another, each with a caption. The agent has no
built-in tools. It works through an in-process MCP server whose tools keep
the scenes in this job's work folder, check them, and draw frames in
headless Chromium so the agent can look at its own animation and fix it
before it finishes.

The motion and design guidance comes from the text-to-lottie skill
(diffusionstudio/lottie, MIT), copied into ``lottie_guides``.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    ToolUseBlock,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    create_sdk_mcp_server,
    tool,
)

from polaris.login import reject_api_key_credential
from polaris.tool_policy import DISALLOWED_TOOLS
from polaris.lottie_video import (
    BACKGROUND,
    FORMAT,
    HEIGHT,
    MAX_CAPTION_LENGTH,
    MAX_SCENE_SECONDS,
    MAX_SCENES,
    MIN_SCENE_SECONDS,
    MIN_TEXT_SIZE,
    WIDTH,
    check_frames,
    check_lottie_video,
    check_scene,
    render_scenes,
    renderer_available,
)

GUIDES_DIR = Path(__file__).with_name("lottie_guides")
GUIDE_FILES = (
    "lottie-spec-map.md",
    "motion-taste.md",
    "design-taste.md",
    "chapterization-transition-grammar.md",
    "recipe-diagram-technical.md",
    "recipe-data-stats.md",
    "recipe-typography.md",
    "recipe-camera-scene-motion.md",
)

SERVER = "lottie"
TOOL_NAMES = (
    "write_scene",
    "read_scene",
    "edit_scene",
    "delete_scene",
    "preview_scene",
    "set_background",
    "set_video",
    "check_video",
)
SCENE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")

# A known-good lottie-web scene the prompt starts the writer from.
STARTER_SCENE = {
    "v": "5.12.0",
    "fr": 30,
    "ip": 0,
    "op": 120,
    "w": WIDTH,
    "h": HEIGHT,
    "nm": "starter",
    "ddd": 0,
    "assets": [],
    "fonts": {
        "list": [
            {
                "fName": "Next-Bold",
                "fFamily": "Atkinson Hyperlegible Next",
                "fStyle": "Bold",
                "ascent": 75,
            },
            {
                "fName": "Next-Regular",
                "fFamily": "Atkinson Hyperlegible Next",
                "fStyle": "Regular",
                "ascent": 75,
            },
        ]
    },
    "layers": [
        {
            "ddd": 0,
            "ind": 1,
            "ty": 5,
            "nm": "title",
            "sr": 1,
            "ip": 0,
            "op": 120,
            "st": 0,
            "ks": {
                "o": {
                    "a": 1,
                    "k": [
                        {"t": 0, "s": [0], "o": {"x": [0.2], "y": [0.75]}, "i": {"x": [0.34], "y": [0.94]}},
                        {"t": 12, "s": [100]},
                    ],
                },
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [400, 90, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": {"a": 0, "k": [100, 100, 100]},
            },
            "t": {
                "d": {
                    "k": [
                        {
                            "s": {
                                "s": 48,
                                "f": "Next-Bold",
                                "t": "Title text",
                                "j": 2,
                                "tr": 0,
                                "lh": 58,
                                "ls": 0,
                                "fc": [0.047, 0.027, 0.004],
                            },
                            "t": 0,
                        }
                    ]
                },
                "p": {},
                "m": {"g": 1, "a": {"a": 0, "k": [0, 0]}},
                "a": [],
            },
        },
        {
            "ddd": 0,
            "ind": 2,
            "ty": 4,
            "nm": "line draws on",
            "sr": 1,
            "ip": 0,
            "op": 120,
            "st": 0,
            "ks": {
                "o": {"a": 0, "k": 100},
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [0, 0, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": {"a": 0, "k": [100, 100, 100]},
            },
            "shapes": [
                {
                    "ty": "gr",
                    "nm": "line",
                    "it": [
                        {
                            "ty": "sh",
                            "ks": {
                                "a": 0,
                                "k": {
                                    "c": False,
                                    "v": [[160, 400], [640, 400]],
                                    "i": [[0, 0], [0, 0]],
                                    "o": [[0, 0], [0, 0]],
                                },
                            },
                        },
                        {
                            "ty": "st",
                            "c": {"a": 0, "k": [0.047, 0.027, 0.004, 1]},
                            "o": {"a": 0, "k": 100},
                            "w": {"a": 0, "k": 6},
                            "lc": 2,
                            "lj": 2,
                        },
                        {
                            "ty": "tm",
                            "s": {"a": 0, "k": 0},
                            "e": {
                                "a": 1,
                                "k": [
                                    {"t": 10, "s": [0], "o": {"x": [0.2], "y": [0.75]}, "i": {"x": [0.34], "y": [0.94]}},
                                    {"t": 40, "s": [100]},
                                ],
                            },
                            "o": {"a": 0, "k": 0},
                            "m": 1,
                        },
                        {
                            "ty": "tr",
                            "p": {"a": 0, "k": [0, 0]},
                            "a": {"a": 0, "k": [0, 0]},
                            "s": {"a": 0, "k": [100, 100]},
                            "r": {"a": 0, "k": 0},
                            "o": {"a": 0, "k": 100},
                        },
                    ],
                },
                {
                    "ty": "gr",
                    "nm": "dot",
                    "it": [
                        {"ty": "el", "p": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [36, 36]}},
                        {"ty": "fl", "c": {"a": 0, "k": [0.659, 0.306, 0.094, 1]}, "o": {"a": 0, "k": 100}},
                        {
                            "ty": "tr",
                            "p": {
                                "a": 1,
                                "k": [
                                    {"t": 40, "s": [160, 400], "o": {"x": [1], "y": [0.49]}, "i": {"x": [0], "y": [0.55]}},
                                    {"t": 90, "s": [640, 400]},
                                ],
                            },
                            "a": {"a": 0, "k": [0, 0]},
                            "s": {"a": 0, "k": [100, 100]},
                            "r": {"a": 0, "k": 0},
                            "o": {"a": 0, "k": 100},
                        },
                    ],
                },
            ],
        },
    ],
}

PALETTE = """\
- background (Polaris paper): #faf8f4 -> [0.980, 0.973, 0.957]. The player paints it; do not add a full-frame background layer.
- ink (main text and strokes): #0c0701 -> [0.047, 0.027, 0.004]
- secondary text: #4a4038 -> [0.290, 0.251, 0.220]
- quiet lines, grids, axes: #d9d2c6 -> [0.851, 0.824, 0.776]
- soft panel fill: #f2eee6 -> [0.949, 0.933, 0.902]
- accent (the one thing to look at): #a84e18 -> [0.659, 0.306, 0.094]
- info / second series: #2b5a8a -> [0.169, 0.353, 0.541]
- positive: #2f6b3a -> [0.184, 0.420, 0.227]
- negative: #a63a2b -> [0.651, 0.227, 0.169]
- warm highlight fill: #fbf0d9 -> [0.984, 0.941, 0.851]"""


def _guides() -> str:
    parts = []
    for name in GUIDE_FILES:
        path = GUIDES_DIR / name
        if path.is_file():
            parts.append(f"<guide name=\"{name}\">\n{path.read_text(encoding='utf-8')}\n</guide>")
    return "\n\n".join(parts)


def lottie_writer_prompt() -> str:
    return f"""\
You are Polaris's animation director. Polaris is a tutor. You turn a teaching
brief into a short explanatory video made of Lottie scenes, the way a great
explainer channel would: clear, beautiful, calm, and exact.

# What you make

A video is {1}-{MAX_SCENES} scenes played one after another. Each scene is one
Lottie JSON document and one step of the explanation, with a caption the
player shows under the picture (and can read aloud). Usually 3 to 6 scenes.
- Canvas: w {WIDTH}, h {HEIGHT} (4:3). Use fr 30. ip 0. A scene lasts
  {MIN_SCENE_SECONDS:g} to {MAX_SCENE_SECONDS:g} seconds (op = seconds x 30).
- The learner may watch on a phone 320px wide, where the canvas is ~0.32x.
  Text size is at least {MIN_TEXT_SIZE} (prefer 34-44 for labels, 48-60 for
  titles). Keep labels short. Lines are at least 4 wide.
- Keep a 40 unit safe margin on every side at every frame.
- Each scene ends on a settled, readable picture that holds for at least
  0.8 seconds; the player pauses there when the learner pauses, and shows it
  alone when the learner asks for reduced motion.
- Make scenes continue each other: if scene 2 builds on scene 1's picture,
  start scene 2 from the same layout at frame 0 so the cut is invisible, then
  move on. This is the main way to make the whole thing feel like one video.
- The caption is one or two plain sentences (at most {MAX_CAPTION_LENGTH}
  characters) that say what this scene shows and why it matters. Do not put
  the caption text in the picture too; the picture shows labels, values, and
  short titles only.

# Colours and type

Lottie colours are 0..1 floats. Polaris's own palette is a good default
for diagrams, text, and abstract ideas:
{PALETTE}
You are not limited to it. When the subject is better shown in other
colours, use them: real-world colours (blood red and vein blue, leaf green,
a night sky, flame orange), a clear colour per category, or a mood that
fits the story. Choose a few colours that work together, give each idea one
colour and keep it for the whole video, and keep one thing as the focus at
a time.
- The background defaults to Polaris paper. For a different one, call
  set_background(color) with a #rrggbb colour before your first preview; the
  player and the previews paint it. Still no full-frame background layer.
- Text and thin lines need strong contrast with what is behind them, at
  least 4.5:1 (WCAG AA): dark text on a light background, light text on a
  dark one. Check it in every preview.
Fonts: only "Atkinson Hyperlegible Next" (Regular or Bold) and
"Atkinson Hyperlegible Mono" (for code and numbers in tables). Declare each in
fonts.list with fName, fFamily, fStyle, ascent 75, and no fPath. Text layers
reference the fName in "f".

# Lottie rules for Polaris's renderer (lottie-web, SVG renderer)

- No expressions (no string "x" on properties). Bake all motion into keyframes.
- No image layers, image assets, or external files. Draw everything with shape
  layers (ty 4), text layers (ty 5), null layers (ty 3) for rigs, and precomps
  (ty 0 with assets that have "layers") when useful.
- Text: a ty 5 layer with t.d.k[0].s = {{s: size, f: fName, t: text, j: 0 left /
  1 right / 2 centre, tr: 0, lh: line height, fc: [r,g,b]}}. The layer position
  is the text baseline origin. Use "\\r" for a new line. Text animators
  (t.a) are fragile in lottie-web; animate the layer transform instead.
- For maths, write it as plain text with Unicode (x², √, π, θ, Σ, →, ≤, ·).
- Masks and track mattes work, but prefer trim paths and transforms.
- Every shape group needs a fill or stroke after its shapes and its "tr"
  transform last.
- Layer order: the first layer in "layers" is drawn on top.

Here is a scene that renders correctly in Polaris. Start from its structure:
{json.dumps(STARTER_SCENE)}

# How you work (tools)

1. Plan first, briefly, in text: the idea of each scene, its final picture,
   how each scene hands over to the next, and the colours and background
   that suit this subject. Call set_background now if it is not paper.
2. write_scene(id, caption, lottie) for each scene. lottie is the whole
   Lottie document as a JSON string. Fix any errors it returns.
3. preview_scene(id) draws frames across the scene in the real renderer and
   shows them to you. ALWAYS preview every scene. Look hard: overlaps, text
   cut off or too close to edges, things off-canvas, empty frames, motion
   that does not read, ugly spacing, weak final picture. Then fix with
   edit_scene (exact text replace in the scene's JSON) or write_scene, and
   preview again. Two or three rounds per scene is normal.
4. set_video(title, description, scene_ids) with the scenes in order. The
   description is two or three plain sentences for someone who cannot see it.
5. check_video() runs the final check. When it says the video is ready, stop
   and reply with one short line.

Be ambitious about craft (choreography, easing, staggered reveals, trim-path
draw-ons, continuity between scenes) but never at the cost of clarity. Teach
exactly what the brief asks, and nothing it does not.

# Guides

The guides below are about motion and design taste and Lottie structure.
They were written for a different player: ignore what they say about Skottie,
the dev server, scene folders, slots, controls.json, font files, background
layers, and transparent backgrounds. Polaris's rules above win.

{_guides()}
"""


class LottieWriterFailed(RuntimeError):
    """The writer finished without a video that passes the check."""


class SceneStore:
    """The writer's scenes and video plan, kept as files in one work folder."""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.scenes_dir = work_dir / "scenes"
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir = work_dir / "previews"
        self.plan_path = work_dir / "video.json"
        self.background_path = work_dir / "background.txt"

    @property
    def background(self) -> str:
        """The background the writer chose, or Polaris paper."""

        if self.background_path.is_file():
            chosen = self.background_path.read_text(encoding="utf-8").strip()
            if HEX_COLOUR.match(chosen):
                return chosen
        return BACKGROUND

    def set_background(self, colour: str) -> bool:
        if not HEX_COLOUR.match(colour):
            return False
        self.background_path.write_text(colour.lower(), encoding="utf-8")
        return True

    def _scene_path(self, scene_id: str) -> Path:
        return self.scenes_dir / f"{scene_id}.json"

    def _captions(self) -> dict[str, str]:
        path = self.scenes_dir / "captions.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _save_captions(self, captions: dict[str, str]) -> None:
        (self.scenes_dir / "captions.json").write_text(json.dumps(captions), encoding="utf-8")

    def scene_ids(self) -> list[str]:
        return sorted(path.stem for path in self.scenes_dir.glob("*.json") if path.stem != "captions")

    def read_text(self, scene_id: str) -> str | None:
        path = self._scene_path(scene_id)
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def write(self, scene_id: str, caption: str | None, text: str) -> list[str]:
        if not SCENE_ID.match(scene_id):
            return ["A scene id is lowercase letters, digits, and dashes, at most 41 characters."]
        try:
            lottie = json.loads(text)
        except json.JSONDecodeError as error:
            return [f"The Lottie JSON does not parse: {error}"]
        self._scene_path(scene_id).write_text(text, encoding="utf-8")
        if caption is not None:
            captions = self._captions()
            captions[scene_id] = caption.strip()
            self._save_captions(captions)
        return check_scene(scene_id, lottie)

    def delete(self, scene_id: str) -> bool:
        path = self._scene_path(scene_id)
        if not path.is_file():
            return False
        path.unlink()
        captions = self._captions()
        captions.pop(scene_id, None)
        self._save_captions(captions)
        return True

    def caption(self, scene_id: str) -> str | None:
        return self._captions().get(scene_id)

    def set_plan(self, title: str, description: str, scene_ids: list[str]) -> None:
        self.plan_path.write_text(
            json.dumps({"title": title, "description": description, "scene_ids": scene_ids}),
            encoding="utf-8",
        )

    def assemble(self) -> dict[str, Any]:
        """The video data from the plan and the stored scenes."""

        if not self.plan_path.is_file():
            raise LottieWriterFailed("set_video was never called.")
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        scenes = []
        for scene_id in plan["scene_ids"]:
            text = self.read_text(scene_id)
            scenes.append(
                {
                    "id": scene_id,
                    "caption": self.caption(scene_id) or "",
                    "lottie": json.loads(text) if text is not None else None,
                }
            )
        return {
            "format": FORMAT,
            "version": 1,
            "title": plan["title"],
            "description": plan["description"],
            "background": self.background,
            "scenes": scenes,
        }


def _text(message: str, *, error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": message}]}
    if error:
        result["is_error"] = True
    return result


def build_tools(store: SceneStore) -> list[Any]:
    @tool(
        "write_scene",
        "Create or replace a scene. lottie is the whole Lottie document as a JSON string.",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "lowercase-dashed id, e.g. 'intro'"},
                "caption": {"type": "string"},
                "lottie": {"type": "string", "description": "Lottie JSON document"},
            },
            "required": ["id", "caption", "lottie"],
        },
    )
    async def write_scene(args: dict[str, Any]) -> dict[str, Any]:
        errors = store.write(str(args["id"]), str(args["caption"]), str(args["lottie"]))
        if errors:
            return _text("Saved, but fix these:\n- " + "\n- ".join(errors), error=True)
        return _text(f"Saved scene '{args['id']}'. Now preview it.")

    @tool("read_scene", "Read a scene's Lottie JSON and caption.", {"id": str})
    async def read_scene(args: dict[str, Any]) -> dict[str, Any]:
        text = store.read_text(str(args["id"]))
        if text is None:
            return _text(f"No scene '{args['id']}'. Scenes: {store.scene_ids()}", error=True)
        return _text(f"caption: {store.caption(str(args['id']))}\nlottie:\n{text}")

    @tool(
        "edit_scene",
        "Replace exact text in a scene's Lottie JSON (like a find-and-replace), "
        "and/or change its caption. old_text must appear exactly once unless replace_all.",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
                "replace_all": {"type": "boolean"},
                "caption": {"type": "string"},
            },
            "required": ["id"],
        },
    )
    async def edit_scene(args: dict[str, Any]) -> dict[str, Any]:
        scene_id = str(args["id"])
        text = store.read_text(scene_id)
        if text is None:
            return _text(f"No scene '{scene_id}'. Scenes: {store.scene_ids()}", error=True)
        old = args.get("old_text")
        if old:
            count = text.count(old)
            if count == 0:
                return _text("old_text was not found. read_scene to see the exact text.", error=True)
            if count > 1 and not args.get("replace_all"):
                return _text(
                    f"old_text appears {count} times. Add context or set replace_all.", error=True
                )
            text = text.replace(old, str(args.get("new_text", "")))
        caption = args.get("caption")
        errors = store.write(scene_id, str(caption) if caption else None, text)
        if errors:
            return _text("Edited, but fix these:\n- " + "\n- ".join(errors), error=True)
        return _text(f"Edited scene '{scene_id}'. Preview it again.")

    @tool("delete_scene", "Delete a scene.", {"id": str})
    async def delete_scene(args: dict[str, Any]) -> dict[str, Any]:
        if store.delete(str(args["id"])):
            return _text(f"Deleted '{args['id']}'.")
        return _text(f"No scene '{args['id']}'.", error=True)

    @tool(
        "preview_scene",
        "Draw frames of a scene in Polaris's renderer and look at them. "
        "Frames default to six spread across the scene; pass frames to pick exact ones.",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "frames": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["id"],
        },
    )
    async def preview_scene(args: dict[str, Any]) -> dict[str, Any]:
        scene_id = str(args["id"])
        text = store.read_text(scene_id)
        if text is None:
            return _text(f"No scene '{scene_id}'. Scenes: {store.scene_ids()}", error=True)
        lottie = json.loads(text)
        frames = [int(frame) for frame in args.get("frames") or []][:9] or check_frames(lottie)
        if not renderer_available():
            return _text("The renderer is not available. Check the JSON carefully instead.")
        try:
            import asyncio

            rendered = await asyncio.to_thread(
                render_scenes,
                [(scene_id, lottie, frames)],
                out_dir=store.previews_dir,
                background=store.background,
                cell_width=400,
            )
        except Exception as error:  # noqa: BLE001 - report any renderer failure to the writer
            return _text(f"The renderer failed: {error}", error=True)
        scene = rendered[0]
        notes = [f"Scene '{scene_id}', frames {frames} (labels under each cell)."]
        if scene.errors:
            notes.append("lottie-web errors:\n- " + "\n- ".join(scene.errors[:5]))
        blank = [frame for frame, ink in scene.ink if ink < 0.004]
        if blank:
            notes.append(f"These frames look blank: {blank}.")
        content: list[dict[str, Any]] = [{"type": "text", "text": "\n".join(notes)}]
        if scene.sheet.is_file():
            content.append(
                {
                    "type": "image",
                    "data": base64.b64encode(scene.sheet.read_bytes()).decode("ascii"),
                    "mimeType": "image/png",
                }
            )
        return {"content": content}

    @tool(
        "set_background",
        "Set the colour the player paints behind every scene, as #rrggbb. "
        "Defaults to Polaris paper. Previews use it too.",
        {"color": str},
    )
    async def set_background(args: dict[str, Any]) -> dict[str, Any]:
        colour = str(args.get("color", "")).strip()
        if not store.set_background(colour):
            return _text(f"'{colour}' is not a #rrggbb colour.", error=True)
        return _text(f"Background set to {colour}. Check text contrast in the next preview.")

    @tool(
        "set_video",
        "Set the title, the description, and the scene ids in playing order.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "scene_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "description", "scene_ids"],
        },
    )
    async def set_video(args: dict[str, Any]) -> dict[str, Any]:
        ids = [str(item) for item in args["scene_ids"]]
        missing = [scene_id for scene_id in ids if store.read_text(scene_id) is None]
        if missing:
            return _text(f"No scenes named {missing}. Scenes: {store.scene_ids()}", error=True)
        store.set_plan(str(args["title"]), str(args["description"]), ids)
        return _text("Video plan saved. Run check_video.")

    @tool("check_video", "Run Polaris's final check on the whole video.", {})
    async def check_video(_args: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        try:
            data = store.assemble()
        except LottieWriterFailed as error:
            return _text(str(error), error=True)
        checked = await asyncio.to_thread(check_lottie_video, data)
        if checked.errors:
            return _text("Not ready:\n- " + "\n- ".join(checked.errors[:20]), error=True)
        return _text("The video is ready. Stop now.")

    return [
        write_scene,
        read_scene,
        edit_scene,
        delete_scene,
        preview_scene,
        set_background,
        set_video,
        check_video,
    ]


def lottie_writer_options(store: SceneStore) -> ClaudeAgentOptions:
    server = create_sdk_mcp_server(name=SERVER, tools=build_tools(store))
    model = os.environ.get("POLARIS_ANIMATION_MODEL") or None
    # The prompt is too long for a Windows command line, so it goes in a file.
    prompt_file = store.work_dir / "system-prompt.md"
    prompt_file.write_text(lottie_writer_prompt(), encoding="utf-8")
    return ClaudeAgentOptions(
        system_prompt={"type": "file", "path": str(prompt_file)},
        tools=[],
        skills=[],
        setting_sources=[],
        mcp_servers={SERVER: server},
        strict_mcp_config=True,
        allowed_tools=[f"mcp__{SERVER}__{name}" for name in TOOL_NAMES],
        disallowed_tools=DISALLOWED_TOOLS,
        permission_mode="dontAsk",
        max_turns=int(os.environ.get("POLARIS_ANIMATION_MAX_TURNS", "80")),
        model=model,
        cwd=store.work_dir,
        verbatim_prompts=True,
    )


def lottie_writer_prompt_for(
    brief: str, *, errors: list[str] | None, existing: list[str]
) -> str:
    lines = ["Brief:", brief.strip()]
    if errors is not None:
        lines += [
            "",
            "Polaris's final check refused your last video. Your scenes are still "
            f"saved ({', '.join(existing) or 'none'}). Fix every error, preview "
            "what you changed, then set_video and check_video again.",
            "",
            "Errors:",
            *[f"- {error}" for error in errors],
        ]
    return "\n".join(lines)


def _log_message(log: Any, message: object) -> None:
    """A short line per assistant text, tool call, and result, for debugging a job."""

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                log.write(f"text: {block.text.strip()[:2000]}\n")
            elif isinstance(block, ToolUseBlock):
                summary = {key: str(value)[:120] for key, value in block.input.items()}
                log.write(f"tool: {block.name} {summary}\n")
    elif isinstance(message, ResultMessage):
        log.write(
            f"result: {message.subtype} turns={message.num_turns} "
            f"cost={message.total_cost_usd} ms={message.duration_ms}\n"
        )
    log.flush()


class LottieAnimationWriter:
    """Writes a Lottie video with an agent that can see its own frames."""

    def __init__(self, work_root: Path) -> None:
        self.work_root = work_root.resolve()
        self.work_root.mkdir(parents=True, exist_ok=True)

    async def write(
        self,
        brief: str,
        *,
        failed_data: dict[str, Any] | None,
        errors: list[str] | None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        folder = job_id or f"brief-{abs(hash(brief)) % 10**10}"
        store = SceneStore(self.work_root / folder)
        options = lottie_writer_options(store)
        prompt = lottie_writer_prompt_for(brief, errors=errors, existing=store.scene_ids())
        log = (store.work_dir / "transcript.log").open("a", encoding="utf-8")
        log.write(f"--- run (fix: {errors is not None})\n")
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                _log_message(log, message)
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    source = message.data.get("apiKeySource")
                    if isinstance(source, str) and source:
                        reject_api_key_credential(source)
                if isinstance(message, ResultMessage) and message.subtype != "success":
                    # Out of turns or an error: hand back whatever is saved.
                    break
        log.close()
        try:
            return store.assemble()
        except (LottieWriterFailed, ValueError, OSError) as error:
            raise LottieWriterFailed(str(error)) from error
