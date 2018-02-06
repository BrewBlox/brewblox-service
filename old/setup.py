from setuptools import setup

setup(
    name='brewpi-service',
    version='0.1',
    long_description=__doc__,
    packages=['brewpi_service'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['Flask']
)
