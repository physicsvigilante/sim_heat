"""Run from the repo root: python -B -m qualification.h1_n13.heldout.controls"""
from copy import deepcopy
from hashlib import sha256
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from qualification.h1_n13.conduction import prepare
from qualification.h1_n13.heldout.oracle import verify

HERE = Path(__file__).resolve().parent


def digest(raw):
    return sha256(raw).hexdigest()


def refused(label, action, message, error_type=ValueError):
    try:
        action()
    except error_type as error:
        assert message in str(error), (label, type(error).__name__, str(error))
        return {"control": label, "exception": type(error).__name__, "detail": str(error)}
    raise AssertionError("unexpected acceptance: "+label)


def main():
    checks = []
    model = (HERE/"model.mo").read_bytes()
    original = (HERE/"facts.json").read_bytes()
    with TemporaryDirectory() as folder:
        case = Path(folder)
        (case/"model.mo").write_bytes(model)
        study = case/"study.json"
        study.write_bytes((HERE/"study.json").read_bytes())
        facts = case/"facts.json"
        def run(pin):
            return prepare(study, case, facts, pin)
        reversed_endpoints = json.loads(original)
        reversed_endpoints["rods"]["link"].update(a="A", b="B")
        alt = json.dumps(reversed_endpoints).encode()
        facts.write_bytes(alt)
        checks.append(refused("reversed fact endpoints with original pin", lambda:run(digest(original)),
                              "source bytes differ"))
        checks.append(refused("reversed physical edge with fresh pin", lambda:run(digest(alt)),
                              "physical connectivity differs"))
        alt = original.replace(b'"stopTime": 120,', b'"stopTime": 120.000000000000000001,')
        assert alt != original
        facts.write_bytes(alt)
        checks.append(refused("sub-binary64 time drift with fresh pin", lambda:run(digest(alt)),
                              "exact source analysis differs"))
        bad_model = model.replace(b"SimHeat.RodArea feed", b"SimHeat.Radiation feed")
        assert bad_model != model
        (case/"model.mo").write_bytes(bad_model)
        descriptor = json.loads(study.read_bytes())
        descriptor["model"]["sha256"] = digest(bad_model)
        study.write_text(json.dumps(descriptor), encoding="utf8")
        checks.append(refused("unsupported radiation with current model hash", lambda:run(digest(alt)),
                              "unsupported constructor"))
    with gzip.open(HERE/"first-output.json.gz", "rt", encoding="utf8") as source:
        data = json.load(source)
    for name, change in (
        ("one missing rod port series", lambda d: d["exports"].pop("link.port_b.Q_flow")),
        ("one reversed nonzero boundary integral", lambda d: d["integrals"]["bath.Q_to_network"]["values"].__setitem__(100,-d["integrals"]["bath.Q_to_network"]["values"][100])),
        ("one omitted final junction value", lambda d: d["requests"]["joint"]["values"].pop()),
    ):
        damaged = deepcopy(data)
        change(damaged)
        checks.append(refused(name, lambda:verify(damaged), "", AssertionError))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
