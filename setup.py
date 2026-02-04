#!/usr/bin/env python3
"""
Setup script for Voice Chess.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements = []
req_file = Path(__file__).parent / "requirements.txt"
if req_file.exists():
    requirements = [
        line.strip()
        for line in req_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="voice-chess",
    version="1.0.0",
    description="Play chess against Ollama using your voice",
    author="Voice Chess",
    python_requires=">=3.10",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "": ["static/*"],
    },
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "chess=server.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment :: Board Games",
    ],
)
