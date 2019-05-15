from setuptools import find_packages, setup

setup(
    name='brewblox-service',
    use_scm_version={'local_scheme': lambda v: ''},
    description='Scaffolding for BrewBlox backend services',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/BrewBlox/brewblox-service',
    author='BrewPi',
    author_email='development@brewpi.com',
    license='GPLv3',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.7',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    keywords='brewing brewpi brewblox embedded',
    packages=find_packages(exclude=['test']),
    install_requires=[
        'pprint',
        'aiohttp',
        'cchardet',
        'aiohttp-swagger',
        'aioamqp',
    ],
    python_requires='>=3.7',
    setup_requires=['setuptools_scm']
)
