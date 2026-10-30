"""Compatibility entry point for setuptools versions before PEP 621 support."""
from pathlib import Path
from setuptools import find_packages, setup

setup(
    name="workcert", version="0.1.0",
    description="Certified piecewise-linear reduction and work queries for force-displacement responses",
    long_description=Path("README.md").read_text(encoding="utf8"),
    long_description_content_type="text/markdown", license="MIT",
    author="Saisai Hou, Yunzhi Zhu, Sen Zhang", author_email="szhang@niit.edu.cn",
    package_dir={"": "src"}, packages=find_packages("src"),
    python_requires=">=3.8", install_requires=["numpy>=1.24"],
    entry_points={"console_scripts": ["workcert=workcert.cli:main"]},
)

