from pathlib import Path

from scripts import consistency


def test_dominant_naming_convention_detects_snake_case_majority(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "def do_thing():\n    pass\n\ndef do_other_thing():\n    pass\n",
        encoding="utf-8",
    )
    assert consistency.dominant_naming_convention([f]) == "snake_case"


def test_dominant_naming_convention_unknown_with_no_functions(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("x = 1\n", encoding="utf-8")
    assert consistency.dominant_naming_convention([f]) == "unknown"


def test_nonconforming_names_flags_camelcase_outlier(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "def do_thing():\n    pass\n\ndef doOtherThing():\n    pass\n\ndef do_third_thing():\n    pass\n",
        encoding="utf-8",
    )
    outliers = consistency.nonconforming_names([f])
    assert outliers == ["doOtherThing"]


def test_nonconforming_names_empty_when_convention_unknown(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("x = 1\n", encoding="utf-8")
    assert consistency.nonconforming_names([f]) == []
