from setuptools import setup, find_packages


setup(
    name='brewblox-service',
    version='0.3.1',
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/brewblox-service',
    author='BrewPi',
    author_email='development@brewpi.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    keywords='brewing brewpi brewblox embedded',
    packages=find_packages(exclude=['test']),
    install_requires=[
        'pprint',
        'dpath',
        'aiohttp',
        'aiodns',
        'cchardet',
        'aiohttp-cors',
        'aiohttp-swagger',
        'aio-pika',
    ],
    extras_require={'dev': ['tox']}
)
