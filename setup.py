from setuptools import setup, find_packages

setup(
    name="shadow-refiner",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "shadow-refiner=core.engine:main",
        ],
    },
    author="ShadowAI",
    description="Universal Intent Reconstruction and Quality Refinement Layer",
    python_requires=">=3.10",
)
