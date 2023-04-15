![PythonSupport](https://img.shields.io/static/v1?label=python&message=%203.8|%203.9|%203.10|%203.11|%203.12&color=blue?style=flat-square&logo=python)
![PyPI version](https://badge.fury.io/py/xcon.svg?)

- [Introduction](#introduction)
- [Documentation](#documentation)
- [Install](#install)
- [Licensing](#licensing)

# Introduction

Helps retrieve configuration information from aws/boto services such as Ssm's Param Store and Secrets Manager,
with the ability the cache a flattened list into a dynamodb table.

Right now this is **pre-release software**, as the dynamo cache table and related need further documentation and testing.

Retrieving values from Param Store and Secrets Manager should work and be relatively fast, as we bulk-grab values
at the various directory-levels that are checked.

**More documentation and testing will be coming soon, for a full 1.0.0 release sometime in the next month or so.**

See **[xcon docs](https://xyngular.github.io/py-xcon/latest/)**.

# Documentation

**[📄 Detailed Documentation](https://xyngular.github.io/py-xcon/latest/)** | **[🐍 PyPi](https://pypi.org/project/xcon/)**

# Install

```bash
# via pip
pip install xcon

# via poetry
poetry add xcon
```

# Licensing

This library is licensed under the "The Unlicense" License. See the LICENSE file.
