# BrewPi Service

Flask version of the BrewPi Service for the next major release.
For our current production version, see [brewpi-www](https://github.com/BrewPi/brewpi-www)

# Install

Install [Python 3.6](https://www.python.org/downloads/)

Create a new virtualenv for brewpi_service. Easiest way to do this is with
virtualenvwrapper. Install it through pip or your package manager.

For Windows:

    pip install virtualenvwrapper-win
    
For other systems:
    
    apt-get install python-virtualenvwrapper (or yum, ...)
    
    
Create a new virtualenv:

    mkvirtualenv brewpiws -p `which python3.6`
    

Now start using the virtualenv:
    
    workon brewpiws


Install all required dependencies:

    pip install -r requirements.txt
    
# Setup

Tell where the flask app is using:

    export FLASK_APP=brewpi_service/__init__.py

Create the database:

    flask initdb
    
# Run

First, run a worker with (don't forget to re-export FLASK_APP if you've just
opened a new terminal):

    flask rq worker

Then, you can run the development server with:

    flask run

You can now point your browser to `http://localhost:5000/admin/` for the
administration panel.
