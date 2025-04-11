#
# © 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
# -----
# File: /Makefile
# Created Date: Wednesday August 16th 2023
# -----
#

VENV           = .venv
VENV_PYTHON    = $(VENV)/bin/python
SYSTEM_PYTHON  = $(or $(shell which python3), $(shell which python))
# If virtualenv exists, use it. If not, find python using PATH
PYTHON         = $(or $(wildcard $(VENV_PYTHON)), $(SYSTEM_PYTHON))
SHELL := /bin/bash

.PHONY: test init

venv/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(SHELL) -c "source $(VENV)/bin/activate; pip install --requirement requirements.txt"

init: venv/bin/activate

clean:
	rm -rf __pycache__
	rm -rf .venv
