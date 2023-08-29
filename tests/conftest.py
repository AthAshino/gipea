#!/usr/bin/env python
"""Fixtures for testing py-gipea

Instructions
------------
put a ".token" file into your directory containg only the token for gipea

"""

import os

import pytest

from gipea import Gitea


@pytest.fixture
def instance(scope="module"):
    try:
        url = os.getenv("GIPEA_URL")
        token = os.getenv("GIPEA_TOKEN")
        auth = os.getenv("GIPEA_AUTH")
        if not url:
            raise ValueError("No Gitea URL was provided")
        if token and auth:
            raise ValueError("Please provide auth or token_text, but not both")
        g = Gitea(url, token_text=token, auth=auth, verify=False)
        print("Gitea Version: " + g.get_version())
        print("API-Token belongs to user: " + g.get_user().username)
        return g
    except Exception:
        assert (
            False
        ), "Gitea could not load. \
                - Instance running at http://localhost:3000 \
                - Token at .token   \
                    ?"
