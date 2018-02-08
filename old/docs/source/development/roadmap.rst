Roadmap
=======

TO BE REWRITTEN!

Environment setup -- **DONE**
-----------------------------

* Rough draft (framework & libraries exploration)
* Setup TDD & BDD testing
* Setup Coverage



Core concepts -- **DONE**
-------------------------

* Controller definition
* Core Device definition
* Plugin system using :py:mod:`setuptools`
* Administration panel

Device Support -- **DONE**
--------------------------

* Controller Device plugins hooks
* Dynamic administration panel integration

Data Logging
------------

* Core architecture for data logging
* data logging plugin hooks


Object Synchronization
----------------------

* Two-way data binding
* Synchronization layer (using `ControlBox library <https://github.com/m-mcgowan/controlbox-connect-py>`_)
* Data synchronization plugins
* Controller mocking for unit testing


Process Support
---------------

* Process Templates

  * Settings

    * Template configuration
    * Recipe configuration
* Flow modeling (using `django-viewflow <http://viewflow.io>`_?)
* Internal DSL for describing state construction

Rest API
--------

* Expose concepts
* Pluggable endpoints

User management
---------------

* Fine grained permissions
