"""
Miracle Hostel Management Portal - Entry Point Alias.
Allows execution via 'python main.py'.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from run import app, run_server

if __name__ == '__main__':
    run_server()

