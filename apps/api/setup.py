from setuptools import find_packages, setup


setup(
    name="learn-to-draw-api",
    version="0.1.0",
    description="Local-first hardware API for LearnToDraw",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "fastapi>=0.115,<1.0",
        "opencv-python>=4.10,<5.0",
        "python-multipart>=0.0.9,<1.0",
        "uvicorn>=0.30,<1.0",
    ],
    extras_require={
        "dev": [
            "httpx>=0.27,<1.0",
            "pytest>=8.0,<9.0",
        ]
    },
)
