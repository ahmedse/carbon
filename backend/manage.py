#!/usr/bin/env python
"""
File: backend/manage.py
Purpose: Django's command-line utility for administrative tasks.

This script allows you to interact with this Django project in various ways,
such as running the development server, applying migrations, or creating superusers.

Usage:
    python manage.py <command> [options]
"""

import os
import sys

def main():
    """
    Run administrative tasks for the Django project.

    This function sets the default settings module and then
    executes the command line utility provided by Django.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()