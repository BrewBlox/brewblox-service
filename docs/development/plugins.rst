Plugin Authoring Guide
======================

In this section, you'll learn how to write a plugin for the BrewPi Service and
how to use the available hooks to inject features and models in the engine.

Quickstart
----------

As with every python project, you should first create a directory with a
:file:`setup.py` file.

A bare minimal :file:`setup.py` should look like the following:

.. code-block:: python
   :linenos:

   import os
   from setuptools import setup, find_packages
   
   # allow setup.py to be run from any path
   os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))
   
   setup(
                name = "brewpi.service.devices.humiditysensor",
                description='Humidity Sensor device support for the BrewPi Service',
                version = "0.1",
                packages = find_packages(),
                namespace_packages = ['devices.humiditysensor'],
   )


As you can see, this file uses :py:mod:`setuptools` which is a standard toolkit
for distributing python packages.

Our `namespace_packages` is pointing to "devices.humiditysensor". This means that we need to create a directory structure as such:

.. code-block:: bash

   devices/
     __init__.py
     humiditysensors/
       __init__.py


For **every** __init__.py, the first line should be:

.. code-block:: python

   __import__('pkg_resources').declare_namespace(__name__)

This import is required to override the namespace we've chosen.

Trying it
~~~~~~~~~

Now that we have an empty, but working plugin, you can try to `develop` it.
Developing it means that you'll link your current working-in-progress plugin to
the python libraries. This trick allows the developer to be able to work on a
live source code while having some code structured as a plugin.

So, go where your :file:`setup.py` resides and run:

.. code-block:: bash

   python setup.py develop

If everything went well, you should be able to import your module from a python
shell, congrats!



