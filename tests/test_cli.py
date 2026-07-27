import json

from overnight import cli, store


def test_list_json_empty(capsys):
    assert cli.main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_list_json_roundtrip(capsys):
    job = store.add("what is the capital of france")
    cli.main(["list", "--json"])
    jobs = json.loads(capsys.readouterr().out)
    assert len(jobs) == 1
    assert jobs[0]["id"] == job.id
    assert jobs[0]["prompt"] == "what is the capital of france"
