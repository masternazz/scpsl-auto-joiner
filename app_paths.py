"""Paths that remain stable in both source and PyInstaller builds."""
import os
import sys


def app_dir():
    # Keep source, debug, and packaged runs on one canonical data store so a
    # server remembered in one build is visible in every later build.
    base = os.environ.get("LOCALAPPDATA")
    if base:
        path = os.path.join(base, "SCP-SL-Auto-Joiner")
        os.makedirs(path, exist_ok=True)
        return path
    if getattr(sys, "frozen", False):
        path = os.path.join(os.path.expanduser("~"), "SCP-SL-Auto-Joiner")
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)
