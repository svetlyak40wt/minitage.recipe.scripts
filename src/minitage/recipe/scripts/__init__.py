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

import datetime
import imp
import logging
import os
import setuptools.archive_util
import sha
import shutil
import sys
import tempfile
import urllib2
import re
import urlparse
import stat

import pkg_resources
from zc.buildout.easy_install import _safe_arg, _easy_install_cmd
import zc.buildout.easy_install

from minitage.recipe import egg
from minitage.core.fetchers.interfaces import IFetcherFactory
from minitage.core import core
from minitage.core.common import splitstrip, remove_path

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
            self.extra_paths = [p for p in self.extra_paths if os.path.isdir(p)]
            options['extra-paths'] = '\n'.join(self.extra_paths)

    parse_entry_point = re.compile(
        '([^=]+)=(\w+(?:[.]\w+)*):(\w+(?:[.]\w+)*)$'
        ).match

    def update(self):
        self.install()

    def install(self):
        """installs an egg
        """

        self.logger.info('Installing console scripts.')
        # install console scripts
        installed_scripts = []
        reqs = []
        scripts = self.options.get('scripts', None)
        if scripts or scripts is None:
            if scripts is not None:
                scripts = scripts.split()
                scripts = dict([
                    ('=' in s) and s.split('=', 1) or (s, s)
                    for s in scripts
                    ])

            for s in self.options.get('entry-points', '').split():
                parsed = self.parse_entry_point(s)
                if not parsed:
                    logging.getLogger(self.name).error(
                        "Cannot parse the entry point %s.", s)
                    raise zc.buildout.UserError("Invalid entry point")
                reqs.append(parsed.groups())

        reqs.extend(self.eggs)

        # get the source distribution url for the eggs
        ws = self._install_requirements(
            reqs,
            self._dest
        )
        reqs_keys = []
        for itereq in ws.entry_keys.values():
            for req in itereq:
                reqs_keys.append(req)
        lreqs = pkg_resources.parse_requirements('\n'.join(reqs_keys))
        
        sitepackages = re.sub('bin.*', 
                               'lib/python%s/site-packages' % self.executable_version, 
                               self.executable)
        scan_paths = [self.buildout['buildout']['develop-eggs-directory'], 
                      self.buildout['buildout']['eggs-directory'],
                      sitepackages] + self.extra_paths 
        env = pkg_resources.Environment(scan_paths, python = self.executable_version)
        required_dists = ws.resolve(lreqs, env)
        for dist in required_dists:
            if not dist in ws:
                ws.add(dist)

        installed_scripts.extend(
            zc.buildout.easy_install.scripts(
                reqs,
                ws,
                self.executable,
                self.options['bin-directory'],
                scripts=scripts,
                extra_paths=self.extra_paths,
                #interpreter=self.options.get('interpreter'),
                initialization=self.options.get('initialization', ''),
                arguments=self.options.get('arguments', ''),
            )
        )


        interpreter = self.options.get('interpreter', '').strip()
        if interpreter:
            inst_script = os.path.join(
                self.buildout['buildout']['bin-directory'],
                interpreter
            )  
            script = py_script_template % {
                'python': self.executable,
                'path': '\',\n\''.join(
                    [p 
                     for p in ws.entries+self.extra_paths
                     if os.path.isdir(p)]),
                'initialization': self.options.get('initialization', ''),
            } 
            open(inst_script, 'w').writelines(script)
            installed_scripts.append(inst_script)
            os.chmod(inst_script,
                 stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                     | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
                     | stat.S_IROTH | stat.S_IXOTH
                    )
            self.logger.info('Installed interpreter in %s' % inst_script)
        
        option_scripts = self.options.get('scripts', None)
        # now install classical scripts from the entry script.
        for dist in ws:
            if dist.has_metadata('scripts'):
                provider = dist._provider
                items = provider.metadata_listdir('scripts')
                
                for script in items:
                    if not option_scripts or (script in option_scripts):
                        script_filename = provider._fn(
                            provider.egg_info, 'scripts/%s' % script)
                        inst_script = os.path.join(
                            self.buildout['buildout']['bin-directory'],
                            os.path.split(script_filename)[1]
                        )
                        shutil.copy(script_filename, inst_script)
                        # insert working set pypath inside and adapt shebang to
                        # self.executable
                        script_content = open(inst_script, 'r').readlines()
                        if len(script_content)>1:
                            if script_content[0].startswith('#!'):
                                del script_content[0]
                            script = script_template % {
                                'python': self.executable,
                                'path': '\',\n\''.join(
                                    [p 
                                    for p in ws.entries+self.extra_paths
                                    if os.path.isdir(p)]),
                                'code': ''.join(script_content),
                                'initialization': self.options.get(
                                    'initialization', ''),
                            }

                        open(inst_script, 'w').writelines(script)
                        installed_scripts.append(inst_script)
                        os.chmod(inst_script,
                             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                                 | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
                                 | stat.S_IROTH | stat.S_IXOTH
                                )
                        self.logger.info('Installed %s' % inst_script)

        return installed_scripts

script_template = """\
#!%(python)s

# ! GENERATED BY minitage.recipe !
import sys
sys.path[0:0] = ['%(path)s', ]

%(initialization)s

# ORGINAL CODE WITHOUT SHEBANG
__doc__  = 'I am generated by minitage.recipe.script recipe'
%(code)s
"""

py_script_template = """\
#!%(python)s
#!!! #GENERATED VIA MINITAGE.recipe !!!

import sys
    
sys.path[0:0] = [ '%(path)s', ]

%(initialization)s

_interactive = True
if len(sys.argv) > 1:
    import getopt
    _options, _args = getopt.getopt(sys.argv[1:], 'ic:')
    _interactive = False
    for (_opt, _val) in _options:
        if _opt == '-i':
            _interactive = True
        elif _opt == '-c':
            exec _val
            
    if _args:
        sys.argv[:] = _args
        execfile(sys.argv[0])

if _interactive:
    import code
    code.interact(banner="", local=globals())
"""

# vim:set et sts=4 ts=4 tw=80:
