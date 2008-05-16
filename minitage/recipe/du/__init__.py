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
import urlparse

from  minitage.core import get_from_cache, system

class Recipe(object):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        self.logger = logging.getLogger(name)
        self.buildout, self.name, self.options = buildout, name, options
        site_packages='site-packages'

        # site-packages defaults to the python version !
        python = options.get('python', buildout['buildout']['python'])

        options['executable'] = buildout[python]['executable']
        if options.has_key('site-packages'):
            site_packages=options['site-packages']
        else:
            site_packages='site-packages-%s' % (
                os.popen(
                    '%s -c "%s"' % (
                        options['executable'],
                        'import sys;print sys.version[:3]'
                    )
                ).read().replace('\n', '')
            )

        options['location'] = os.path.join(
            buildout['buildout']['parts-directory'],
            site_packages
        )

        # If 'download-cache' has not been specified,
        # fallback to [buildout]['downloads']
        buildout['buildout'].setdefault(
            'download-cache',
            buildout['buildout'].get(
                'download-cache',
                os.path.join(
                    buildout['buildout']['directory'], 'downloads'
                )
            )
        )

        # separate python archives in downloaddir/distutils
        self.download_cache = os.path.join(
            buildout['buildout']['directory'],
            buildout['buildout'].get('download-cache'),
            'distutils'
        )
        self.offline = buildout['buildout'].get('install-from-cache')

    def set_py_path(self):
        """Set python path."""
        pypath = self.options.get('pythonpath', '').split()
        os.environ['PYTHONPATH']=":".join(
            pypath,
            self.buildout['buildout']['directory'],
            self.options['location'],
            os.environ.get('PYTHONPATH',''),
        )
        sys.path += pypath


    def set_path(self):
        """Set path."""
        os.environ['PATH']=":".join(
            self.options.get('path', '').split(),
            self.buildout['buildout']['directory'],
            self.options['location'],
            os.environ.get('PATH', '')
        )

    def set_pkgconfigpath(self):
        """Set PKG-CONFIG-PATH."""
        os.environ['PKG_CONFIG_PATH']=":".join(
            self.options.get('pkg-config-path', '').split(),
            os.environ.get('PKG_CONFIG_PATH', '')
        )

    def set_compilation_flags(self):
        """Set CFALGS/LDFLAGS."""

    def install(self):
        """
        installs a python package using distutils
            - You can play with pre-setup-hook and post-setup-hook to make as in
            hexagonit.cmmi
            - You can apply patches, and more over specificly to your os with
            those 4 options in buildout:
                - freebsd-patches
                - linux-patches
                - patches
                - darwin-patches """

        dest = self.options['location']
        url = self.options['url']
        build_ext = self.options.get('build_ext','')
        fname = get_from_cache(url,
                             self.name,
                             self.download_cache,
                             self.offline)

        patch_cmd = self.options.get(
            'patch-binary',
            'patch'
        ).strip()
        patch_options = ' '.join(self.options.get(
            'patch-options', '-p0').split()
        )
        patches = self.options.get('patches', '').split()
        uname=os.uname()[0]
        # conditionnaly add OS specifics patches.
        patches+=self.options.get('%s-patches'%(uname.lower()), '').split()

        tmp = tempfile.mkdtemp('buildout-' + self.name)
        self.logger.info('Unpacking and configuring')
        setuptools.archive_util.unpack_archive(
            fname,
            tmp
        )
        here = os.getcwd()
        if not os.path.exists(dest):
            os.makedirs(dest)

        try:
            cmds=[]
            executable=self.options.get(
                'executable',
                sys.executable
            )
            os.chdir(tmp)
            try:
                if not os.path.exists('setup.py'):
                    entries = os.listdir(tmp)
                    if len(entries) == 1:
                        os.chdir(entries[0])
                    else:
                        raise core.MinimergeError("Couldn't find setup.py")


                # set python path
                self.set_py_path()

                # set path
                self.set_path()

                # set pkgconfigpath
                self.set_pkgconfigpath()

                if self.options.get('rpath',None):
                    os.environ['LDFLAGS']=os.environ.get('LDFLAGS',' ')+" "+" ".join([" -Wl,-rpath -Wl,%s " %s for s in self.options['rpath'].split()])
                    os.environ['LD_RUN_PATH']=os.environ.get('LD_RUN_PATH',' ')+":".join(["%s" %s for s in self.options['rpath'].split()])

                if self.options.get('libraries',None):
                    os.environ['LDFLAGS']= os.environ.get('LDFLAGS',' ')+" "+" ".join([" -L%s " %s for s in self.options['libraries'].split()])

                if self.options.get('includes',None):
                    os.environ['CFLAGS'] =os.environ.get('CFLAGS',' ')   +" "+ " ".join([" -I%s "   %s for s in self.options['includes'].split()])
                    os.environ['CPPFLAGS']=os.environ.get('CPPFLAGS',' ')+" "+" ".join([" -I%s " %s for s in self.options['includes'].split()])
                    os.environ['CXXFLAGS']=os.environ.get('CXXFLAGS',' ')+" "+" ".join([" -I%s " %s for s in self.options['includes'].split()])

                if patches:
                     self.logger.info('Applying patches')
                     for patch in patches:
                         system('%s %s < %s' % (patch_cmd, patch_options, patch),self.logger)

                if 'pre-setup-hook' in self.options and len(self.options['pre-setup-hook'].strip()) > 0:
                    self.logger.info('Executing pre-setup-hook')
                    self.call_script(self.options['pre-setup-hook'])

                if build_ext or self.options.get('rpath',None) or self.options.get('libraries',None) or self.options.get('includes',None):
                    cmds.append('"%s" setup.py build_ext %s' % (executable,build_ext.replace('\n',' ')))

                cmds.append('"%s" setup.py build' % (executable))
                #cmds.append( '''"%s" setup.py install --install-purelib="%s" --install-platlib="%s"''' % (executable, dest, dest))
                cmds.append( '''"%s" setup.py install --install-purelib="%s" --install-platlib="%s" --prefix=%s''' % (executable, dest, dest,self.buildout['buildout']['directory']))
                for cmd in cmds:
                    system(cmd,self.logger)

                if 'post-setup-hook' in self.options and len(self.options['post-setup-hook'].strip()) > 0:
                    self.logger.info('Executing post-setup-hook')
                    self.call_script(self.options['post-setup-hook'])

            finally:
                os.chdir(here)
        except:
            os.rmdir(dest)
            raise

        return []

    def update(self):
        pass

    def call_script(self, script):
        """This method is copied from z3c.recipe.runscript.

        See http://pypi.python.org/pypi/z3c.recipe.runscript for details.
        """
        filename, callable = script.split(':')
        filename = os.path.abspath(filename)
        module = imp.load_source('script', filename)
        # Run the script with all options
        getattr(module, callable.strip())(self.options, self.buildout)
