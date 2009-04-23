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
        self.logger.info('Start checkouts')
        for url, url_infos in self.urls.items():
            dest = url_infos.get('directory')
            if not dest.startswith('/'):
                dest = os.path.join(
                    self.options['location'],
                    dest
                )
            fname = self._download(url=url,
                                   destination=dest,
                                   cache=False)
            self.logger.info('Completed dowbload of %s in %s' % (url, dest))
            directories.append(fname)
        self.logger.info('Finnished checkouts')
        return []

# vim:set et sts=4 ts=4 tw=80:
