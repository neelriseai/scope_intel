"""JS adapter call-edge extraction (phase5: frontend call graphs).

Dhi's web/app.js indexed as symbols with no callers/callees, so scope
queries could not navigate the frontend. Functions must now carry `calls`
so the resolver builds edges, exactly like the Python adapter.
"""

from pathlib import Path

from scope_intel.adapters.javascript_adapter import JavaScriptAdapter

SAMPLE = """
function speak(text, cues) {
  const voice = chooseVoice();
  pulseBoundary(text);
  if (window.speechSynthesis) {
    window.speechSynthesis.speak(makeUtterance(text));
  }
  for (const c of cues) { console.log(c); }
}

const chooseVoice = () => {
  return pickLocal();
};

function pulseBoundary(word) {
  animateWord(word);
}

class AvatarStage {
  render() {}
}
"""


def test_function_symbols_carry_call_names(tmp_path: Path) -> None:
    parsed = JavaScriptAdapter().parse_file(tmp_path / "app.js", SAMPLE)
    by_name = {s.name: s for s in parsed.symbols}
    assert by_name["speak"].kind == "function"
    assert "chooseVoice" in by_name["speak"].calls
    assert "pulseBoundary" in by_name["speak"].calls
    assert "makeUtterance" in by_name["speak"].calls
    # keywords/builtins are not calls
    assert "if" not in by_name["speak"].calls
    assert "for" not in by_name["speak"].calls
    assert "console" not in by_name["speak"].calls


def test_spans_do_not_leak_calls_into_neighbors(tmp_path: Path) -> None:
    parsed = JavaScriptAdapter().parse_file(tmp_path / "app.js", SAMPLE)
    by_name = {s.name: s for s in parsed.symbols}
    assert by_name["chooseVoice"].calls == ["pickLocal"]
    assert by_name["pulseBoundary"].calls == ["animateWord"]
    # no self-recursion noise, classes carry no calls
    assert "speak" not in by_name["speak"].calls
    assert by_name["AvatarStage"].calls == []
