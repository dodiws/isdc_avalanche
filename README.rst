=========
avalanche
=========

Process and display avalanche risk and forecast data.
Optional Module for ISDC

Quick start
-----------

1. Add "avalanche" to your DASHBOARD_PAGE_MODULES setting like this::

    DASHBOARD_PAGE_MODULES = [
        ...
        'avalanche',
    ]

    If necessary add "avalanche" in (check comment for description): 
        QUICKOVERVIEW_MODULES, 
        MAP_APPS_TO_DB_CUSTOM

    For development in virtualenv add AVALANCHE_PROJECT_DIR path to VENV_NAME/bin/activate:
        export PYTHONPATH=${PYTHONPATH}:\
        ${HOME}/AVALANCHE_PROJECT_DIR

2. To create the avalanche tables:

   python manage.py makemigrations
   python manage.py migrate avalanche --database geodb

