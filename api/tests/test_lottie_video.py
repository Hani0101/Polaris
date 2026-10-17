import copy
import json

import pytest

from polaris.animation import ANIMATION_FILE, READY, RUNNING, load_animation, submit_animation
from polaris.lottie_video import LottieVideo, check_lottie_video, check_scene, describe_lottie_video
from polaris.lottie_writer import STARTER_SCENE, SceneStore, lottie_writer_prompt


@pytest.fixture(autouse=True)
def no_render(monkeypatch):
    monkeypatch.setenv("POLARIS_LOTTIE_RENDER", "off")


def video(**changes):
    data = {
        "format": "lottie",
        "title": "A dot crosses a line",
        "description": "A line draws on, then a dot travels along it.",
        "scenes": [
            {"id": "intro", "caption": "A line draws on.", "lottie": copy.deepcopy(STARTER_SCENE)},
            {"id": "move", "caption": "The dot travels.", "lottie": copy.deepcopy(STARTER_SCENE)},
        ],
    }
    data.update(changes)
    return data


def test_starter_scene_passes():
    assert check_scene("s", STARTER_SCENE) == []


def test_video_passes_and_keeps_scenes_as_steps():
    checked = check_lottie_video(video())
    assert checked.errors == []
    assert [step.id for step in checked.video.steps] == ["intro", "move"]


def test_expressions_are_refused():
    lottie = copy.deepcopy(STARTER_SCENE)
    lottie["layers"][0]["ks"]["r"]["x"] = "time * 360"
    errors = check_scene("spin", lottie)
    assert any("expressions are not allowed" in error and "spin" in error for error in errors)


def test_images_and_external_fonts_are_refused():
    lottie = copy.deepcopy(STARTER_SCENE)
    lottie["assets"] = [{"id": "img", "w": 10, "h": 10, "u": "https://example.com/", "p": "a.png"}]
    lottie["fonts"]["list"][0]["fPath"] = "https://example.com/font.woff"
    errors = check_scene("s", lottie)
    assert any("image" in error for error in errors)
    assert any("external files" in error for error in errors)
    assert any("fPath" in error for error in errors)


def test_small_text_and_wrong_canvas_are_refused():
    lottie = copy.deepcopy(STARTER_SCENE)
    lottie["layers"][0]["t"]["d"]["k"][0]["s"]["s"] = 12
    lottie["w"] = 1920
    errors = check_scene("s", lottie)
    assert any("text is at least" in error for error in errors)
    assert any("w and h" in error for error in errors)


def test_scene_length_limits():
    lottie = copy.deepcopy(STARTER_SCENE)
    lottie["op"] = 10
    assert any("lasts" in error for error in check_scene("s", lottie))


def test_duplicate_scene_ids_and_long_captions_are_refused():
    data = video()
    data["scenes"][1]["id"] = "intro"
    data["scenes"][0]["caption"] = "x" * 400
    errors = check_lottie_video(data).errors
    assert any("Two scenes" in error for error in errors)
    assert any("caption" in error for error in errors)


def test_submit_stores_a_lottie_video_and_loads_it(tmp_path):
    attempt = submit_animation(video(), job_id="job-1", work_dir=tmp_path, runs_before=0)
    assert attempt.status == READY
    stored = json.loads((tmp_path / ANIMATION_FILE).read_text(encoding="utf-8"))
    assert stored["format"] == "lottie" and stored["id"] == "job-1"
    loaded = load_animation(tmp_path)
    assert isinstance(loaded, LottieVideo)
    assert "Step 2 ('move'): The dot travels." in describe_lottie_video(loaded)


def test_submit_sends_lottie_errors_back(tmp_path):
    data = video()
    data["scenes"][0]["lottie"]["layers"] = []
    attempt = submit_animation(data, job_id="job-1", work_dir=tmp_path, runs_before=0)
    assert attempt.status == RUNNING
    assert any("intro" in error for error in attempt.errors)
    assert not (tmp_path / ANIMATION_FILE).exists()


def test_scene_store_assembles_in_plan_order(tmp_path):
    store = SceneStore(tmp_path)
    assert store.write("b", "Second.", json.dumps(STARTER_SCENE)) == []
    assert store.write("a", "First.", json.dumps(STARTER_SCENE)) == []
    store.set_plan("T", "D", ["a", "b"])
    data = store.assemble()
    assert [scene["id"] for scene in data["scenes"]] == ["a", "b"]
    assert data["scenes"][0]["caption"] == "First."
    assert check_lottie_video(data).errors == []


def test_scene_store_refuses_bad_ids_and_bad_json(tmp_path):
    store = SceneStore(tmp_path)
    assert store.write("Bad Id", "c", "{}")
    assert any("does not parse" in error for error in store.write("ok", "c", "{nope"))


def test_writer_prompt_carries_the_guides_and_the_starter():
    prompt = lottie_writer_prompt()
    assert "Motion Taste" in prompt
    assert '"nm": "starter"' in prompt
