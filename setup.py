from setuptools import setup, find_packages

setup(
    name="shadow-aegis",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "shadow-aegis=core.engine:main",
        ],
    },
    author="ShadowAI",
    description="Universal Quality Guardrail for AI-Human Interaction",
    python_requires=">=3.10",
)
