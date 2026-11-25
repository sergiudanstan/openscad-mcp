"""Unit tests for console parsing, literal serialisation and parameter extraction."""

import pytest

from openscad_mcp import diagnostics

# Verbatim OpenSCAD 2021.01 output.
SAMPLE = """\
WARNING: Ignoring unknown module 'foo' in file warn.scad, line 2
WARNING: Ignoring unknown variable 'b' in file warn.scad, line 3
ECHO: a = undef
ERROR: Assertion '(1 == 2)' failed: "bad" in file warn.scad, line 4
TRACE: called by 'assert' in file warn.scad, line 4
Geometries in cache: 1
Total rendering time: 0:00:00.001
   Top level object is a 3D object:
   Facets:          6
"""


class TestParseOutput:
    def test_classifies_lines_with_locations(self):
        d = diagnostics.parse_output(SAMPLE)
        assert [w["line"] for w in d["warnings"]] == [2, 3]
        assert d["errors"][0]["line"] == 4 and d["errors"][0]["file"] == "warn.scad"
        assert d["errors"][0]["trace"] == ["called by 'assert' in file warn.scad, line 4"]
        assert d["echo"] == ["a = undef"]
        assert d["stats"] == {"render_time": "0:00:00.001", "dimension": 3, "facets": 6}

    def test_parser_error(self):
        d = diagnostics.parse_output(
            "ERROR: Parser error: syntax error in file parse.scad, line 2\nCan't parse file 'parse.scad'!\n"
        )
        assert len(d["errors"]) == 2 and d["errors"][0]["line"] == 2

    def test_empty_object_is_a_warning(self):
        d = diagnostics.parse_output("Current top level object is empty.")
        assert d["warnings"] and not d["errors"]

    def test_truncate(self):
        text = "\n".join(f"ECHO: {i}" for i in range(500))
        out = diagnostics.truncate(text, max_lines=10)
        assert out.count("\n") == 10 and out.endswith("[490 more lines truncated]")


class TestLiterals:
    @pytest.mark.parametrize(
        "value, literal",
        [
            (10, "10"),
            (2.5, "2.5"),
            (True, "true"),
            (None, "undef"),
            ("10", "10"),  # backwards compatible: numeric strings pass through
            ("[1, 2]", "[1, 2]"),
            ("hello", '"hello"'),
            ('say "hi"', '"say \\"hi\\""'),
            ([1, "a", [False]], '[1, "a", [false]]'),
        ],
    )
    def test_to_literal(self, value, literal):
        assert diagnostics.to_literal(value) == literal

    def test_rejects_nan_and_bad_names(self):
        with pytest.raises(ValueError):
            diagnostics.to_literal(float("nan"))
        with pytest.raises(ValueError):
            diagnostics.define_args({"a; b": 1})
        assert diagnostics.define_args({"$fn": 64}) == ["-D", "$fn=64"]


SRC = """\
// Box width
width = 40; // [10:5:100]
depth = 20; // Depth in mm
/* [Text] */
label = "A;B"; // label text
show = true;
holes = [3, 5];
derived = width * 2;
/* [Hidden] */
secret = 1;
module part() { inner = 5; cube(width); }
after = 3;
"""


class TestParameters:
    def test_customizer_semantics(self):
        params = {p["name"]: p for p in diagnostics.extract_parameters(SRC)}
        assert list(params) == ["width", "depth", "label", "show", "holes"]
        assert params["width"]["constraint"] == "10:5:100"
        assert params["width"]["description"] == "Box width"
        assert params["depth"]["description"] == "Depth in mm"
        assert params["label"]["value"] == "A;B" and params["label"]["group"] == "Text"
        assert params["show"]["value"] is True
        assert params["holes"]["type"] == "vector"

    def test_nested_assignments_ignored(self):
        params = diagnostics.extract_parameters("if (true) {\n  x = 1;\n}\ny = 2;\n")
        assert [p["name"] for p in params] == ["y"]
