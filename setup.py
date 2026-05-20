from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ai-flow-architect",
    version="0.1.0",
    author="盛鑫",
    author_email="2709786902@qq.com",
    description="AI proposes. You decide. — Adversarial AI workflow engine with built-in quality arbitration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wdnmd1265/ai-flow-architect",
    project_urls={
        "Bug Tracker": "https://github.com/wdnmd1265/ai-flow-architect/issues",
        "Documentation": "https://github.com/wdnmd1265/ai-flow-architect#readme",
        "Source Code": "https://github.com/wdnmd1265/ai-flow-architect",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
            "flake8>=6.1.0",
            "pre-commit>=3.3.0",
            "sphinx>=7.0.0",
            "sphinx-rtd-theme>=1.3.0",
        ],
        "redis": [
            "redis>=5.0.0",
        ],
        "all": [
            "redis>=5.0.0",
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "isort>=5.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ai-flow=ai_flow_architect.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords=[
        "ai",
        "workflow",
        "multi-model",
        "collaboration",
        "token-saving",
        "quality-assurance",
    ],
)