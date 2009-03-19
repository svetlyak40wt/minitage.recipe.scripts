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

import logging
import os
import shutil
import re
import stat

import pkg_resources
import zc.buildout.easy_install

from minitage.recipe import egg

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

    parse_entry_point = re.compile(
        '([^=]+)=(\w+(?:[.]\w+)*):(\w+(?:[.]\w+)*)$'
        ).match

    def update(self):
        return self.install()

    def install(self):
        """installs an egg
        """
        self.logger.info('Installing console scripts.')
        # install console scripts
        installed_scripts, install_paths = {},[]
        bin = self.buildout['buildout']['bin-directory']
        sitepackages = re.sub('bin.*',
                              'lib/python%s/site-packages' % self.executable_version,
                               self.executable)
        scan_paths = [self.buildout['buildout']['develop-eggs-directory'],
                      self.buildout['buildout']['eggs-directory'],
                      sitepackages] + self.extra_paths
        entry_points = []
        # parse script key
        scripts = self.options.get('scripts', {})
        if scripts or scripts is None:
            if scripts is not None:
                scripts = scripts.split()
                scripts = dict([
                    ('=' in s) and s.split('=', 1) or (s, s)
                    for s in scripts
                    ])

        # install needed stuff and get according working set
        reqs, ws = self.working_set()
        env = pkg_resources.Environment(scan_paths, python = self.executable_version)
        required_dists = ws.resolve(reqs, env)
        for dist in required_dists:
            if not dist in ws:
                ws.add(dist)
        pypath = [p for p in ws.entries+self.extra_paths if os.path.exists(p)]
        template_vars = {'python': self.executable,
                         'path': '\',\n\''.join(pypath),
                         'arguments': self.options.get('arguments', ''),
                         'initialization': self.options.get('initialization', ''),}

        # parse entry points key
        for s in self.options.get('entry-points', '').split():
            if s.strip():
                parsed = self.parse_entry_point(s)
                if not parsed:
                    logging.getLogger(self.name).error(
                        "Cannot parse the entry point %s.", s)
                    raise zc.buildout.UserError("Invalid entry point")
                entry_points.append(parsed.groups()) 

        # scan eggs for entry point keys
        for req in reqs:
            dist = ws.find(req)
            for name in pkg_resources.get_entry_map(dist, 'console_scripts'):
                entry_point = dist.get_entry_info('console_scripts', name)
                entry_points.append(
                    (name, entry_point.module_name,
                     '.'.join(entry_point.attrs))
                    )

        # generate interpreter
        interpreter = self.options.get('interpreter', '').strip()
        if interpreter:
            inst_script = os.path.join(bin, interpreter)
            installed_scripts[interpreter] = inst_script, py_script_template % template_vars

        # generate console entry pointts
        for name, module_name, attrs in entry_points:
            sname = name
            if scripts:
                sname = scripts.get(name)
                if sname is None:
                    continue
            entry_point_vars = template_vars.copy()
            entry_point_vars.update(
                {'module_name':  module_name,
                 'attrs': attrs,})
            installed_scripts[sname] = os.path.join(bin, sname), entry_point_template % entry_point_vars

        # generate scripts
        option_scripts = self.options.get('scripts', None)
        # now install classical scripts from the entry script.
        already_installed = [os.path.basename(s) for s in installed_scripts]
        for dist in ws:
            if dist.has_metadata('scripts'):
                provider = dist._provider
                items = [s
                         for s in provider.metadata_listdir('scripts')
                         if not s in already_installed]
                for script in items:
                    sname = name
                    if scripts:
                        sname = scripts.get(name)
                        if sname is None:
                            continue
                    if not option_scripts or (script in option_scripts):
                        script_filename = provider._fn(
                            provider.egg_info, 'scripts/%s' % script)
                        inst_script = os.path.join(bin,os.path.split(script_filename)[1])
                        shutil.copy(script_filename, inst_script)
                        # insert working set pypath inside and adapt shebang to
                        # self.executable
                        script_content = open(inst_script, 'r').readlines()
                        if len(script_content)>1:
                            if script_content[0].startswith('#!'):
                                del script_content[0]
                            script_vars = template_vars.copy()
                            script_vars.update({'code': ''.join(script_content)})
                            code = script_template % script_vars
                            sname = scripts.get(script, script)
                            installed_scripts[sname] = inst_script, code

        ls = []
        for script in installed_scripts:
            path, content = installed_scripts[script]
            ls.append(path)
            install_paths.append(path)
            open(path, 'w').writelines(content)
            os.chmod(path,
                     stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                     | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
                     | stat.S_IROTH | stat.S_IXOTH
                    )
        l = installed_scripts.keys()
        l.sort()
        self.logger.info(
            'Generated scripts: \'%s\'.' % (
                "', '".join(l)
            )
        )
        return installed_scripts.keys()

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

entry_point_template = """\
#!%(python)s
#!!! #GENERATED VIA MINITAGE.recipe !!!

import sys
sys.path[0:0] = [ '%(path)s', ]

%(initialization)s
import %(module_name)s

if __name__ == '__main__':
    %(module_name)s.%(attrs)s(%(arguments)s)
"""



def stub():
    pass

# vim:set et sts=4 ts=4 tw=80:
