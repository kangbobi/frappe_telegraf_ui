from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in frappe_whatsapp/__init__.py
from frappe_telegraf_ui import __version__ as version

setup(
    name="frappe_telegraf_ui",
    version=version,
    description="Telegraf UI",
    author="Kang bobi",
    author_email="devprogramming.bs@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)