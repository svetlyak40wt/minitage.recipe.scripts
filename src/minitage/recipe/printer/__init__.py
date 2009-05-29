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
import re
import pkg_resources

from minitage.recipe import egg
import StringIO

CUTED_STR = '#--- 8-< 8-<  8-<  8-<  8-<  8-<  8-<  ---'

class Recipe(egg.Recipe):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        egg.Recipe.__init__(self,
                            buildout, name, options)

        options['bin-directory'] = buildout['buildout']['bin-directory']
        self.extra_paths = [
            os.path.join(buildout['buildout']['directory'], p.strip())
            for p in options.get('extra-paths', '').split('\n')
            if p.strip()
            ]
        if self.extra_paths:
            self.extra_paths = [p for p in self.extra_paths if os.path.exists(p)]
            options['extra-paths'] = '\n'.join(self.extra_paths)

    def update(self):
        return self.install()

    def install(self):
        """Dump all eggs versions needed for part.
        """
        self.logger.info('Versions pinned:')
        sitepackages = re.sub('bin.*',
                              'lib/python%s/site-packages' % self.executable_version,
                               self.executable)
        scan_paths = [self.buildout['buildout']['develop-eggs-directory'],
                      self.buildout['buildout']['eggs-directory'],
                      sitepackages] + self.extra_paths
        # install needed stuff and get according working set
        sreqs, ws = self.working_set()
        reqs = [pkg_resources.Requirement.parse(r) for r in sreqs]
        env = pkg_resources.Environment(scan_paths, python = self.executable_version)
        required_dists = ws.resolve(reqs, env)

        if not ('quiet' in self.options):
            self.logger.info('Maybe put this in a cfg like file ;)')
            print CUTED_STR

        s = StringIO.StringIO()
        if 'file' in self.options:
            s = open(self.options['file'], 'w')

        file_content = "\n\n[versions]\n"
        envreqs = []
        for dist in list(set(required_dists)):
           envreqs.append("%s=%s" % (dist.project_name, dist.version))
        envreqs.sort()
        file_content += '\n'.join(envreqs)
        file_content += '\n\n[buildout]\nversions=versions\n\n'
        s.write(file_content)

        if not ('quiet' in self.options):
            print file_content
            print CUTED_STR

        if 'file' in self.options:
            self.logger.info('Generated: %s' % self.options['file'])

        return []

# vim:set et sts=4 ts=4 tw=80:
