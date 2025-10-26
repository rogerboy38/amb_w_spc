from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="amb_w_spc",
    version="2.0.0",
    description="Advanced Manufacturing, Warehouse Management & Statistical Process Control for ERPNext",
    long_description="""
    AMB W SPC is a comprehensive manufacturing and warehouse management system built for ERPNext.
    
    Features:
    - Advanced Warehouse Management with zone tracking and temperature control
    - Statistical Process Control (SPC) with real-time monitoring
    - Material Assessment and Quality Management
    - Batch tracking and traceability
    - Pick task management and optimization
    - Real-time alerts and performance analytics
    - Integrated sales order fulfillment
    - FDA compliance and audit trails
    - Plant-specific access controls
    
    Perfect for pharmaceutical, food, and manufacturing industries requiring 
    strict quality control and warehouse optimization.
    """,
    long_description_content_type="text/plain",
    author="AMB-Wellness",
    author_email="fcrm@amb-wellness.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    license="MIT",
    url="https://github.com/rogerboy38/amb_w_spc",
    project_urls={
        "Documentation": "https://github.com/rogerboy38/amb_w_spc/wiki",
        "Source": "https://github.com/rogerboy38/amb_w_spc",
        "Tracker": "https://github.com/rogerboy38/amb_w_spc/issues",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Framework :: ERPNext",
        "Intended Audience :: Manufacturing",
        "Intended Audience :: Healthcare Industry", 
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Manufacturing",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Scientific/Engineering :: Mathematics",
    ],
    keywords="erpnext manufacturing warehouse spc quality control batch tracking",
    python_requires=">=3.8",
    entry_points={
        "frappe": [
            "amb_w_spc = amb_w_spc.hooks"
        ]
    },
)