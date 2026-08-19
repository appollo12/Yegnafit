#!/usr/bin/env bash
# exit on error
set -o errexit

apt-get update && apt-get install -y tesseract-ocr
pip install --upgrade pip
pip install -r requirements.txt
