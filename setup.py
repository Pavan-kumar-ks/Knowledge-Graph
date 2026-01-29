"""
Setup configuration for the Policy Knowledge Graph package.
"""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="policy-knowledge-graph",
    version="0.1.0",
    author="Your Name",
    description="Extract entities from policy documents and load into Neo4j graph",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyPDF2>=3.0.0",
        "neo4j>=5.0.0",
        "python-dotenv>=0.19.0",
    ],
    entry_points={
        "console_scripts": [
            "policy-graph=src.pipeline:main",
        ],
    },
)
