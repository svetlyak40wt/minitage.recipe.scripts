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

import logging
import os
import shutil
import re
import stat

import pkg_resources
import zc.buildout.easy_install

from minitage.recipe.egg import egg
from minitage.core.common import get_from_cache, system, splitstrip
parse_entry_point = re.compile(
        '([^=]+)=(\w+(?:[.]\w+)*):(\w+(?:[.]\w+)*)$'
        ).match
re_flags = re.U|re.M|re.S|re.X
template_replacements = {
    re.compile('\\\\t', re_flags): '    ', # \t -> '    '
}
class Recipe(egg.Recipe):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        egg.Recipe.__init__(self,
                            buildout, name, options)
        self.not_filtered = []
        self.arguments = self.options.get('arguments', '')
        self.zap = splitstrip(self.options.get('zap', ''))
        # integration with buildout.minitagificator
        self.for_buildoutscripts = options.get('buildoutscripts', getattr(self, 'for_patchs',False))
        self.initialization = self.options.get('initialization', '')
        self.env_initialization = self.options.get('env_initialization', '')
        self.options_scripts = self.options.get('scripts', '')
        self.entry_points_options = self.options.get('entry-points', '').strip()
        self.interpreter = self.options.get('interpreter', '').strip()
        self.dependent_scripts = bool(self.options.get('dependent-scripts', '').strip())
        template_replacements_opt = self.options.get('template-replacements', '')
        self.template_replacements = template_replacements.copy()
        for k in template_replacements_opt.split('\n'):
            if ' => ' in k:
                rep, value = k.split(' => ')
                self.template_replacements[re.compile(rep, re_flags)] = value

        self.env_file = self.options.get('env-file', '').strip()
        self.bin = self.buildout['buildout'].get('bin-directory',
                                                 os.path.join(os.getcwd(), 'bin'))
        if self.extra_paths:
            self.extra_paths = [p for p in self.extra_paths if os.path.exists(p)]
            options['extra-paths'] = '\n'.join(self.extra_paths)

    parse_entry_point = parse_entry_point

    def update(self):
        return self.install()

    def filter(self, dist, name,
               entry_points_options, arguments,
               console_scripts):
        """
        Filter script creation or not.
        Think that the recipe is also used by minitagificator and we patch zc.buildout.easy_install.Installer.
        We may install everything including buildout itself, with an incopatible python version.
        So, we must take care with a robust filter mecanism!
        """
        # never touch to buildout script if it s not explicit!
        if name in ['zc.buildout', 'buildout']:
            if ('buildout' in console_scripts) \
               or ('zc.buildout' in console_scripts)\
               or self.options.get('eggs').strip() == 'zc.buildout':
                return True
            else:
                return False

        dist_in_eggs = (dist.project_name in self.eggs
                        or (
                            len(
                                [a
                                 for a in self.eggs
                                 if a.startswith('%s==' % dist.project_name)
                                ]
                            ) > 0
                        )
                       )

        if not (name in self.zap):
            if not self.dependent_scripts:
                if (not dist.project_name in self.eggs)\
                and (not name in console_scripts):
                    return False

            if console_scripts:
                if not name in console_scripts:
                    return False

            if (
                ((not entry_points_options)
                 and (not (arguments and not dist_in_eggs))
                 and (not ('scripts' in self.options)))
                or (name in console_scripts)
                or (bool(self.for_buildoutscripts)
                    and (dist.project_name in self.options['eggs']))
                or ('generate_all_scripts' in self.options
                    and not entry_points_options)
            ):
                return True
        return False

    @egg.dependency_resolver_decorator
    def install(self, working_set=None):
        """installs an egg
        """
        self.logger.info('Installing console scripts.')
        arguments = self.arguments
        # install console scripts
        installed_scripts, install_paths = {},[]
        bin = self.bin
        sitepackages = re.sub('bin.*',
                              'lib/python%s/site-packages' % self.executable_version,
                               self.executable)
        scan_paths =[self.buildout['buildout']['develop-eggs-directory'],
                      self.buildout['buildout']['eggs-directory'],
                      sitepackages]  + self.extra_paths
        entry_points = []
        # parse script key
        scripts = self.options_scripts
        entry_points_options = self.entry_points_options
        if isinstance(scripts, str):
            scripts = scripts.split('\n')
            scripts = dict([
                ('=' in s) and s.split('=', 1) or (s, s)
                for s in scripts if s
                ])
        console_scripts = scripts.keys()

        # install needed stuff and get according working set
        sreqs, ws = self.working_set(working_set=working_set)
        reqs = [pkg_resources.Requirement.parse(r) for r in sreqs]
        env = pkg_resources.Environment(scan_paths, python = self.executable_version)
        required_dists = []
        try:
            required_dists = ws.resolve(reqs, env)
        except:
            adists = []
            # try to load from paths
            # when they are versions conflicts, because the main source of them
            # at this stage (and not before) are versions pinned in eggs
            # directlry which we had overidden in buildout.cfg
            for distpath in ws.entries:
                dists = [a
                         for a in pkg_resources.find_distributions(distpath)]
                for dist in dists:
                    if not dist in adists:
                        adists.append(dist)
                        required_dists.append(dist)

        for dist in required_dists:
            if not dist in ws:
                ws.add(dist)
        pypath = [os.path.abspath(p)
                  for p in ws.entries+self.extra_paths
                  if os.path.exists(p)]
        abs_pypath = pypath[:]

        rpypath, rsetup = pypath, ''
        if self._relative_paths:
            rpypath, rsetup = zc.buildout.easy_install._relative_path_and_setup(
                os.path.join(self.bin, 'i_will_be_a_script'),
                pypath,
                self._relative_paths
            )
        else:
            rpypath = "'%s'" % "',\n'".join(rpypath)

        template_vars = {'python': self.executable,
                         'path': rpypath,
                         'rsetup': rsetup,
                         'arguments': arguments,
                         'initialization': self.initialization,
                         'env_initialization': self.env_initialization,
                         }

        # parse entry points key
        for s in [item
                  for item in entry_points_options.split()
                  if item]:
            if s.strip():
                parsed = self.parse_entry_point(s)
                if not parsed:
                    logging.getLogger(self.name).error(
                        "Cannot parse the entry point %s.", s)
                    raise zc.buildout.UserError("Invalid entry point")
                entry = parsed.groups()
                entry_points.append(entry)
                scripts[entry[0]] = entry[0]

        # scan eggs for entry point keys
        consumed_ep = []
        for dist in ws:
            for name in pkg_resources.get_entry_map(dist, 'console_scripts'):
                if self.filter(dist, name,
                               entry_points_options, arguments,
                               console_scripts):
                    scripts.setdefault(name, name)
                    entry_point = dist.get_entry_info('console_scripts', name)
                    #consumed_ep.append(name)
                    entry_points.append(
                        (name, entry_point.module_name,
                         '.'.join(entry_point.attrs))
                        )

        # generate interpreter
        interpreter = self.interpreter
        if interpreter:
            interpreter_vars = self.get_script_vars(template_vars, interpreter)
            inst_script = os.path.join(bin, interpreter)
            installed_scripts[interpreter] = inst_script, py_script_template % template_vars

        if self.env_file:
            env_vars = self.get_script_vars(template_vars, os.path.basename(self.env_file))
            env_vars['path'] = ':'.join(abs_pypath)
            env_script = self.env_file
            if not '/' in self.env_file:
                env_script = os.path.join(bin, self.env_file)
            installed_scripts[env_script] = env_script, env_template % env_vars

        # generate console entry pointts
        for name, module_name, attrs in entry_points:
            sname = name
            if scripts:
                sname = scripts.get(name)
                if sname is None:
                    continue
            entry_point_vars = self.get_script_vars(template_vars, sname)
            entry_point_vars.update(
                {'module_name':  module_name,
                 'attrs': attrs,})
            installed_scripts[sname] = (
                os.path.join(bin, sname),
                entry_point_template % entry_point_vars
            )

        # generate scripts
        option_scripts = self.options_scripts
        # now install classical scripts from the entry script.
        already_installed = [os.path.basename(s) for s in installed_scripts]
        for dist in ws:
            provider = dist._provider
            items = {}
            if dist.has_metadata('scripts'):
                for s in provider.metadata_listdir('scripts'):
                    if not(s in already_installed)\
                       and not(s.endswith('.pyc') or s.endswith('.pyo')):
                        items[s] = provider._fn(provider.egg_info, 'scripts/%s' % s)
            for script in items:
                if self.filter(dist, script,
                               entry_points_options, arguments,
                               console_scripts):
                    # mean to filter by dist, even if the distudoesnt provide
                    # console scripts ;), just add dist.project_name in the
                    # scripts section
                    if dist.project_name in console_scripts:
                        scripts.setdefault(script, script)
                    sname = scripts.get(script, script)
                    # install the script if it exists an entry point which
                    # have generated the same script name with a prefixed cs.
                    destName = sname
                    if sname in installed_scripts:
                        destName = 'cs.%s' % sname
                    script_filename = items[script]
                    inst_script = os.path.join(bin, destName)
                    script_vars = self.get_script_vars(template_vars, destName)
                    script_vars.update({'code': script_filename})
                    code = script_template % script_vars
                    installed_scripts[destName] = inst_script, code

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
        msg = 'There were no scripts found to generate or the recipe did not select any one.'
        if(l):
            msg = 'Generated scripts: \'%s\'.' % (
                "', '".join(l)
            )
        self.logger.info(msg)
        return installed_scripts.keys()


    def get_script_vars(self, base_vars, script_name):
        res = base_vars.copy()
        for var in base_vars:
            overridden_var = '%s-%s' % (script_name, var)
            if overridden_var in self.options:
                res[var] = self.options[overridden_var]
        for key in ['initialization', 'env_initialization', 'arguments']:
            if key in res:
                for rep in self.template_replacements:
                    data = res[key]
                    if isinstance(data, basestring):
                        if rep.search(data):
                            res[key] = rep.sub(self.template_replacements[rep], data)
                    elif isinstance(data, list):
                        for i in range(len(data)):
                            if isinstance(data[i], basestring):
                                if rep.search(data[i]):
                                    res[key][i] = rep.sub(self.template_replacements[rep], data[i])
        return res



script_template = """\
#!%(python)s

# ! GENERATED BY minitage.recipe !
import os
import sys
import subprocess

%(rsetup)s

sys.path[0:0] = [%(path)s ]

%(initialization)s

# EXEC ORGINAL CODE WITHOUT SHEBANG
__doc__  = 'I am generated by minitage.recipe.script recipe'

os.environ['PYTHONPATH'] = ':'.join(sys.path + os.environ.get('PYTHONPATH', '').split(':'))
sys.argv.pop(0)
sys.exit(
    subprocess.Popen(
        [sys.executable, '%(code)s']+sys.argv,
        env=os.environ
    ).wait()
)

"""
env_template = """\
#!/usr/bin/env sh

PYTHONPATH="%(path)s"
export PYTHONPATH

%(env_initialization)s

"""

py_script_template = """\
#!%(python)s
#!!! #GENERATED VIA MINITAGE.recipe !!!

import sys

%(rsetup)s

sys.path[0:0] = [ %(path)s ]

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

%(rsetup)s

sys.path[0:0] = [ %(path)s ]

%(initialization)s

import %(module_name)s

if __name__ == '__main__':
    %(module_name)s.%(attrs)s(%(arguments)s)
"""



def stub():
    pass

# vim:set et sts=4 ts=4 tw=80:
