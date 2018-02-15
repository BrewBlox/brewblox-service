from setuptools import setup, find_packages


setup(
    name='brewblox-service',
    version='0.2',
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/brewblox-service',
    author='BrewPi',
    author_email='elco@brewpi.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    keywords='brewing brewpi brewblox embedded',
    packages=find_packages(exclude=['test']),
    package_data={'brewblox_service': ['plugins/*/info.json']},
    install_requires=[
        'Flask',
        'flask-cors',
        'flask-apispec',
        'flask-plugins',
        'pprint',
        'dpath',
        'requests',
    ],
    extras_require={'dev': ['tox']},
    entry_points={
        'console_scripts': [
            'brewblox = brewblox_service.__main__:main'
        ]
    }
)
