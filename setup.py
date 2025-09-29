from setuptools import setup, find_packages
import os
import re

# Read requirements
with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# Read version from __init__.py without importing it
init_path = os.path.join(os.path.dirname(__file__), "amb_w_spc", "__init__.py")
with open(init_path, "r") as f:
    version_content = f.read()

version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_content)
if version_match:
    version = version_match.group(1)
else:
    version = "1.0.0"

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
)
