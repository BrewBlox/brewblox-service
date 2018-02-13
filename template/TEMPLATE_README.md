# Package template for BrewBlox Service plugins

There is some boilerplate code involved when creating a new Python package.

The general idea is that you copy everything in here to your new repository or directory, update some placeholder names, and start coding.

## Files

### [setup.py](./setup.py)
Used to create a distributable and installable Python package. See https://docs.python.org/3.6/distutils/setupscript.html for more information.

**Required Changes:** 
* Change the `project_name` variable to your project name. This is generally the same as the repository name. This name is used when installing the package through Pip.
* Change the `package_name` variable to the module name. This can be the same name as your project name, but can't include dashes `-`. This name is used when importing your package in Python.
* Check whether all other fields are correct. Refer to the documentation for more info.


### [tox.ini](./tox.ini)
This file kicks off automated testing and linting of your package. See http://tox.readthedocs.io/en/latest/config.html for more information.

**Required Changes:**
* Change `--cov=YOUR_PACKAGE` to refer to your module name.
* The `--cov-fail-under=100` makes the build fail if code coverage is less than 100%. It is optional, but recommended. Remove the `#` comment character to enable it.


### [requirements.txt](./requirements.txt)
Include all runtime requirements for your package here. See https://pip.pypa.io/en/stable/reference/pip_install/#requirements-file-format for more information.

**Note:** There is overlap between your requirements file, and the `install_requires=[]` line in `setup.py`. For most cases, the rule of thumb is that if you need an external package to run, you should add it as dependency to both files.


### [requirements-dev.txt](./requirements-dev.txt)
The file works just like [requirements.txt](./requirements.txt), but should only list the packages needed to test the code. End users do not need these dependencies.


### [.coveragerc](./.coveragerc)
This file contains some configuration for `pytest-cov`. In most normal cases, you do not have to change anything.


### [README.md](./README.md)
TODO


### [YOUR_PACKAGE/](./YOUR_PACKAGE/)
Your module. This directory name should match the `package_name` variable in `setup.py`.
**Required Changes:**
* Rename to the desired module name. (Python import name. Can't include dashes "-").


### [YOUR_PACKAGE/plugins](./YOUR_PACKAGE/plugins)
The directory in which the Flask plugin manager will be looking for your plugin. See https://flask-plugins.readthedocs.io/en/latest/ for more information.
**Required Changes:**
* Add your code here.
