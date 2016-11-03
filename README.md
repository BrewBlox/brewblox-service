# BrewPi Service

Flask verison of a BrewPi Service for the next major release.
For our current production version, see [brewpi-www](https://github.com/BrewPi/brewpi-www)

# Install

Install [Python 3.3+](https://www.python.org/downloads/)

Create a new virtualenv for brewpi_service. Easiest way to do this is with
virtualenvwrapper. Install it through pip or your package manager.

For Windows:

    pip install virtualenvwrapper-win
    
For other systems:
    
    apt-get install python-virtualenvwrapper (or yum, ...)
    
    
Create a new virtualenv:

    mkvirtualenv brewpiws
    

Now start using the virtualenv:
    
    workon brewpiws


Install all required dependencies:

    pip install -r requirements.txt
    
# Setup

Create the database:

    python create_db.py
    
# Run

You can run the development server with:

    celery -A brewpi_service.tasks.celery worker -l DEBUG
    python run.py

You can now point your browser to `http://localhost:5000/admin/` for the
administration panel.
