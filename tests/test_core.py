from pathlib import Path
from labvault_scout.hashing import sha256_file
from labvault_scout.risk import classify, load_rules
from labvault_scout.scanner import iter_files

def test_core(tmp_path: Path):
    f=tmp_path/"result.jnb"; f.write_bytes(b"labvault")
    assert list(iter_files(tmp_path)) == [f]
    assert len(sha256_file(f)) == 64
    assert classify(f,load_rules())["risk"] == "RESCUE"

def test_unknown(tmp_path: Path):
    f=tmp_path/"sample.xyzunknown"; f.write_text("x")
    assert classify(f,load_rules())["risk"] == "UNKNOWN"
