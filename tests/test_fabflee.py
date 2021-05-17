import os
import sys
import subprocess
import pytest
import logging


base = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "FabFlee/config_files"
)

logger = logging.getLogger(__name__)

# GitHub action = 2 cores


def test_par_mali(run_par):
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG)
    ret = run_par("mali", "10", "2")
    assert ret == "OK"


@pytest.fixture
def run_py():
    def _run_py(config, simulation_period):
        config_path = os.path.join(base, config)
        current_dir = os.getcwd()
        os.chdir(config_path)

        cmd = ["python3",
               "run.py",
               "input_csv",
               "source_data",
               simulation_period,
               "simsetting.csv",
               "> out.csv"
               ]

        ret = "OK"
        try:
            output = subprocess.check_output(cmd).decode("utf-8")
        except subprocess.CalledProcessError as e:
            ret = "Command '{}' return non-zero exit status: {}\n{}".format(
                " ".join(cmd), e.returncode, e.output
            )

        os.chdir(current_dir)
        return ret
        # assert(output.find('success') >= 0)
    return _run_py


@pytest.fixture
def run_par():
    def _run_par(config, simulation_period, cores):
        config_path = os.path.join(base, config)
        current_dir = os.getcwd()
        os.chdir(config_path)
        cmd = ["mpirun",
               "-n",
               cores,
               "python3",
               "run.py",
               "input_csv",
               "source_data",
               simulation_period,
               "simsetting.csv",
               "> out.csv"
               ]

        ret = "OK"
        try:
            output = subprocess.check_output(cmd).decode("utf-8")
        except subprocess.CalledProcessError as e:
            ret = "Command '{}' return non-zero exit status: {}\n{}".format(
                " ".join(cmd), e.returncode, e.output
            )

        os.chdir(current_dir)
        return ret
        # assert(output.find('success') >= 0)
    return _run_par
