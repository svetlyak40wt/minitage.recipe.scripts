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

import pkg_resources
from zc.buildout.easy_install import _safe_arg, _easy_install_cmd
import zc.buildout.easy_install

from minitage.recipe import common
from minitage.core import core
from minitage.core.common import splitstrip

class Recipe(common.MinitageCommonRecipe):
    """
    Downloads and installs a distutils Python distribution.
    """
    def __init__(self, buildout, name, options):
        common.MinitageCommonRecipe.__init__(self,
                                    buildout, name, options)

        # caches
        self.eggs_caches = [
            buildout['buildout']['develop-eggs-directory'],
            buildout['buildout']['eggs-directory'],
        ]

        # add distutils or dirty packages too.
        self.eggs_caches.extend(
            self.minitage_eggs
        )

        # real eggs
        self.eggs = splitstrip(self.options.get('eggs', ''))

        # findlinks for eggs
        self.find_links = splitstrip(self.options.get('find-links', ''))

        # zip flag for eggs
        self.zip_safe = False
        if self.options.get('zip-safe', 'true'):
            self.zip_safe = True

        self._env = pkg_resources.Environment(
            self.eggs_caches,
            python=self.executable_version
        )

        # monkey patch zc.buildout loggging
        zc.buildout.easy_install.logger = self.logger
        self.logger.setLevel(5)
        
        # get an instance of the zc.buildout egg installer
        # to search in the cache if we dont have dist yet
        # and etc.
        self.inst = zc.buildout.easy_install.Installer(
            dest=None,
            links=self.find_links,
            executable=self.executable,
            always_unzip=self.zip_safe,
            versions=self.buildout.get('versions', {}),
            path=self.eggs_caches
        )

    def install(self):
        """installs an egg
        """
        self.logger.info('Installing python egg(s).')
        # initialise working directories
        if not os.path.exists(self.tmp_directory):
            os.makedirs(self.tmp_directory)

        # get the source distribution url for the eggs
        if 'eggs' in self.options:
            try:
                self._install_requirements(
                    self.eggs,
                    self.buildout['buildout']['eggs-directory'])
            except Exception, e:
                self.logger.error('Compilation error. The package is left as is at %s where '
                      'you can inspect what went wrong' % self.tmp_directory)
                self.logger.error('Message was:\n\t%s' % e)
                raise core.MinimergeError('Recipe failed, cant install.') 

        # cleaning stuff 
        if os.path.isdir(self.tmp_directory):
            shutil.rmtree(self.tmp_directory)

        return []

    def update(self):
        pass

    def _install_requirements(self, req, dest, working_set=None):
        """Get urls of neccessary eggs to
        achieve a requirement.
        """

        requirements = [self.inst._constrain(
            pkg_resources.Requirement.parse(spec))
            for spec in req]

        if working_set is None:
            ws = pkg_resources.WorkingSet([])
        else:
            ws = working_set

        # Maybe an existing dist is already the best dist that satisfies the
        # requirement
        dists = []
        for requirement in requirements:
            dist, avail = self.inst._satisfied(requirement)
            if dist is None:
                if avail is None:
                    raise zc.buildout.easy_install.MissingDistribution(requirement, ws) 
                dist = self._get_dist(avail, dest, ws)

        for dist in dists:
            ws.add(dist)
            # Check whether we picked a version and, if we did, report it:
            if not (
                dist.precedence == pkg_resources.DEVELOP_DIST
                or
                (len(requirement.specs) == 1
                 and
                 requirement.specs[0][0] == '==')
                ):
                self.logger.debug('Picked: %s = %s',
                             dist.project_name, dist.version)
                if not self.inst._allow_picked_versions:
                    raise zc.buildout.UserError(
                        'Picked: %s = %s' % (dist.project_name, dist.version)
                        )
        return ws

    def _install_distribution(self, dist, dest):
        """Install a setuptool distribution
        into the eggs cache."""
        # where we put the builded  eggs
        tmp = os.path.join(self.tmp_directory, 'eggs')
        if not os.path.isdir(tmp):
            os.makedirs(tmp)
        # maybe extract time
        location = dist.location
        if not os.path.isdir(location):
            location = tempfile.mkdtemp()
            self._unpack(dist.location, location)
            location = self._get_compil_dir(location)
        self.options['compile-directory'] = location
        # maybe patch time
        self._patch(location, dist)
        # compile time
        self._run_easy_install(tmp, ['%s' % location])
        # scan to seach resulted eggs.
        dists = []
        env = pkg_resources.Environment(
            [tmp],
            python=self.executable_version)

        for project in env:
            dists.extend(env[project])

        if not dists:
            raise zc.buildout.UserError("Couldn't install: %s" % dist)

        if len(dists) > 1:
            logger.warn("Installing %s\n"
                        "caused multiple distributions to be installed:\n"
                        "%s\n",
                        dist, '\n'.join(map(str, dists)))
        else:
            d = dists[0]
            if d.project_name != dist.project_name:
                logger.warn("Installing %s\n"
                            "Caused installation of a distribution:\n"
                            "%s\n"
                            "with a different project name.",
                            dist, d)
            if d.version != dist.version:
                logger.warn("Installing %s\n"
                            "Caused installation of a distribution:\n"
                            "%s\n"
                            "with a different version.",
                            dist, d)

        # install eggs in the destination
        result = []
        for d in dists:
            newloc = os.path.join(
                dest,
                os.path.basename(d.location))
            if os.path.exists(newloc):
                if os.path.isdir(newloc):
                    shutil.rmtree(newloc)
                else:
                    os.remove(newloc)
            os.rename(d.location, newloc)

            [d] = pkg_resources.Environment(
                [newloc],
                python=self.executable_version
            )[d.project_name]
            result.append(d)
        
        return result

    def _run_easy_install(self, prefix, specs, caches=None):
        """Install a python egg using easy_install."""
        if not caches:
            caches = []

        args = ('-c', _easy_install_cmd, '-mUNxd', _safe_arg(prefix))
        if self.zip_safe:
            args += ('-Z', )

        args += ('-v', )

        if self.offline:
            args+= ('-H None', )

        for dir in caches + self.eggs_caches:
            args += ('-f %s' % dir,)
        
        # use the common nice functions to make our environement convenient to
        # build packages with dependencies
        self._set_py_path()
        self._set_path()
        self._set_pkgconfigpath()
        self._set_compilation_flags() 

        cwd = os.getcwd()
        for spec in specs:
            largs = args + ('%s' % spec, )
            
            # installing from a path, cd inside
            if spec.startswith('/') and os.path.isdir(spec):
                os.chdir(spec)

            self.logger.info('Running easy_install: \n%s "%s"\n', self.executable, '" "'.join(largs))
            
            try:
                sys.stdout.flush() # We want any pending output first
                if self.uname == 'Darwin':
                    os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.5'
                largs += (dict(os.environ),)
                exit_code = os.spawnle(
                    os.P_WAIT,
                    self.executable,
                    _safe_arg (self.executable),
                    *largs)
                if exit_code > 0:
                    raise
            except Exception, e:
                raise core.MinimergeError('PythonPackage via easy_install Install failed')
           
        os.chdir(cwd)   

    def _get_dist(self, avail, dest, ws):
        """Get a distribution."""
        search_pathes = self.eggs_caches
        if not dest in search_pathes:
            search_pathes = self.eggs_caches + [dest]

        requirement = pkg_resources.Requirement.parse(
            '%s == %s' % (avail.project_name, avail.version)
        )

        self.logger.info('Trying to get  '
                                 'distribution for \'%s\'' % (
                                     avail.project_name
                                 )
                                )

        # We may overwrite distributions, so clear importer
        # cache.
        sys.path_importer_cache.clear()

        # if the dist begin with an url, we try to dnowload it.
        # if available location is a path, add it too to find links
        link = avail.location
        if link.startswith('/'):
            if not os.path.isdir(link):
                link = os.path.dirname(link)
            self.inst._index.add_find_links([link]) 
        source = self.inst._index.obtain(requirement).location
        if not source.startswith('/'):
            filename = self._download(source)
        # or we copy the dist in a temp directory for building it
        else:
            filename = os.path.join(
                self.tmp_directory,
                os.path.basename(source)
            )
            if os.path.isdir(source):
                shutil.copytree(source, filename)
            else:
                shutil.copy(source, filename)

        dist = avail.clone(location=filename)

        if dist is None:
            raise zc.buildout.UserError(
                "Couln't download distribution %s." % avail)

        if dist.precedence == pkg_resources.EGG_DIST:
            # It's already an egg, just fetch it into the dest

            newloc = os.path.join(
                dest, os.path.basename(dist.location))

            if os.path.isdir(dist.location):
                # we got a directory. It must have been
                # obtained locally.  Just copy it.
                shutil.copytree(dist.location, newloc)
            else:

                if self.zip_safe:
                    should_unzip = True
                else:
                    metadata = pkg_resources.EggMetadata(
                        zipimport.zipimporter(dist.location)
                        )
                    should_unzip = (
                        metadata.has_metadata('not-zip-safe')
                        or
                        not metadata.has_metadata('zip-safe')
                        )

                if should_unzip:
                    setuptools.archive_util.unpack_archive(
                        dist.location, newloc)
                else:
                    shutil.copyfile(dist.location, newloc)

            # Getting the dist from the environment causes the
            # distribution meta data to be read.  Cloning isn't
            # good enough.
            dists = pkg_resources.Environment(
                [newloc],
                python=self.executable_version,
                )[dist.project_name]
        else:
            # It's some other kind of dist.  We'll let setup.py
            # make the stuff
            dist = self._install_distribution(dist, dest)

        self._env.scan(search_pathes)
        dist = self._env.best_match(requirement, ws)
        self.logger.info("Got %s.", dist)
        
        return dist

    def _patch(self, location, dist):
        # patch for eggs are based on the project_name
        patch_cmd = self.options.get(
            '%s-patch-binary' % dist.project_name,
            'patch'
        ).strip()

        patch_options = ' '.join(
            self.options.get(
                '%s-patch-options' % dist. project_name, '-p0'
            ).split()
        )
        patches = self.options.get(
            '%s-patches' % dist.project_name,
            '').split()
        # conditionnaly add OS specifics patches.
        patches.extend(
            splitstrip(
                self.options.get(
                    '%s-%s-patches' % (dist.project_name,
                                       self.uname.lower()),
                    ''
                )
            )
        ) 
        common. MinitageCommonRecipe._patch(
            self, location, patch_cmd, patch_options, patches
        )

# vim:set et sts=4 ts=4 tw=80:
