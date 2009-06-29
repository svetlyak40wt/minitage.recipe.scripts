# Copyright (C) 2009, Mathieu PASQUET <kiorky@cryptelium.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the <ORGANIZATION> nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.



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
