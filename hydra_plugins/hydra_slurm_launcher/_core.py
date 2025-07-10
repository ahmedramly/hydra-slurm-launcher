import subprocess
import os
import shlex
import sys
import json
from pathlib import Path
from hydra.utils import to_absolute_path
from hydra.core.utils import (
    JobReturn,
    JobStatus,
    filter_overrides,
)
from typing import Any, List
from .config import SlurmQueueConf


def submit_job(
    config: SlurmQueueConf,
    overrides: List[str],
    job_name: str,
    output_dir: str,
) -> JobReturn:
    cmd = build_command(overrides)
    script_path = generate_slurm_script(config, job_name, output_dir, cmd)

    ret = JobReturn()
    ret.return_value = None
    submitted = subprocess.run(
        ["sbatch", script_path], check=True, stdout=subprocess.PIPE, text=True
    )
    if submitted.returncode == 0:
        # Try to extract job ID
        job_id = None
        for line in submitted.stdout.splitlines():
            if "Submitted batch job" in line:
                job_id = line.strip().split()[-1]

        ret.status = JobStatus.COMPLETED
        ret.return_value = {"job_id": job_id} if job_id else None
    else:
        ret.status = JobStatus.FAILED

    return ret


def submit_job_array(
    config: SlurmQueueConf,
    all_overrides: List[List[str]],
    job_names: List[str],
    output_dirs: List[str],
    sweep_dir: str,
) -> List[JobReturn]:
    """
    Submit all jobs as a SLURM job array.

    Args:
        config: SLURM configuration
        all_overrides: List of override lists, one per job
        job_names: List of job names, one per job
        output_dirs: List of output directories, one per job
        sweep_dir: Main sweep directory where array script will be saved

    Returns:
        List of JobReturn objects, one per job
    """
    # Create a directory for storing override configurations within the sweep directory
    # array_dir = os.path.join(sweep_dir, "array_configs")
    # os.makedirs(array_dir, exist_ok=True)

    # Use job_array_name for naming config file
    array_name = config.job_array_name

    # Store all overrides and output information in a single JSON file
    array_config_file = os.path.join(
        sweep_dir, f"{array_name}_array_config.json"
    )
    config_data = []

    for idx, (overrides, job_name, output_dir) in enumerate(
        zip(all_overrides, job_names, output_dirs)
    ):
        config_data.append(
            {
                "overrides": " ".join(filter_overrides(overrides)),
                "job_name": job_name,
                "output_dir": output_dir,
                "task_id": idx,
            }
        )

    with open(array_config_file, "w") as f:
        json.dump(config_data, f)

    # Generate array script
    array_size = len(all_overrides)
    array_script = generate_array_script(
        config=config,
        array_name=array_name,
        array_size=array_size,
        config_file=array_config_file,
        sweep_dir=sweep_dir,
    )

    # Make the script executable
    os.chmod(array_script, 0o755)

    # Submit the job array
    try:
        submitted = subprocess.run(
            ["sbatch", array_script],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )

        # Extract job ID if possible
        array_job_id = None
        for line in submitted.stdout.splitlines():
            if "Submitted batch job" in line:
                array_job_id = line.strip().split()[-1]

        # Create one JobReturn per task in the array
        returns = []
        for i in range(array_size):
            ret = JobReturn()
            ret.status = JobStatus.COMPLETED
            ret.return_value = {
                "job_id": f"{array_job_id}_{i}" if array_job_id else None
            }
            returns.append(ret)

        return returns

    except subprocess.CalledProcessError:
        # In case of failure, return failed status for all jobs
        returns = [
            JobReturn(status=JobStatus.FAILED) for _ in range(array_size)
        ]
        return returns


def generate_array_script(
    config: SlurmQueueConf,
    array_name: str,
    array_size: int,
    config_file: str,
    sweep_dir: str,
) -> str:
    """
    Generate a SLURM script for a job array.

    Args:
        config: SLURM configuration
        array_name: Name for the job array
        array_size: Size of the job array
        config_file: Path to the JSON file containing configs
        sweep_dir: Main sweep directory where the script will be saved

    Returns:
        Path to the generated script
    """
    non_slurm = [
        "additional",
        "setup",
        "_target_",
        "job_name",
        "job_array_name",
    ]

    paths = {"array": f"0-{array_size-1}"}

    params = {
        k: v
        for k, v in vars(config).items()
        if v is not None and k not in non_slurm
    }
    params.update(paths)

    if config.additional:
        params.update(config.additional)

    # Define the script contents
    lines = ["#!/bin/bash", " ", "# SLURM parameters"]

    # Add job name parameter
    lines.append(f"#SBATCH --job-name={array_name}")

    # Explicitly tell SLURM to discard its own output files
    lines.append("#SBATCH --output=/dev/null")
    lines.append("#SBATCH --error=/dev/null")

    # Add other SLURM parameters
    for k in params:
        if k not in ["output", "error"]:
            lines.append(as_sbatch_flag(k, params[k]))

    # Add commands to handle task-specific configuration
    lines += [
        " ",
        "# Get task-specific configuration",
        "CONFIG=$(python -c \"import json; import os; import sys; f=open('"
        + config_file
        + "'); "
        + "configs=json.load(f); task_id=int(os.environ['SLURM_ARRAY_TASK_ID']); "
        + 'print(json.dumps(configs[task_id])) if 0 <= task_id < len(configs) else sys.exit(1)")',
        " ",
        "if [ $? -ne 0 ]; then",
        '    echo "Error: Could not retrieve configuration for task $SLURM_ARRAY_TASK_ID"',
        "    exit 1",
        "fi",
        " ",
        "# Extract task-specific information",
        "OVERRIDES=$(echo $CONFIG | python -c \"import json; import sys; print(json.loads(sys.stdin.read())['overrides'])\")",
        "JOB_NAME=$(echo $CONFIG | python -c \"import json; import sys; print(json.loads(sys.stdin.read())['job_name'])\")",
        "OUTPUT_DIR=$(echo $CONFIG | python -c \"import json; import sys; print(json.loads(sys.stdin.read())['output_dir'])\")",
        " ",
        "# Create output directory if it doesn't exist",
        'mkdir -p "$OUTPUT_DIR"',
        " ",
        "# Redirect all output to the job-specific files",
        'exec > "$OUTPUT_DIR/${JOB_NAME}_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.out"',
        'exec 2> "$OUTPUT_DIR/${JOB_NAME}_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.err"',
        " ",
    ]

    # Add setup commands if they exist
    if config.setup:
        lines += [" ", "# Setup commands"] + config.setup

    # Run the main command
    lines += [
        " ",
        "# Run the command",
        f"python {to_absolute_path(sys.argv[0])} hydra.launcher=basic $OVERRIDES",
    ]

    script = "\n".join(lines)

    # Save the array script in the sweep directory
    script_path = os.path.join(sweep_dir, f"{array_name}_array.sh")

    with open(script_path, "w") as f:
        f.write(script)

    return script_path


def generate_slurm_script(
    config: SlurmQueueConf, job_name: str, output_dir: str, command: str
) -> Path:
    non_slurm = ["additional", "setup", "_target_", "job_array_name"]

    # Store original job_name from config
    original_config_job_name = config.job_name

    # Set job name for SLURM directives
    if config.job_name is None:
        config.job_name = job_name

    paths = {
        "output": f"{output_dir}/{config.job_name}_%j.out",
        "error": f"{output_dir}/{config.job_name}_%j.err",
    }

    params = {
        k: v
        for k, v in vars(config).items()
        if v is not None and k not in non_slurm
    }
    params.update(paths)
    if config.additional:
        params.update(config.additional)

    lines = ["#!/bin/bash", " ", "# SLURM parameters"]
    for k in params:
        lines.append(as_sbatch_flag(k, params[k]))
    if config.setup:
        lines += [" ", "# Setup commands"] + config.setup
    lines += [" ", "# Run the command", command]
    script = "\n".join(lines)

    # Use job_name for script filename, not config.job_name
    script_path = os.path.join(output_dir, f"{job_name}.sh")
    with open(script_path, "w") as f:
        f.write(script)

    # Restore original job_name in config to avoid side effects
    config.job_name = original_config_job_name

    return script_path


def build_command(overrides: List[str]) -> str:
    overrides = filter_overrides(overrides)
    command = f"python {to_absolute_path(sys.argv[0])} hydra.launcher=basic"
    if overrides:
        command += " " + " ".join(overrides)
    return command


# adapted from https://github.com/facebookincubator/submitit/blob/main/submitit/slurm/slurm.py
def as_sbatch_flag(key: str, value: Any) -> str:
    key = key.replace("_", "-")
    if isinstance(value, bool):
        return f"#SBATCH --{key}"
    value = shlex.quote(str(value))
    return f"#SBATCH --{key}={value}"
