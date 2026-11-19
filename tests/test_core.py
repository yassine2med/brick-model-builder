import pytest
from rdflib import Graph, Namespace, RDF

from brick_builder.__main__ import main
from brick_builder.core import ModelError, count_triples, read_entities, to_turtle

HEADER = "id,label,type,part_of,location,feeds,point_of\n"
BRICK = Namespace("https://brickschema.org/schema/Brick#")
BLDG = Namespace("https://example.org/building#")


def sheet(tmp_path, body):
    p = tmp_path / "s.csv"
    p.write_text(HEADER + body)
    return p


def graph_of(tmp_path, body):
    g = Graph()
    g.parse(data=to_turtle(read_entities(sheet(tmp_path, body))), format="turtle")
    return g


def test_class_mapping(tmp_path):
    g = graph_of(tmp_path, "a1,AHU 1,AHU,,,,\n")
    assert (BLDG.a1, RDF.type, BRICK.Air_Handling_Unit) in g


def test_type_is_case_insensitive(tmp_path):
    g = graph_of(tmp_path, "r1,R,  room ,,,,\n")
    assert (BLDG.r1, RDF.type, BRICK.Room) in g


def test_part_of_both_directions(tmp_path):
    g = graph_of(tmp_path, "b,B,Building,,,,\nf,F,Floor,b,,,\n")
    assert (BLDG.f, BRICK.isPartOf, BLDG.b) in g
    assert (BLDG.b, BRICK.hasPart, BLDG.f) in g


def test_feeds_multiple_targets(tmp_path):
    g = graph_of(tmp_path, "a,A,AHU,,,v1;v2,\nv1,V1,VAV,,,,\nv2,V2,VAV,,,,\n")
    assert (BLDG.a, BRICK.feeds, BLDG.v1) in g and (BLDG.v2, BRICK.isFedBy, BLDG.a) in g


def test_point_relationship(tmp_path):
    g = graph_of(tmp_path, "a,A,AHU,,,,\ns,S,Supply Air Temp Sensor,,,,a\n")
    assert (BLDG.a, BRICK.hasPoint, BLDG.s) in g


def test_label_quotes_are_escaped(tmp_path):
    g = graph_of(tmp_path, 'a,"Unit ""1"" east",AHU,,,,\n')
    assert 'Unit "1" east' in {str(o) for o in g.objects(BLDG.a)}


def test_unknown_type_is_reported(tmp_path):
    with pytest.raises(ModelError, match="unknown type"):
        read_entities(sheet(tmp_path, "a,A,Spaceship,,,,\n"))


def test_all_problems_listed_together(tmp_path):
    body = "a,A,AHU,,,ghost,\na,A2,AHU,,,,\n9x,Bad,AHU,,,,\n"
    with pytest.raises(ModelError) as info:
        read_entities(sheet(tmp_path, body))
    text = str(info.value)
    assert "duplicate id a" in text and "unknown id ghost" in text and "bad id" in text


def test_self_reference_rejected(tmp_path):
    with pytest.raises(ModelError, match="itself"):
        read_entities(sheet(tmp_path, "a,A,AHU,,,a,\n"))


def test_example_sheet_parses_and_counts():
    ents = read_entities("examples/building_a.csv")
    assert len(ents) == 16
    assert count_triples(to_turtle(ents)) > 50


def test_cli_success_and_failure(tmp_path, capsys):
    out = tmp_path / "m.ttl"
    assert main(["examples/building_a.csv", "--out", str(out)]) == 0
    assert out.read_text().startswith("@prefix brick:")
    assert main([str(sheet(tmp_path, "a,A,Nope,,,,\n"))]) == 1
    assert "model has problems" in capsys.readouterr().err
