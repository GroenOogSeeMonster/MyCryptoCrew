from setuptools import setup, find_packages

setup(
    name="crypto_analysis_project",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.1",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "flake8>=4.0.1",
            "black>=23.0.0",
            "isort>=5.12.0",
        ]
    },
    python_requires=">=3.9",
) 