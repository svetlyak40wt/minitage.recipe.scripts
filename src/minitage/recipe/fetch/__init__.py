#!/usr/bin/env python

# Copyright (C) 2008, Mathieu PASQUET <kiorky@cryptelium.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

__docformat__ = 'restructuredtext en'

import os
from minitage.recipe import common
from minitage.core.common import get_from_cache, system, splitstrip 

class Recipe(common.MinitageCommonRecipe):
    """
    Downloads something from somewhere.
    """

    def update(self):
        """update."""
        self.install()

    def install(self):
        """installs an egg
        """
        directories = []
        for url in self.urls:
            dest = self.prefix
            parts = url.split(' ')
            if len(parts) > 1:
                dest = os.path.join(dest, parts[0])
                url = ' '.join(parts[1:])

            if not os.path.isdir(dest):
                os.makedirs(dest)
            fname = self._download(url=url, scm = self.scm, destination=dest, cache=False)
            directories.append(fname)
        return []

# vim:set et sts=4 ts=4 tw=80:
