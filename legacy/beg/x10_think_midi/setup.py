"""
Setup script for X10 Think MIDI Intelligence Engine.

Install with: pip install -e .
Build with: python setup.py sdist bdist_wheel
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

setup(
    name="x10-think-midi",
    version="1.0.0",
    author="X10 Think Team",
    author_email="contact@x10think.dev",
    description="Professional-grade Python MIDI Intelligence Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/x10think/x10-think-midi",
    project_urls={
        "Bug Tracker": "https://github.com/x10think/x10-think-midi/issues",
        "Documentation": "https://x10think.github.io/docs",
    },
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Musicians",
        "Topic :: Multimedia :: Sound/Audio :: MIDI",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "PyYAML>=6.0",
    ],
    extras_require={
        "gui": ["PyQt6>=6.4.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "Sphinx>=6.0.0",
            "sphinx-rtd-theme>=1.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "x10-think=x10_think.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "x10_think": [
            "resources/rules/*.json",
            "resources/profiles/*.json",
            "resources/themes/*.qss",
        ],
    },
)
