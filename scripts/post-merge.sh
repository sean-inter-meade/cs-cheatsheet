#!/bin/bash
set -e

uv pip install --target .pythonlibs/lib/python3.11/site-packages -r requirements.txt
