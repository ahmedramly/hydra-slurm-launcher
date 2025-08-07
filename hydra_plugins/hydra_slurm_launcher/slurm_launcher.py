import logging
from pathlib import Path
from hydra.plugins.launcher import Launcher
from hydra.types import TaskFunction, HydraContext
from hydra.core.utils import (
    JobReturn,
    filter_overrides,
    setup_globals,
    configure_log,
)
from hydra_plugins.hydra_slurm_launcher._core import submit_job_array
from omegaconf import DictConfig, OmegaConf
from typing import Any, List, Optional
from .config import SlurmQueueConf


log = logging.getLogger(__name__)


class SlurmLauncher(Launcher):
    def __init__(self, **kwargs: Any) -> None:
        resolved_kwargs = OmegaConf.to_container(
            OmegaConf.create(kwargs), resolve=True
        )
        self.slurm_config = SlurmQueueConf(**resolved_kwargs)

        self.config: Optional[DictConfig] = None
        self.task_function: Optional[TaskFunction] = None
        self.hydra_context: Optional[HydraContext] = None

    def setup(
        self,
        *,
        hydra_context: HydraContext,
        task_function: TaskFunction,
        config: DictConfig,
    ) -> None:
        """
        Setup method to initialize the launcher.
        """
        self.hydra_context = hydra_context
        self.task_function = task_function
        self.config = config

    def launch(
        self, job_overrides: List[List[str]], initial_job_idx: int
    ) -> List[JobReturn]:
                
        setup_globals()
        assert self.hydra_context is not None
        assert self.config is not None
        assert self.task_function is not None

        configure_log(
            self.config.hydra.hydra_logging, self.config.hydra.verbose
        )
        sweep_dir = Path(str(self.config.hydra.sweep.dir))
        sweep_dir.mkdir(parents=True, exist_ok=True)

        # Check if using job array based on config
        if self.slurm_config.job_array_name is not None:
            return self._launch_job_array(
                job_overrides, initial_job_idx, sweep_dir
            )
        else:
            return self._launch_individual_jobs(
                job_overrides, initial_job_idx, sweep_dir
            )

    def _launch_job_array(
        self,
        job_overrides: List[List[str]],
        initial_job_idx: int,
        sweep_dir: Path,
    ) -> List[JobReturn]:
        """Launch jobs as a single SLURM job array"""
        
        from ._core import submit_job_array
        
        log.info(
            f"Submitting {len(job_overrides)} jobs to SLURM as a job array"
        )

        # Collect information for each job
        job_names = []
        output_dirs = []

        for idx, overrides in enumerate(job_overrides):
            idx = initial_job_idx + idx

            # Load config for this specific job to get job name and output directory
            sweep_config = self.hydra_context.config_loader.load_sweep_config(
                self.config, overrides
            )

            output_dir = sweep_dir / str(sweep_config.hydra.sweep.subdir)
            job_name = str(sweep_config.hydra.job.name)

            job_names.append(job_name)
            output_dirs.append(str(output_dir))

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

        # Submit all jobs as a single array job
        returns = submit_job_array(
            config=self.slurm_config,
            all_overrides=job_overrides,
            job_names=job_names,
            output_dirs=output_dirs,
            sweep_dir=str(
                sweep_dir
            ),  # Pass the sweep directory for the array script
        )

        return returns

    def _launch_individual_jobs(
        self,
        job_overrides: List[List[str]],
        initial_job_idx: int,
        sweep_dir: Path,
    ) -> List[JobReturn]:
        """Launch jobs individually"""
        
        from ._core import submit_job
        
        log.info(f"Submitting {len(job_overrides)} jobs to SLURM individually")
        returns: List[JobReturn] = []

        for idx, overrides in enumerate(job_overrides):
            idx = initial_job_idx + idx
            lst = " ".join(filter_overrides(overrides))
            log.info(f"Submitting job {idx} with overrides: {lst}")

            sweep_config = self.hydra_context.config_loader.load_sweep_config(
                self.config, overrides
            )
            output_dir = sweep_dir / str(sweep_config.hydra.sweep.subdir)
            output_dir.mkdir(parents=True, exist_ok=True)
            job_name = str(sweep_config.hydra.job.name)

            ret = submit_job(
                config=self.slurm_config,
                overrides=overrides,
                job_name=job_name,
                output_dir=str(output_dir),
            )
            returns.append(ret)

        return returns
