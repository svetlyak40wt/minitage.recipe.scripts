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
