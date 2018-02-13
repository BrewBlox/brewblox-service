from setuptools import setup, find_packages

project_name = 'YOUR-PACKAGE'
package_name = 'YOUR_PACKAGE'

setup(
    name=project_name,
    version='0.1',
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/' + project_name,
    author='BrewPi',
    author_email='development@brewpi.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    keywords='brewing brewpi brewblox embedded plugin service',
    packages=find_packages(exclude=['test']),
    package_data={package_name: ['plugins/*/info.json']},
    install_requires=[
        'brewblox-service'
    ],
    extras_require={'dev': ['tox']}
)
