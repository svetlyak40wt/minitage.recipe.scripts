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

import copy
import imp
import logging
import os
import re
import shutil
import sys
import subprocess

from minitage.core.common import get_from_cache, system, splitstrip
from minitage.core.unpackers.interfaces import IUnpackerFactory
from minitage.core.fetchers.interfaces import IFetcherFactory
from minitage.core import core

__logger__ = 'minitage.recipe'

def appendVar(var, values, separator='', before=False):
    oldvar = copy.deepcopy(var)
    tmp = separator.join([value for value in values if not value in var])
    if before:
        if not tmp:
            separator = ''
        var = "%s%s%s" % (oldvar, separator,  tmp)
    else:
        if not oldvar:
            separator = ''
        var = "%s%s%s" % (tmp, separator, oldvar)
    return var

class MinitageCommonRecipe(object):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        """__init__.
        The code is voulantary not splitted
        because i want to use this object as an api for the other
        recipes.
        """
        self.logger = logging.getLogger(__logger__)
        self.buildout, self.name, self.options = buildout, name, options
        self.offline = buildout.offline
        self.install_from_cache = self.options.get('install-from-cache', None)

        # url from and scm type if any
        # the scm is one available in the 'fetchers' factory
        self.url = self.options.get('url', None)
        self.urls = self.options.get('urls', '').strip().split('\n')
        self.urls.append(self.url)
        self.urls = [re.sub('/$', '', u) for u in self.urls if u]
        self.scm = self.options.get('scm', None)
        self.revision = self.options.get('revision', None)
        self.scm_args = self.options.get('scm-args', None)

        # update with the desired env. options
        if 'environment' in options:
            lenv = buildout.get(options['environment'].strip(), {})
            for key in lenv:
                os.environ[key] = lenv[key]
        
        # maybe md5
        self.md5 = self.options.get('md5sum', None)

        # system variables
        self.uname = sys.platform
        # linuxXXX ?
        if 'linux' in self.uname:
            self.uname = 'linux'
        self.cwd = os.getcwd()
        self.minitage_directory = os.path.abspath(
            os.path.join(self.buildout['buildout']['directory'], '..', '..')
        )
        # destination
        options['location'] = options.get('location',
                                          os.path.join(
                                              buildout['buildout']['parts-directory'],
                                              options.get('name', self.name)
                                          )
                                         )
        self.prefix = options['location']

        # configure script for cmmi packages
        self.configure = options.get('configure', 'configure')
        # prefix separtor in ./configure --prefix%SEPARATOR%path
        self.prefix_separator = options.get('prefix-separator', '=')
        if self.prefix_separator == '':
            self.prefix_separator = ' '
        self.prefix_option = self.options.get('prefix-option',
                                              '--prefix%s' % self.prefix_separator)
        # if we are installing in minitage, try to get the
        # minibuild name and object there.
        self.str_minibuild = os.path.split(self.cwd)[1]
        self.minitage_section = {}

        # system/libraries dependencies
        self.minitage_dependencies = []
        # distutils python stuff
        self.minitage_eggs = []

        # compilation flags
        self.includes = splitstrip(self.options.get('includes', ''))
        self.includes += splitstrip(self.options.get('includes-dirs', ''))
        self.libraries = splitstrip(self.options.get('library-dirs', ''))
        self.libraries_names = ' '
        for l in self.options.get('libraries', '').split():
            self.libraries_names += '-l%s ' % l
        self.rpath = splitstrip(self.options.get('rpath', ''))

        # Defining the python interpreter used to install python stuff.
        # using the one defined in the key 'executable'
        # fallback to sys.executable or
        # python-2.4 if self.name = site-packages-2.4
        # python-2.5 if self.name = site-packages-2.5
        self.executable = os.path.abspath(options.get('executable', sys.executable))
        if options.get('python'):
            self.executable = self.buildout.get(
                options['python'].strip(), 
                {}).get('executable')
        if not 'executable' in options:
            # if we are an python package
            # just get the right interpreter for us.
            # and add ourselves to the deps
            # to get the cflags/ldflags in env.
            #
            for pyver in core.PYTHON_VERSIONS:
                if self.name == 'site-packages-%s' % pyver:
                    interpreter_path = os.path.join(
                        self.minitage_directory,
                        'dependencies', 'python-%s' % pyver, 'parts',
                        'part'
                    )
                    self.executable = os.path.join(
                        interpreter_path, 'bin', 'python'
                    )
                    self.minitage_dependencies.append(interpreter_path)
                    self.includes.append(
                        os.path.join(
                            interpreter_path,
                            'include',
                            'python%s' % pyver
                        )
                    )

        # which python version are we using ?
        self.executable_version = os.popen(
            '%s -c "%s"' % (
                self.executable ,
                'import sys;print sys.version[:3]'
            )
        ).read().replace('\n', '')

        # site-packages defaults
        self.site_packages = 'site-packages-%s' % self.executable_version
        self.site_packages_path = self.options.get(
            'site-packages',
            os.path.join(
                self.buildout['buildout']['directory'],
                'parts',
                self.site_packages)
        )

        # If 'download-cache' has not been specified,
        # fallback to [buildout]['downloads']
        buildout['buildout'].setdefault(
            'download-cache',
            buildout['buildout'].get(
                'download-cache',
                os.path.join(
                    buildout['buildout']['directory'],
                    'downloads'
                )
            )
        )

        # separate archives in downloaddir/minitage
        self.download_cache = os.path.join(
            buildout['buildout']['directory'],
            buildout['buildout'].get('download-cache'),
            'minitage'
        )

        # do we install cextension stuff
        self.build_ext = self.options.get('build-ext', '')

        # patches stuff
        self.patch_cmd = self.options.get(
            'patch-binary',
            'patch'
        ).strip()

        self.patch_options = ' '.join(
            self.options.get(
                'patch-options', '-p0'
            ).split()
        )
        self.patches = self.options.get('patches', '').split()
        # conditionnaly add OS specifics patches.
        self.patches.extend(
            splitstrip(
                self.options.get(
                    '%s-patches' % (self.uname.lower()),
                    ''
                )
            )
        )

        # if gmake is setted. taking it as the make cmd !
        # be careful to have a 'gmake' in your path
        # we have to make it only in non linux env.
        # if wehave gmake setted, use gmake too.
        gnumake = 'make'
        if self.buildout.get('part', {}).get('gmake', None)\
           and self.uname not in ['cygwin', 'linux']:
            gnumake = 'gmake'
        self.make_cmd = self.options.get('make-binary', gnumake).strip()
        self.make_options = self.options.get('make-options', '').strip()

        # what we will install.
        # if 'make-targets'  present, we get it line by line
        # and all target must be specified
        # We will default to make '' and make install
        self.make_targets = splitstrip(
            self.options.get(
                'make-targets',
                ' '
            )
            , '\n'
        )
        if not self.make_targets:
            self.make_targets = ['']

        self.install_targets =  splitstrip(
            self.options.get(
                'make-install-targets',
                'install'
            )
            , '\n'
        )

        # configuration options
        self.configure_options = ' '.join(
            splitstrip(
                self.options.get(
                    'configure-options',
                    '')
            )
        )
        # conditionnaly add OS specifics patches.
        self.configure_options += ' %s' % (
            self.options.get('configure-options-%s' % (
                self.uname.lower()), '')
        )

        # path we will put in env. at build time
        self.path = splitstrip(self.options.get('path', ''))

        # pkgconfigpath
        self.pkgconfigpath = splitstrip(self.options.get('pkgconfigpath', ''))

        # python path
        self.pypath = [self.buildout['buildout']['directory'],
                       self.options['location']]
        self.pypath.extend(self.pypath)
        self.pypath.extend(
            splitstrip(
                self.options.get('pythonpath', '')
            )
        )

        # tmp dir
        self.tmp_directory = os.path.join(
            buildout['buildout'].get('directory'),
            '__minitage__%s__tmp' % name
        )

        # build directory
        self.build_dir = self.options.get('build-dir', None)

        # minitage specific
        # we will search for (priority order)
        # * [part : minitage-dependencies/minitage-eggs]
        # * a [minitage : deps/eggs]
        # * the minibuild dependencies key.
        # to get the needed dependencies and put their
        # CFLAGS / LDFLAGS / RPATH / PYTHONPATH / PKGCONFIGPATH
        # into the env.
        if 'minitage' in buildout:
            self.minitage_section = buildout['minitage']

        self.minitage_section['dependencies'] = '%s %s' % (
                self.options.get('minitage-dependencies', ' '),
                self.minitage_section.get('dependencies', ' '),
        )

        self.minitage_section['eggs'] = '%s %s' % (
                self.options.get('minitage-eggs', ' '),
                self.minitage_section.get('eggs', ' '),
        )

        # try to get dependencies from the minibuild
        #  * add them to deps if dependencies
        #  * add them to eggs if they are eggs
        # but be non bloquant in errors.
        self.minibuild = None
        self.minimerge = None
        minibuild_dependencies = []
        minibuild_eggs = []
        self.minitage_config = os.path.join(
            self.minitage_directory, 'etc', 'minimerge.cfg')
        try:
            self.minimerge = core.Minimerge({
                'nolog' : True,
                'config': self.minitage_config
                }
            )
        except:
            message = 'Problem when intializing minimerge '\
                    'instance with %s config.'
            self.logger.debug(message % self.minitage_config)

        try:
            self.minibuild = self.minimerge._find_minibuild(
                self.str_minibuild
            )
        except:
            message = 'Problem looking for \'%s\' minibuild'
            self.logger.debug(message % self.str_minibuild)

        if self.minibuild:
            for dep in self.minibuild.dependencies :
                m = None
                try:
                    m = self.minimerge._find_minibuild(dep)
                except Exception, e:
                    message = 'Problem looking for \'%s\' minibuild'
                    self.logger.debug(message % self.str_minibuild)
                if m:
                    if m.category == 'eggs':
                        minibuild_eggs.append(dep)
                    if m.category == 'dependencies':
                        minibuild_dependencies.append(dep)

        self.minitage_dependencies.extend(
            [os.path.abspath(os.path.join(
                self.minitage_directory,
                'dependencies',
                s,
                'parts',
                'part'
            )) for s in splitstrip(
                self.minitage_section.get('dependencies', '')
            ) + minibuild_dependencies ]
        )

        self.minitage_eggs.extend(
            [os.path.abspath(os.path.join(
                self.minitage_directory,
                'eggs', s, 'parts', self.site_packages,
            )) for s in splitstrip(
                self.minitage_section.get('eggs', '')
            ) + minibuild_eggs]
        )

        # sometime we install system libraries as eggs because they depend on
        # a particular python version !
        # There is there we suceed in getting their libraries/include into
        # enviroenmment by dealing with them along with classical
        # system dependencies.
        for s in self.minitage_dependencies + self.minitage_eggs:
            self.includes.append(os.path.join(s, 'include'))
            self.libraries.append(os.path.join(s, 'lib'))
            self.rpath.append(os.path.join(s, 'lib'))
            self.pkgconfigpath.append(os.path.join(s, 'lib', 'pkgconfig'))
            self.path.append(os.path.join(s, 'bin'))
            self.path.append(os.path.join(s, 'sbin'))

        for s in self.minitage_eggs \
                 + [self.site_packages_path] \
                 + [self.buildout['buildout']['eggs-directory']] :
            self.pypath.append(s)

        # cleaning if we have a prior compilation step.
        if os.path.isdir(self.tmp_directory):
            self.logger.info(
                'Removing pre existing '
                'temporay directory: %s' % (
                    self.tmp_directory)
            )
            shutil.rmtree(self.tmp_directory)


    def _choose_configure(self, compile_dir):
        """configure magic to runne with
        exotic configure systems.
        """
        if self.build_dir:
            if not os.path.isdir(self.build_dir):
                os.makedirs(self.build_dir)
        else:
            self.build_dir = compile_dir

        configure = os.path.join(compile_dir, self.configure)
        if not os.path.isfile(configure) \
           and (not 'noconfigure' in self.options):
            self.logger.error('Unable to find the configure script')
            raise core.MinimergeError('Invalid package contents, '
                                      'there is no configure script.')

        return configure

    def _configure(self, configure):
        """Run configure script.
        Argument
            - configure : the configure script
        """
        cwd = os.getcwd()
        os.chdir(self.build_dir)
        if not 'noconfigure' in self.options:
            self._system(
                    '%s %s%s %s' % (
                        configure,
                        self.prefix_option,
                        self.prefix,
                        self.configure_options
                    )
                )
        os.chdir(cwd)

    def _make(self, directory, targets):
        """Run make targets except install."""
        cwd = os.getcwd()
        os.chdir(directory)
        for target in targets:
            try:
                self._system('%s %s %s' % (self.make_cmd, self.make_options, target))
            except Exception, e:
                message = 'Make failed for targets: %s' % targets
                raise core.MinimergeError(message)
        os.chdir(cwd)

    def _make_install(self, directory):
        """"""
        # moving and restoring if problem :)
        cwd = os.getcwd()
        os.chdir(directory)
        tmp = '%s.old' % self.prefix
        if os.path.isdir(self.prefix):
            shutil.move(self.prefix, tmp)

        if not 'noinstall' in self.options:
            try:
                os.makedirs(self.prefix)
                self._call_hook('pending-make-install-hook')
                self._make(directory, self.install_targets)
            except Exception, e:
                shutil.rmtree(self.prefix)
                shutil.move(tmp, self.prefix)
                raise core.MinimergeError('Install failed:\n\t%s' % e)
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        os.chdir(cwd)

    def _download(self, url=None, destination=None,
                  scm=None, revision=None, scm_args=None, cache=True):
        """Download the archive."""
        self.logger.info('Download archive')
        if not url:
            url = self.url

        if not destination:
            destination = self.download_cache

        if destination and not os.path.isdir(destination):
            os.makedirs(destination)

        if scm:
            # set path for scms.
            self._set_path()
            opts = {}

            if not revision:
                revision = self.revision

            if not scm_args:
                scm_args = self.scm_args

            if scm_args:
                opts['args'] = scm_args

            if revision:
                opts['revision'] = revision

            scm_dest = destination
            if cache:
                scm_dir = os.path.join(
                    destination, scm)
                if not os.path.isdir(scm_dir):
                    os.makedirs(scm_dir)
                subdir = url.replace('://', '/').replace('/', '.')
                scm_dest = os.path.join(scm_dir, subdir)

            # fetching now
            if not self.offline:
                ff = IFetcherFactory(self.minitage_config)
                scm = ff(scm)
                scm.fetch_or_update(scm_dest, url, opts)
            else:
                if not os.path.exists(scm_dest):
                    message = 'Can\'t get a working copy from \'%s\''\
                              ' into \'%s\' when we are in offline mode'
                    raise core.MinimergeError(message % (url, scm_dest))
                else:
                    self.logger.info('We assumed that \'%s\' is the result'
                                     ' of a check out as'
                                     ' we are in offline mode.' % scm_dest
                                    )
            return scm_dest

        else:
            return get_from_cache(
                url,
                destination,
                self.logger,
                self.md5,
                self.offline,
            )

    def _set_py_path(self, ws=None):
        """Set python path.
        Arguments:
            - ws : setuptools WorkingSet
        """
        self.logger.info('Setting path')
        # setuptool ws maybe?
        if ws:
            self.pypath.extend(ws.entries)
        os.environ['PYTHONPATH'] = ':'.join(self.pypath)


    def _set_path(self):
        """Set path."""
        self.logger.info('Setting path')
        os.environ['PATH'] = appendVar(os.environ['PATH'],
                     self.path\
                     + [self.buildout['buildout']['directory'],
                        self.options['location']]\
                     , ':')


    def _set_pkgconfigpath(self):
        """Set PKG-CONFIG-PATH."""
        self.logger.info('Setting pkgconfigpath')
        os.environ['PKG_CONFIG_PATH'] = ':'.join(
            self.pkgconfigpath
            + os.environ.get('PKG_CONFIG_PATH', '').split(':')
        )

    def _set_compilation_flags(self):
        """Set CFALGS/LDFLAGS."""
        self.logger.info('Setting compilation flags')
        if self.rpath:
            os.environ['LD_RUN_PATH'] = appendVar(
                os.environ.get('LD_RUN_PATH', ''),
                [s for s in self.rpath\
                 if s.strip()]
                + [os.path.join(self.prefix, 'lib')],
                ':'
            )

        if self.libraries:
            darwin_ldflags = ''
            if self.uname == 'darwin':
                # need to cut backward comatibility in the linker
                # to get the new rpath feature present
                # >= osx Leopard
                darwin_ldflags = ' -mmacosx-version-min=10.5.0 '

            os.environ['LDFLAGS'] = appendVar(
                os.environ.get('LDFLAGS',''),
                ['-L%s -Wl,-rpath -Wl,%s' % (s,s) \
                 for s in self.libraries + [os.path.join(self.prefix, 'lib')]
                 if s.strip()]
                + [darwin_ldflags] ,
                ' '
            )

            if self.uname == 'cygwin':
                os.environ['LDFLAGS'] = ' '.join(
                    [os.environ['LDFLAGS'],
                     '-L/usr/lib -L/lib -Wl,-rpath -Wl,/usr/lib -Wl,-rpath -Wl,/lib']
                )
        if self.libraries_names:
            os.environ['LDFLAGS'] = ' '.join([os.environ.get('LDFLAGS', ''), self.libraries_names]).strip()

        if self.minimerge:
            os.environ['CFLAGS']  = ' '.join([
                os.environ.get('CFLAGS', ' '),
                ' ',
                self.minimerge._config._sections.get('minitage.compiler', {}).get('cflags', ''),
                ' ']
            )
            os.environ['LDFLAGS']  = ' '.join([
                os.environ.get('LDFLAGS', ' '),
                ' ',
                self.minimerge._config._sections.get('minitage.compiler', {}).get('ldflags', ''),
                ' ']
            )
            os.environ['MAKEOPTS']  = ' '.join([
                os.environ.get('MAKEOPTS', ' '),
                ' ',
                self.minimerge._config._sections.get('minitage.compiler', {}).get('makeopts', ''),
                ' ']
            )
        if self.includes:
            os.environ['CFLAGS'] = appendVar(
                os.environ.get('CFLAGS', ''),
                ['-I%s' % s \
                 for s in self.includes\
                 if s.strip()]
                ,' '
            )
            os.environ['CPPFLAGS'] = appendVar(
                os.environ.get('CPPFLAGS', ''),
                ['-I%s' % s \
                 for s in self.includes\
                 if s.strip()]
                ,' '
            )
            os.environ['CXXFLAGS'] = appendVar(
                os.environ.get('CXXFLAGS', ''),
                ['-I%s' % s \
                 for s in self.includes\
                 if s.strip()]
                ,' '
            )

    def _unpack(self, fname, directory=None):
        """Unpack something"""
        self.logger.info('Unpacking')
        if not directory:
            directory = self.tmp_directory
        unpack_f = IUnpackerFactory()
        u = unpack_f(fname)
        u.unpack(fname, directory)

    def _patch(self, directory, patch_cmd=None,
               patch_options=None, patches =None):
        """Aplying patches in pwd directory."""
        if not patch_cmd:
            patch_cmd = self.patch_cmd
        if not patch_options:
            patch_options = self.patch_options
        if not patches:
            patches = self.patches
        if patches:
            self.logger.info('Applying patches.')
            cwd = os.getcwd()
            os.chdir(directory)
            for patch in patches:
                system('%s -t %s < %s' %
                       (patch_cmd,
                        patch_options,
                        patch),
                       self.logger
                      )
            os.chdir(cwd)

    def update(self):
        pass

    def _call_hook(self, hook, destination=None):
        """
        This method is copied from z3c.recipe.runscript.
        See http://pypi.python.org/pypi/z3c.recipe.runscript for details.
        """
        cwd = os.getcwd()
        if destination:
            os.chdir(destination)

        if hook in self.options \
           and len(self.options[hook].strip()) > 0:
            self.logger.info('Executing %s' % hook)
            script = self.options[hook]
            filename, callable = script.split(':')
            filename = os.path.abspath(filename)
            module = imp.load_source('script', filename)
            getattr(module, callable.strip())(
                self.options, self.buildout
            )

        if destination:
            os.chdir(cwd)

    def _get_compil_dir(self, directory):
        """Get the compilation directory after creation.
        Basically, the first repository in the directory
        which is not the download cache.
        Arguments:
            - directory where we will compile.
        """
        self.logger.info('Guessing compilation directory')
        contents = os.listdir(directory)
        # remove download dir
        if '.download' in contents:
            del contents[contents. index('.download')]
        return os.path.join(directory, contents[0])

    def _system(self, cmd):
        """Running a command."""
        self.logger.info('Running %s' % cmd)
        p = subprocess.Popen(cmd, env=os.environ, shell=True)
        ret = 0
        try:
            sts = os.waitpid(p.pid, 0)
            ret = sts [1]
        except:
            ret = 1
        # ret = os.system(cmd)
        if ret:
            raise  core.MinimergeError('Command failed: %s' % cmd)

# vim:set et sts=4 ts=4 tw=80:
