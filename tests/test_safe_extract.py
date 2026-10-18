import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import icechart_caching as ic


def _make_zip(path, names):
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            zf.writestr(name, "x")


def test_safe_extractall_blocks_traversal(tmp_path):
    archive = tmp_path / "evil.zip"
    _make_zip(archive, ["../escape.txt"])
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(ValueError):
            ic._safe_extractall(zf, str(dest))
    # the escaping member must not have been written outside the target dir
    assert not (tmp_path / "escape.txt").exists()


def test_safe_extractall_allows_normal_members(tmp_path):
    archive = tmp_path / "ok.zip"
    _make_zip(archive, ["a.txt", "sub/b.txt"])
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(archive) as zf:
        ic._safe_extractall(zf, str(dest))
    assert (dest / "a.txt").read_text() == "x"
    assert (dest / "sub" / "b.txt").read_text() == "x"
