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

import stat
import re
import os

import pkg_resources
import zc.buildout
from minitage.recipe import scripts

class Recipe(scripts.Recipe):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        scripts.Recipe.__init__(self,
                            buildout, name, options)
        if "config-file" not in options:
            self.logger.error("You need to specify either a paste configuration file")
            raise zc.buildout.UserError("No paste configuration given")

    def install(self):
        """installs an egg
        """
        self.logger.info('Installing scriptsgi script')
        # install console scripts
        bin = self.buildout['buildout']['bin-directory']
        sitepackages = re.sub('bin.*',
                              'lib/python%s/site-packages' % self.executable_version,
                               self.executable)
        scan_paths = [self.buildout['buildout']['develop-eggs-directory'],
                      self.buildout['buildout']['eggs-directory'],
                      sitepackages] + self.extra_paths
        entry_points = []

        # install needed stuff and get according working set
        reqs, ws = self.working_set()
        sreqs, ws = self.working_set()
        reqs = [pkg_resources.Requirement.parse(r) for r in sreqs]
        env = pkg_resources.Environment(scan_paths, python = self.executable_version)
        required_dists = ws.resolve(reqs, env)
        for dist in required_dists:
            if not dist in ws:
                ws.add(dist)
        pypath = [p for p in ws.entries+self.extra_paths if os.path.exists(p)]
        template_vars = {'python': self.executable,
                         'path': '\',\n\''.join(pypath),
                         'arguments': self.options.get('arguments', ''),
                         'config': self.options.get('config-file', ''),
                         'initialization': self.options.get('initialization', ''),}

        option_scripts = self.options.get('scripts', None)
        # now install classical scripts from the entry script.
        if not os.path.isdir(self.options.get('location')):
            os.makedirs(self.options.get('location'))
        path = os.path.abspath(os.path.join(self.options.get('location'), 'wsgi'))
        open(path, 'w').writelines(wsgi_template % template_vars)
        os.chmod(path,
                 stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                 | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
                 | stat.S_IROTH | stat.S_IXOTH
                )
        self.logger.info('Generated script: \'%s\'.' % path)
        return []

wsgi_template = """\
#!%(python)s
#!!! #GENERATED VIA MINITAGE.recipe !!!

import sys
sys.path[0:0] = [ '%(path)s', ]

%(initialization)s

from paste.deploy import loadapp
application = loadapp("config:%(config)s")
"""
# vim:set et sts=4 ts=4 tw=80:
