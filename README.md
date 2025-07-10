# Hydra SLURM Launcher

A custom Hydra launcher plugin that submits jobs to a SLURM cluster using `sbatch`. This plugin extends Hydra's multirun capabilities to seamlessly work with SLURM workload managers, allowing you to run parameter sweeps and parallel jobs on HPC clusters without terminal blocking.

## Features

- **SLURM Integration**: Submit Hydra jobs directly to SLURM clusters using `sbatch`
- **Job Arrays**: Support for SLURM job arrays for efficient parallel execution
- **Flexible Configuration**: Comprehensive SLURM parameter configuration including resources, partitions, and GPU support
- **Resource Management**: Configure nodes, CPUs, memory, and GPU resources
- **Custom Setup**: Support for custom environment setup commands
- **Notification Support**: Configure email notifications for job status updates

## Installation

### From Source

```bash
git clone <repository-url>
cd hydra-slurm-launcher
pip install -e .
```

<!-- ### Using pip (if published)

```bash
pip install hydra-slurm-launcher
``` -->

## Requirements

- Python >= 3.6
- hydra-core >= 1.0.0
- Access to a SLURM cluster

## Usage

### Basic Configuration

Add the SLURM launcher to your Hydra configuration:

```yaml
# config.yaml
defaults:
  - _self_
  - override hydra/launcher: slurm

# Your application config here
param1: value1
param2: value2

launcher:
  partition: gpu
  time: "01:00:00"
  cpus_per_task: 4
  mem: "16G"
  gpus: 1
```

### Running a Sweep

```bash
python your_script.py -m param1=1,2,3 param2=a,b,c
```

### Advanced Configuration

```yaml
launcher:
  _target_: hydra_plugins.hydra_slurm_launcher.slurmlauncher.SlurmLauncher
  
  # Basic SLURM configuration
  partition: gpu
  job_name: my_experiment
  job_array_name: null  # Set to use job arrays instead of individual jobs
  
  # Resource configuration
  nodes: 1
  ntasks: 1
  ntasks_per_node: null
  cpus_per_task: 8
  mem: "32G"
  time: "02:00:00"
  
  # GPU configuration
  gres: "gpu:v100:2"  # or use gpus: 2
  
  # Job configuration
  account: my_account
  qos: normal
  begin: null  # Schedule job to start at specific time
  
  # Notification configuration
  mail_type: "BEGIN,END,FAIL"
  mail_user: "user@example.com"
  
  # Additional SLURM parameters
  additional:
    constraint: "intel"
    exclusive: ""
  
  # Custom setup commands
  setup:
    - "module load python/3.8"
    - "source activate myenv"
    - "export CUDA_VISIBLE_DEVICES=$SLURM_LOCALID"
```

## Configuration Options

### Basic Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `partition` | str | SLURM partition to submit to | "default" |
| `job_name` | str | Name for individual jobs | None |
| `job_array_name` | str | Name for job array (enables array mode) | None |

### Resource Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `nodes` | int | Number of nodes | None |
| `ntasks` | int | Number of tasks | None |
| `ntasks_per_node` | int | Number of tasks per node | None |
| `cpus_per_task` | int | Number of CPUs per task | None |
| `mem` | str | Memory requirement (e.g., "16G") | None |
| `time` | str | Time limit (e.g., "01:30:00") | None |

### GPU Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `gres` | str | Generic resource specification | None |
| `gpus` | int | Number of GPUs (alternative to gres) | None |

### Job Management

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `account` | str | SLURM account to charge | None |
| `qos` | str | Quality of Service | None |
| `begin` | str | Job start time | None |

### Notifications

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `mail_type` | str | When to send email notifications | None |
| `mail_user` | str | Email address for notifications | None |

### Advanced Options

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `additional` | dict | Additional SLURM parameters | {} |
| `setup` | list | Custom setup commands | [] |

## Job Arrays vs Individual Jobs

### Individual Jobs (Default)

Each parameter combination is submitted as a separate SLURM job:

```yaml
launcher:
  job_name: experiment
  partition: gpu
```

### Job Arrays

All parameter combinations are submitted as a single job array:

```yaml
launcher:
  job_array_name: experiment_array
  partition: gpu
```

Job arrays are more efficient for large parameter sweeps and reduce scheduler overhead.

## Examples

### Machine Learning Training

```yaml
# config.yaml
defaults:
  - launcher: slurm

model:
  lr: 0.001
  batch_size: 32

launcher:
  partition: gpu
  time: "04:00:00"
  cpus_per_task: 8
  mem: "32G"
  gpus: 1
  setup:
    - "module load cuda/11.2"
    - "source activate ml_env"
```

```bash
python train.py -m model.lr=0.001,0.01,0.1 model.batch_size=32,64,128
```

### Data Processing Pipeline

```yaml
launcher:
  partition: cpu
  time: "01:00:00"
  cpus_per_task: 16
  mem: "64G"
  job_array_name: data_processing
  setup:
    - "module load python/3.9"
```


## License

This project is licensed under the MIT License - see the LICENSE file for details.


## Acknowledgments

- Built on top of [Hydra](https://hydra.cc/) by Facebook Research
- Inspired by the need for seamless HPC integration with modern ML workflows