from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in amb_w_spc/__init__.py
from amb_w_spc import __version__ as version

setup(
    name="amb_w_spc",
    version=version,
    description="Advanced Manufacturing Business - Workforce Statistical Process Control",
    author="AMB Systems",
    author_email="info@ambsystems.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Frappe",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    project_urls={
        "Documentation": "https://github.com/your-username/amb_w_spc/wiki",
        "Source": "https://github.com/your-username/amb_w_spc",
        "Tracker": "https://github.com/your-username/amb_w_spc/issues",
    },
)