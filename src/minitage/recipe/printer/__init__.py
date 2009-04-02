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

from minitage.recipe import egg
import StringIO

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
        # install needed stuff and get according working set
        reqs, ws = self.working_set()
        s = StringIO.StringIO()
        if 'file' in self.options:
            s = open(self.options['file'], 'w')

        if not ('quiet' in self.options):
            self.logger.info('Maybe put this in a cfg like file ;)')
            print 
            print
        s.write("[versions]\n")
        reqs = []
        for dist in ws:
           reqs.append("%s=%s\n" % (dist.project_name, dist.version))
        reqs.sort()
        s.write(''.join(reqs))
        
        if isinstance(s, file):
            s.close()
        
        if not ('quiet' in self.options):
            if isinstance(s, file):
                print open(self.options['file']).read()
            else:
                print s.getvalue()
        if not ('quiet' in self.options):
            self.logger.info('------------')

        return []

# vim:set et sts=4 ts=4 tw=80:
