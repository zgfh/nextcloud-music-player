"""
Entry point for the NextCloud Music Player application.
"""

from .app import main

if __name__ == '__main__':
    app = main()
    app.main_loop()
