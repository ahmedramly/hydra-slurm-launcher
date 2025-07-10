from dataclasses import dataclass, field
from typing import Optional, List, Dict
from hydra.core.config_store import ConfigStore


@dataclass
class SlurmQueueConf:
    _target_: str = (
        "hydra_plugins.hydra_slurm_launcher.slurmlauncher.SlurmLauncher"
    )

    # Basic SLURM configuration
    partition: str = "default"
    job_name: Optional[str] = None
    job_array_name: Optional[str] = (
        None  # If set, use job array instead of individual jobs
    )

    # Resource configuration
    nodes: Optional[int] = None
    ntasks: Optional[int] = None
    ntasks_per_node: Optional[int] = None
    cpus_per_task: Optional[int] = None
    mem: Optional[str] = None
    time: Optional[str] = None

    # GPU configuration
    gres: Optional[str] = None
    gpus: Optional[int] = None

    # Job configuration
    account: Optional[str] = None
    qos: Optional[str] = None
    begin: Optional[str] = None

    # Notification configuration
    mail_type: Optional[str] = None
    mail_user: Optional[str] = None

    # Additional configuration
    additional: Dict[str, str] = field(default_factory=dict)
    setup: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.gpus is not None and self.gres is not None:
            raise ValueError("Cannot specify both 'gpus' and 'gres'")
        if self.gpus is not None:
            self.gres = f"gpu:{self.gpus}"
        if self.job_name is not None and self.job_array_name is not None:
            raise ValueError(
                "Cannot specify both 'job_name' and 'job_array_name'"
            )


cs = ConfigStore.instance()
cs.store(
    group="hydra/launcher",
    name="slurm",
    node=SlurmQueueConf(),
    provider="hydra_slurm_launcher",
)
