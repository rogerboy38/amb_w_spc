from setuptools import setup, find_packages

with open("requirements.txt") as f:
	requirements = f.read().strip().split("\n")

setup(
	name="amb_w_spc",
	version="2.0.0",
	description="Advanced Manufacturing & Statistical Process Control - Integrated SFC and SPC System",
	author="MiniMax Agent",
	author_email="admin@example.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=requirements
)