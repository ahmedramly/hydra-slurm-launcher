from setuptools import setup, find_namespace_packages

setup(
    name="hydra-slurm-launcher",
    version="1.0.0",
    author="Ahmed Alramly",
    author_email="ahmedramly@gmail.com",
    description="A custom Hydra (pseudo)-launcher to submit jobs to a SLURM cluster using sbatch.",
    packages=find_namespace_packages(include=["hydra_plugins.*"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Framework :: Hydra :: Plugin",
    ],
    install_requires=[
        "hydra-core>=1.0.0",
    ],
    python_requires=">=3.6",
)
