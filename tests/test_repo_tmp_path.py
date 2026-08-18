import shutil

from conftest import make_repo_tmp_path, PYTEST_TMP_BASE


def test_make_repo_tmp_path_uses_repo_out_directory():
    path = make_repo_tmp_path("trial")

    try:
        assert path.is_dir()
        assert path.is_relative_to(PYTEST_TMP_BASE)
        assert "pytest-tmp" in path.as_posix()
    finally:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
