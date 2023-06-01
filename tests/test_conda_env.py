import io
import os
import pathlib
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union, Sequence
from unittest.mock import mock_open, patch


from types import ModuleType, TracebackType

import pytest
import tox
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from ruamel.yaml import YAML
from tox.pytest import CaptureFixture, ToxProject, ToxProjectCreator
from tox_conda.plugin import CondaEnvRunner

import tox.run
from tox.config.sets import EnvConfigSet
from tox.execute.api import Execute, ExecuteInstance, ExecuteOptions, ExecuteStatus, Outcome
from tox.execute.request import ExecuteRequest, shell_cmd
from tox.execute.stream import SyncWrite
from tox.plugin import manager
from tox.report import LOGGER, OutErr
from tox.run import run as tox_run
from tox.run import setup_state as previous_setup_state
from tox.session.cmd.run.parallel import ENV_VAR_KEY
from tox.session.state import State
from tox.tox_env import api as tox_env_api
from tox.tox_env.api import ToxEnv

# from tox_conda.plugin import tox_testenv_create, tox_testenv_install_deps

# pytest_plugins = "tox.pytest"


@pytest.fixture(name="tox_project")
def init_fixture(
    tmp_path: Path,
    capfd: CaptureFixture,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> ToxProjectCreator:
    def _init(
        files: Dict[str, Any], base: Optional[Path] = None, prj_path: Optional[Path] = None
    ) -> ToxProject:
        """create tox  projects"""
        return ToxProject(files, base, prj_path or tmp_path / "p", capfd, monkeypatch, mocker)

    return _init

# class MockExecute(Execute):
#     def __init__(self, colored: bool, exit_code: int) -> None:
#         self.exit_code = exit_code
#         super().__init__(colored)

#     def build_instance(
#         self,
#         request: ExecuteRequest,
#         options: ExecuteOptions,
#         out: SyncWrite,
#         err: SyncWrite,
#     ) -> ExecuteInstance:
#         return MockExecuteInstance(request, options, out, err, self.exit_code)


@pytest.fixture
def mock_conda_env_runner(request, monkeypatch):
    class MockExecuteStatus(ExecuteStatus):
        def __init__(self, options: ExecuteOptions, out: SyncWrite, err: SyncWrite, exit_code: int) -> None:
            super().__init__(options, out, err)
            self._exit_code = exit_code

        @property
        def exit_code(self) -> Optional[int]:
            return self._exit_code

        def wait(self, timeout: Optional[float] = None) -> Optional[int]:  # noqa: U100
            return self._exit_code

        def write_stdin(self, content: str) -> None:  # noqa: U100
            return None  # pragma: no cover

        def interrupt(self) -> None:
            return None  # pragma: no cover

    class MockExecuteInstance(ExecuteInstance):
        def __init__(
            self,
            request: ExecuteRequest,
            options: ExecuteOptions,
            out: SyncWrite,
            err: SyncWrite,
            exit_code: int,
        ) -> None:
            super().__init__(request, options, out, err)
            self.exit_code = exit_code

        def __enter__(self) -> ExecuteStatus:
            return MockExecuteStatus(self.options, self._out, self._err, self.exit_code)

        def __exit__(
            self,
            exc_type: Optional[BaseException],  # noqa: U100
            exc_val: Optional[BaseException],  # noqa: U100
            exc_tb: Optional[TracebackType],  # noqa: U100
        ) -> None:
            pass

        @property
        def cmd(self) -> Sequence[str]:
            return self.request.cmd
    

    shell_cmds = []
    mocked_run_ids = request.param
    original_execute_instance_factor = CondaEnvRunner._execute_instance_factory

    def mock_execute_instance_factory(request: ExecuteRequest,
                                    options: ExecuteOptions,
                                    out: SyncWrite,
                                    err: SyncWrite):
        shell_cmds.append(request.cmd)

        if request.run_id in mocked_run_ids:
            return MockExecuteInstance(request, options, out, err, 0)
        else:
            return original_execute_instance_factor(request, options, out, err)
        
    # CondaEnvRunner._execute_instance_factory = mock_execute_instance_factory

    monkeypatch.setattr(CondaEnvRunner, "_execute_instance_factory", mock_execute_instance_factory)

    yield shell_cmds

@pytest.mark.parametrize('mock_conda_env_runner', [["create_python_env-create", "create_python_env-install", "install_package"]], indirect=True)
def test_conda_create(tox_project, monkeypatch, mock_conda_env_runner):
    ini = "[testenv:py123]"
    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")
    executed_shell_commands = mock_conda_env_runner
    outcome.assert_success()

    # ini = "[testenv:py123]"
    # tox_proj = tox_project({"tox.ini": ini})
    # execute_calls = tox_proj.patch_execute(lambda r: 0 if "install" in r.run_id else None)
    # result = tox_proj.run("-e", "py123")
    # result.assert_success()
    # assert len(execute_calls) == 2

# def test_conda_create(tox_project, monkeypatch):
#     original_run = CondaEnvRunner._run_with_executor

#     def mock_run(self, executor, request):
#         if request.run_id == "_get_python":
#             return original_run(self, executor, request)
#         # Define your own logic here
#         return "mocked return value"

#     monkeypatch.setattr(CondaEnvRunner, "_run_with_executor", mock_run)

#     ini = "[testenv:py123]"
#     outcome = tox_project({"tox.ini": ini}).run("-e", "py123")
#     outcome.assert_success()



# @pytest.fixture
# def mock_conda_env_runner(request, monkeypatch):
#     original_run = CondaEnvRunner._run_with_executor
#     shell_cmds = []

#     def mock_run(self, executor, request):
#         shell_cmds.append(request.shell_cmd)
#         if request.run_id == "_get_python":
#             return original_run(self, executor, request)

#         mocked_values = request.config.getoption("mocked_values", default={})
#         return mocked_values.get(request.run_id, "default mocked return value")

#     def patch_conda_env_runner():
#         monkeypatch.setattr(CondaEnvRunner, "_run_with_executor", mock_run)

#     patch_conda_env_runner()
#     yield shell_cmds

# @pytest.fixture
# def tox_ini():
#     return "[testenv:py123]"

# def test_conda_create(tox_project, mock_conda_env_runner, tox_ini, pytestconfig):
#     ini = tox_ini
#     pytestconfig.option.mocked_values = {"py123": "custom mocked value for py123"}

#     outcome = tox_project({"tox.ini": ini}).run("-e", "py123")
#     outcome.assert_success()

#     assert "conda env create" in mock_conda_env_runner
#     assert outcome.ret == "custom mocked value for py123"


# def test_conda_create(tox_project, monkeypatch):
#     ini = "[testenv:py123]"
#     tox_proj = tox_project({"tox.ini": ini})
#     execute_calls = tox_proj.patch_execute(lambda r: 0 if "install" in r.run_id else None)
#     result = tox_proj.run("-e", "py123")
#     result.assert_success()
#     assert len(execute_calls) == 2

    # venv = VirtualEnv(config.envconfigs["py123"])
    # assert venv.path == config.envconfigs["py123"].envdir

    # with mocksession.newaction(venv.name, "getenv") as action:
    #     tox_testenv_create(action=action, venv=venv)
    # pcalls = mocksession._pcalls
    # assert len(pcalls) >= 1
    # call = pcalls[-1]
    # assert "conda" in call.args[0]
    # assert "create" == call.args[1]
    # assert "--yes" == call.args[2]
    # assert "-p" == call.args[3]
    # assert venv.path == call.args[4]
    # assert call.args[5].startswith("python=")


# def create_test_env(config, mocksession, envname):

#     venv = VirtualEnv(config.envconfigs[envname])
#     with mocksession.newaction(venv.name, "getenv") as action:
#         tox_testenv_create(action=action, venv=venv)
#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     pcalls[:] = []

#     return venv, action, pcalls


# def test_install_deps_no_conda(newconfig, mocksession, monkeypatch):
#     """Test installation using conda when no conda_deps are given"""
#     # No longer remove the temporary script, so we can check its contents.
#     monkeypatch.delattr(PopenInActivatedEnv, "__del__", raising=False)

#     env_name = "py123"
#     config = newconfig(
#         [],
#         """
#         [testenv:{}]
#         deps=
#             numpy
#             -r requirements.txt
#             astropy
#     """.format(
#             env_name
#         ),
#     )

#     config.toxinidir.join("requirements.txt").write("")

#     venv, action, pcalls = create_test_env(config, mocksession, env_name)

#     assert len(venv.envconfig.deps) == 3
#     assert len(venv.envconfig.conda_deps) == 0

#     tox_testenv_install_deps(action=action, venv=venv)

#     assert len(pcalls) >= 1

#     call = pcalls[-1]

#     if tox.INFO.IS_WIN:
#         script_lines = " ".join(call.args).split(" && ", maxsplit=1)
#         pattern = r"conda\.bat activate .*{}".format(re.escape(env_name))
#     else:
#         # Get the cmd args from the script.
#         shell, cmd_script = call.args
#         assert shell == "/bin/sh"
#         with open(cmd_script) as stream:
#             script_lines = stream.readlines()
#         pattern = r"eval \"\$\(/.*/conda shell\.posix activate /.*/{}\)\"".format(env_name)

#     assert re.match(pattern, script_lines[0])

#     cmd = script_lines[1].split()
#     assert cmd[-6:] == ["-m", "pip", "install", "numpy", "-rrequirements.txt", "astropy"]


# def test_install_conda_deps(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         deps=
#             numpy
#             astropy
#         conda_deps=
#             pytest
#             asdf
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert len(venv.envconfig.conda_deps) == 2
#     assert len(venv.envconfig.deps) == 2 + len(venv.envconfig.conda_deps)

#     tox_testenv_install_deps(action=action, venv=venv)
#     # We expect two calls: one for conda deps, and one for pip deps
#     assert len(pcalls) >= 2
#     call = pcalls[-2]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
#     # Make sure that python is explicitly given as part of every conda install
#     # in order to avoid inadvertent upgrades of python itself.
#     assert conda_cmd[6].startswith("python=")
#     assert conda_cmd[7:9] == ["pytest", "asdf"]


# def test_install_conda_no_pip(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_deps=
#             pytest
#             asdf
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert len(venv.envconfig.conda_deps) == 2
#     assert len(venv.envconfig.deps) == len(venv.envconfig.conda_deps)

#     tox_testenv_install_deps(action=action, venv=venv)
#     # We expect only one call since there are no true pip dependencies
#     assert len(pcalls) >= 1

#     # Just a quick sanity check for the conda install command
#     call = pcalls[-1]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]


# def test_update(tmpdir, newconfig, mocksession):
#     pkg = tmpdir.ensure("package.tar.gz")
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         deps=
#             numpy
#             astropy
#         conda_deps=
#             pytest
#             asdf
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")
#     tox_testenv_install_deps(action=action, venv=venv)

#     venv.hook.tox_testenv_create = tox_testenv_create
#     venv.hook.tox_testenv_install_deps = tox_testenv_install_deps
#     with mocksession.newaction(venv.name, "update") as action:
#         venv.update(action)
#         venv.installpkg(pkg, action)


# def test_conda_spec(tmpdir, newconfig, mocksession):
#     """Test environment creation when conda_spec given"""
#     txt = tmpdir.join("conda-spec.txt")
#     txt.write(
#         """
#         pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_deps=
#             numpy
#             astropy
#         conda_spec={}
#         """.format(
#             str(txt)
#         ),
#     )
#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert venv.envconfig.conda_spec
#     assert len(venv.envconfig.conda_deps) == 2

#     tox_testenv_install_deps(action=action, venv=venv)
#     # We expect conda_spec to be appended to conda deps install
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
#     # Make sure that python is explicitly given as part of every conda install
#     # in order to avoid inadvertent upgrades of python itself.
#     assert conda_cmd[6].startswith("python=")
#     assert conda_cmd[7:9] == ["numpy", "astropy"]
#     assert conda_cmd[-1].startswith("--file")
#     assert conda_cmd[-1].endswith("conda-spec.txt")


# def test_empty_conda_spec_and_env(tmpdir, newconfig, mocksession):
#     """Test environment creation when empty conda_spec and conda_env."""
#     txt = tmpdir.join("conda-spec.txt")
#     txt.write(
#         """
#         pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_env=
#           foo: path-to.yml
#         conda_spec=
#           foo: path-to.yml
#         """,
#     )
#     venv, _, _ = create_test_env(config, mocksession, "py123")

#     assert venv.envconfig.conda_spec is None
#     assert venv.envconfig.conda_env is None


# def test_conda_env(tmpdir, newconfig, mocksession):
#     """Test environment creation when conda_env given"""
#     yml = tmpdir.join("conda-env.yml")
#     yml.write(
#         """
#         name: tox-conda
#         channels:
#           - conda-forge
#           - nodefaults
#         dependencies:
#           - numpy
#           - astropy
#           - pip:
#             - pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_env={}
#         """.format(
#             str(yml)
#         ),
#     )

#     venv = VirtualEnv(config.envconfigs["py123"])
#     assert venv.path == config.envconfigs["py123"].envdir

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")
#     assert venv.envconfig.conda_env

#     mock_file = mock_open()
#     with patch("tox_conda.plugin.tempfile.NamedTemporaryFile", mock_file):
#         with patch.object(pathlib.Path, "unlink", autospec=True) as mock_unlink:
#             with mocksession.newaction(venv.name, "getenv") as action:
#                 tox_testenv_create(action=action, venv=venv)
#                 mock_unlink.assert_called_once

#     mock_file.assert_called_with(dir=tmpdir, prefix="tox_conda_tmp", suffix=".yaml", delete=False)

#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     cmd = call.args
#     assert "conda" in os.path.split(cmd[0])[-1]
#     assert cmd[1:4] == ["env", "create", "-p"]
#     assert venv.path == call.args[4]
#     assert call.args[5].startswith("--file")
#     assert cmd[6] == str(mock_file().name)

#     yaml = YAML()
#     tmp_env = yaml.load(mock_open_to_string(mock_file))
#     assert tmp_env["dependencies"][-1].startswith("python=")


# def test_conda_env_and_spec(tmpdir, newconfig, mocksession):
#     """Test environment creation when conda_env and conda_spec are given"""
#     yml = tmpdir.join("conda-env.yml")
#     yml.write(
#         """
#         name: tox-conda
#         channels:
#           - conda-forge
#           - nodefaults
#         dependencies:
#           - numpy
#           - astropy
#         """
#     )
#     txt = tmpdir.join("conda-spec.txt")
#     txt.write(
#         """
#         pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_env={}
#         conda_spec={}
#         """.format(
#             str(yml), str(txt)
#         ),
#     )
#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert venv.envconfig.conda_env
#     assert venv.envconfig.conda_spec

#     mock_file = mock_open()
#     with patch("tox_conda.plugin.tempfile.NamedTemporaryFile", mock_file):
#         with patch.object(pathlib.Path, "unlink", autospec=True) as mock_unlink:
#             with mocksession.newaction(venv.name, "getenv") as action:
#                 tox_testenv_create(action=action, venv=venv)
#                 mock_unlink.assert_called_once

#     mock_file.assert_called_with(dir=tmpdir, prefix="tox_conda_tmp", suffix=".yaml", delete=False)

#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     cmd = call.args
#     assert "conda" in os.path.split(cmd[0])[-1]
#     assert cmd[1:4] == ["env", "create", "-p"]
#     assert venv.path == call.args[4]
#     assert call.args[5].startswith("--file")
#     assert cmd[6] == str(mock_file().name)

#     yaml = YAML()
#     tmp_env = yaml.load(mock_open_to_string(mock_file))
#     assert tmp_env["dependencies"][-1].startswith("python=")

#     with mocksession.newaction(venv.name, "getenv") as action:
#         tox_testenv_install_deps(action=action, venv=venv)
#     pcalls = mocksession._pcalls
#     # We expect conda_spec to be appended to conda deps install
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
#     # Make sure that python is explicitly given as part of every conda install
#     # in order to avoid inadvertent upgrades of python itself.
#     assert conda_cmd[6].startswith("python=")
#     assert conda_cmd[-1].startswith("--file")
#     assert conda_cmd[-1].endswith("conda-spec.txt")


# def test_conda_install_args(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_deps=
#             numpy
#         conda_install_args=
#             --override-channels
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert len(venv.envconfig.conda_install_args) == 1

#     tox_testenv_install_deps(action=action, venv=venv)

#     call = pcalls[-1]
#     assert call.args[6] == "--override-channels"


# def test_conda_create_args(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_create_args=
#             --override-channels
#     """,
#     )

#     venv = VirtualEnv(config.envconfigs["py123"])
#     assert venv.path == config.envconfigs["py123"].envdir

#     with mocksession.newaction(venv.name, "getenv") as action:
#         tox_testenv_create(action=action, venv=venv)
#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     assert "conda" in call.args[0]
#     assert "create" == call.args[1]
#     assert "--yes" == call.args[2]
#     assert "-p" == call.args[3]
#     assert venv.path == call.args[4]
#     assert call.args[5] == "--override-channels"
#     assert call.args[6].startswith("python=")


# def test_verbosity(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py1]
#         conda_deps=numpy
#         [testenv:py2]
#         conda_deps=numpy
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py1")
#     tox_testenv_install_deps(action=action, venv=venv)
#     assert len(pcalls) == 1
#     call = pcalls[0]
#     assert "conda" in call.args[0]
#     assert "install" == call.args[1]
#     assert isinstance(call.stdout, io.IOBase)

#     tox.reporter.update_default_reporter(
#         tox.reporter.Verbosity.DEFAULT, tox.reporter.Verbosity.DEBUG
#     )
#     venv, action, pcalls = create_test_env(config, mocksession, "py2")
#     tox_testenv_install_deps(action=action, venv=venv)
#     assert len(pcalls) == 1
#     call = pcalls[0]
#     assert "conda" in call.args[0]
#     assert "install" == call.args[1]
#     assert not isinstance(call.stdout, io.IOBase)


# def mock_open_to_string(mock):
#     return "".join(call.args[0] for call in mock().write.call_args_list)
