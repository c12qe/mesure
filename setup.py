import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
    name="joelpendleton", # Replace with your own username
    version="0.0.1",
    author="Joel Pendleton",
    author_email="contact@joelpendleton.com",
    description="A package to enable easy measurent, analysis and control of quantum dot experiments.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/c12qe/mesure",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='=3.9.12',
)