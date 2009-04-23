#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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
import distutils
import os
import shutil
import sys
import re
import tarfile
import tempfile
import subprocess
import py_compile
import logging

from ConfigParser import NoOptionError
import iniparse as ConfigParser
import pkg_resources
import setuptools.archive_util
from setuptools.command import easy_install
import zc.buildout.easy_install

from minitage.recipe import common
from minitage.core.fetchers.interfaces import IFetcherFactory
from minitage.core import core
from minitage.core.common import splitstrip

PATCH_MARKER = 'ZMinitagePatched'
orig_versions_re = re.compile('-*%s.*' % PATCH_MARKER, re.U|re.S)

def get_orig_version(version):
    if not version: version = ''
    return orig_versions_re.sub('', version)

def get_requirement_version(requirement):
    patched_egg, version = False, None
    for spec in requirement.specs:
        for item in spec:
            if PATCH_MARKER in item:
                version = item
                patched_egg = True
    return version, patched_egg

def merge_extras(a, b):
    a.extras += b.extras
    a.extras = tuple(set(a.extras))
    return a

def merge_specs(a, b):
    a.specs += b.specs
    a.specs = list(set(a.specs))
    return a

def redo_pyc(egg, executable=sys.executable, environ=os.environ):
    print "Location : %s" % egg
    logger = logging.getLogger('minitage.recipe PyCompiler')
    if not os.path.isdir(egg):
        return

    # group sort, and uniquify files to compile
    files = {}
    for dirpath, dirnames, filenames in os.walk(egg):
        ffilenames = [filename for filename in filenames if filename.endswith('.py')]
        if dirpath in files:
            files[dirpath] += ffilenames
        else:
            files[dirpath] = ffilenames

    tocompile = []
    for dirpath in files:
        for filename in tuple(set(files[dirpath])):
            filepath = os.path.join(dirpath, filename)
            # OK, it looks like we should try to compile.
            # Remove old files.
            for suffix in 'co':
                if os.path.exists(filepath+suffix):
                    os.remove(filepath+suffix)
            tocompile.append(filepath)

    try:
        # Compile under current optimization
        args = [zc.buildout.easy_install._safe_arg(sys.executable)]
        args.extend(['-m', 'py_compile'])
        subprocess.Popen(args+tocompile, env=environ).wait()
        if __debug__:
        # Recompile under other optimization. :)
            args.insert(1, '-O')
            subprocess.Popen(args+tocompile, env=environ).wait()
    except py_compile.PyCompileError, error:
        logger.warning("Couldn't compile %s", filepath)

class Recipe(common.MinitageCommonRecipe):
    """
    Downloads and installs a distutils Python distribution.
    """

    def __init__(self, buildout, name, options):
        common.MinitageCommonRecipe.__init__(self,
                                    buildout, name, options)
        # override recipe default and download into a subdir
        # minitage-cache/eggs
        # separate archives in downloaddir/minitage
        options['bin-directory'] = buildout['buildout']['bin-directory']
        self.download_cache = os.path.abspath(
            os.path.join(self.download_cache, 'eggs')
        )

        if not os.path.isdir(self.download_cache):
            os.makedirs(self.download_cache)

        self.extra_paths = [
            os.path.join(buildout['buildout']['directory'], p.strip())
            for p in options.get('extra-paths', '').split('\n')
            if p.strip()
            ]

        self.versions = buildout.get(
            buildout['buildout'].get('versions', '').strip(),
            {}
        )
        self.buildout_versions = buildout['buildout'].get('versions', '').strip()
        if not self.buildout_versions in buildout:
            self.buildout_versions = None
        # compatibility with zc.recipe.egg:
        relative_paths = options.get(
            'relative-paths',
            buildout['buildout'].get('relative-paths', 'false')
        )
        if relative_paths == 'true':
            options['buildout-directory'] = buildout['buildout']['directory']
            self._relative_paths = options['buildout-directory']
        else:
            self._relative_paths = ''
        # end compat

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
        self.eggs = [i\
                     for i in self.options.get('eggs', '').split('\n')\
                     if i]

        self.eggs += [i\
                     for i in self.options.get('egg', '').split('\n')\
                     if i]
        if not self.eggs:
            eggs = [name]
        # findlinks for eggs
        self.find_links = splitstrip(self.options.get('find-links', ''))
        self.find_links += splitstrip(self.buildout['buildout'].get('find-links', ''))

        #index replacement
        self.index = self.options.get('index',
                                     self.buildout['buildout'].get('index', None)
                                     )

        # zip flag for eggs
        self.zip_safe = False
        if self.options.get('zip-safe', 'true'):
            self.zip_safe = True

        # sharing env with Installer for performance optimization
        #self._env = pkg_resources.Environment(
        #    self.eggs_caches,
        #    python=self.executable_version
        #)

        # monkey patch zc.buildout loggging
        self.logger.setLevel(
            zc.buildout.easy_install.logger.getEffectiveLevel()
        )
        zc.buildout.easy_install.logger = self.logger

        # get an instance of the zc.buildout egg installer
        # to search in the cache if we dont have dist yet
        # and etc.
        if self.offline:
            self.index = 'file://%s' % self.eggs_caches[0]
            self.find_links = []
        self.inst = zc.buildout.easy_install.Installer(
            dest=None,
            index=self.index,
            links=self.find_links,
            executable=self.executable,
            always_unzip=self.zip_safe,
            versions=self.buildout.get('versions', {}),
            path=self.eggs_caches,
            newest = self.buildout.newest,
            allow_hosts=self.options.get('allow-hosts',
                                         self.buildout.get('allow-hosts', {})
                                         ),
        )
        # FORCING NEWEST MODE !!! see Installer code...
        self.inst._newest = self.buildout.newest
        self._dest= os.path.abspath(
            self.buildout['buildout']['eggs-directory']
        )

        # intiatiate environement cache
        self.scan()

    def update(self):
        """update."""
        self.install()

    def install(self):
        """installs an egg
        """
        reqs, working_set = self.working_set()
        return []

    def working_set(self, extras=None, working_set=None, dest=None):
        """real recipe method but renamed for convenience as
        we do not return a path tuple but a workingset
        """
        self.logger.info('Installing python egg(s).')
        requirements = None
        if not extras:
            extras = []
        elif isinstance(extras, tuple):
            extras = list(extras)

        if not dest:
            dest = self._dest

        for i, r in enumerate(copy.deepcopy(extras)):
            if not isinstance(r, pkg_resources.Requirement):
                extras[i] = pkg_resources.Requirement.parse(r)

        # initialise working directories
        if not os.path.exists(self.tmp_directory):
            os.makedirs(self.tmp_directory)
        # get the source distribution url for the eggs
        try:
            # if we have urls
            # downloading each, scanning its stuff and giving it to easy install
            requirements, working_set = self.install_static_distributions(working_set,
                                                                          requirements=requirements,
                                                                          dest=dest)
            # installing classical requirements
            if self.eggs or extras:
                drequirements, working_set = self._install_requirements(
                    self.eggs + extras,
                    dest,
                    working_set=working_set)
                requirements.extend(drequirements)
        except Exception, e:
            raise
            self.logger.error('Compilation error. The package is'
                              ' left as is at %s where '
                              'you can inspect what went wrong' % (
                                  self.tmp_directory))
            self.logger.error('Message was:\n\t%s' % e)
            raise core.MinimergeError('Recipe failed, cant install.')

        # cleaning stuff
        if os.path.isdir(self.tmp_directory):
            shutil.rmtree(self.tmp_directory)
        if not dest in self.eggs_caches:
            self.eggs_caches.append(dest)

        # old code, keeping atm
        #env = pkg_resources.Environment(self.eggs_caches,
        #                                python=self.executable_version)

        return ['%s' % r for r in requirements], working_set

    def install_static_distributions(self,
                                     working_set=None,
                                     urls=None,
                                     requirements=None,
                                     dest=None):
        """Install distribution distribued somewhere as archives."""
        if not working_set:
            working_set = pkg_resources.WorkingSet([])
        if not requirements:
            requirements = []
        if not dest:
            dest = self._dest
        # downloading
        if not urls:
            urls = self.urls
        for i, url in enumerate(urls):
            fname = self._download(url=url)
            dists = []
            # if it is a repo, making a local copy
            # and scan its distro
            if os.path.isdir(fname):
                self._call_hook('post-download-hook', fname)
                tmp = os.path.join(self.tmp_directory, 'wc')
                f = IFetcherFactory(self.minitage_config)
                for fetcher in f.products:
                    dot = getattr(f.products[fetcher](),
                                  'metadata_directory', None)
                    if dot:
                        if os.path.exists(os.path.join(fname, dot)):
                            shutil.copytree(fname, tmp)
                            break
                # go inside dist and scan for setup.py
                self.options['compile-directory'] = tmp
                self._call_hook('post-checkout-hook', fname)
                # build the egg distribution in there.
                cwd = os.getcwd()
                os.chdir(tmp)
                self._sanitizeenv(working_set)
                ret = os.system('%s setup.py sdist' % sys.executable)
                os.chdir(cwd)
                sdists = os.path.join(tmp, 'dist')
                for item in os.listdir(sdists):
                    dists.extend( [e \
                                   for e \
                                   in setuptools.package_index.distros_for_filename(
                                       os.path.join(sdists,item)
                                   )]
                                )
            else:
                # scan for the distribution archive infos.
                dists = [e \
                         for e \
                         in setuptools.package_index.distros_for_filename(
                             fname)]

            # sort duplicates
            paths = []
            toinstall = []
            for dist in dists:
                if not dist.location in [d.location\
                                         for d in toinstall]:
                    toinstall.append(dist)

            for dist in toinstall:
                requirement = None
                if dist.version:
                    requirement = pkg_resources.Requirement.parse(
                        '%s == %s' % (dist.project_name, dist.version)
                    )
                else:
                    requirement = pkg_resources.Requirement.parse(
                        dist.project_name
                    )
                # force env rescanning if egg was not there at init.
                self.scan([dest])
                sdist, savail = None, None
                try:
                    sdist, savail, _ = self._satisfied(requirement, working_set)
                except zc.buildout.easy_install.MissingDistribution:
                    pass
                if sdist:
                    msg = 'If you want to rebuild, please do \'rm -rf %s\''
                    self.logger.info(msg % sdist.location)
                    sdist.activate()
                    working_set.add(sdist)
                else:
                    already_installed_dependencies = {}
                    for r in requirements:
                        already_installed_dependencies[r.project_name] = r
                    installed_dist = self._install_distribution(
                        dist,
                        dest,
                        working_set,
                        already_installed_dependencies)
                    installed_dist.activate()
                    working_set.add(installed_dist)
                    requirements.append(dist.as_requirement())
                # for buildout to use it !
                self._pin_version(dist.project_name, dist.version)
                self.versions[dist.project_name] = dist.version
                self.add_dist(dist)
        return requirements, working_set

    def scan(self, scanpaths=None):
        if not scanpaths:
            scanpaths = self.eggs_caches
        self.inst._env.scan(scanpaths)

    def _search_sdist(self, requirement, working_set):
        env = pkg_resources.Environment(
            [self.download_cache],
            python=self.executable_version)
        sdists = []
        dist = None
        # try to scan source distribtions
        for file in os.listdir(self.download_cache):
            path = os.path.join(self.download_cache, file)
            if os.path.isfile(path):
                sdists.extend(
                    setuptools.package_index.distros_for_url(path))
            for distro in sdists:
                env.add(distro)
        # last try, testing sources (very useful for offline mode
        # or when your egg is not indexed)
        avail = env.best_match(requirement, working_set)
        if not avail:
            raise zc.buildout.easy_install.MissingDistribution(
                    requirement, working_set)
        if avail:
            msg = 'We found a source distribution for \'%s\' in \'%s\'.'
            self.logger.info(msg % (requirement, avail.location))
        return avail

    def _satisfied(self, requirement, working_set):
        # be sure to honnour versions restrictions
        requirement = self._constrain_requirement(requirement)
        # if we are in online mode, trying to get the latest version available
        candidate = None
        # first try with what we have in binary form
        try:
            dist, avail = self.inst._satisfied(requirement)
        except zc.buildout.easy_install.MissingDistribution:
            # force env rescanning if egg was not there at init.
            self.scan([self._dest])
            dist, avail = self.inst._satisfied(requirement)
        search_new = self.buildout.newest
        if dist:
            if dist.precedence == pkg_resources.DEVELOP_DIST:
                search_new = False
        # do not search newer when we already have '==' in requirement :)
        # neweer thab ==1.0 ==> 1.0 and searching is just a no-op!
        if '==' in '%s' % requirement:
            search_new = False
        if search_new:
            candidate = self.inst._obtain(requirement)
        if candidate:
            if avail:
                if candidate.version > avail.version:
                    avail = candidate
            if dist:
                if candidate.version > dist.version:
                    avail = candidate
                    dist = None
        if not dist:
            if avail is None:
                # try to found a sdist, but do not stop there,
                # this art can call other ones
                try:
                    avail = self._search_sdist(requirement, working_set)
                except zc.buildout.easy_install.MissingDistribution:
                    # just mark the dist as missing.
                    avail = None

        # there we have dist or avail setted, weither the egg is alredy installed
        # both can be null is nothing is installed or downloaded right now.
        # In this case, we just have the requirement availlabke
        v, patched_egg = get_requirement_version(requirement)
        patches = []
        # Try to get the possibles patch for the project if this is the relevant
        # v can be wrong atm,if the requirement is not yet pinned to the patched
        # version !!!
        v, _, _, patches, _ = self._get_dist_patches(requirement.project_name, v)

        # leads to bugs in buildout behaviour if we read things we didnt have to ;'(
        # if this is a minitage patched egg, there is a chance that the
        # part which build the egg was not built yet.
        # We will try to find and run it!
        #if (not patches) and patched_egg:
        #    for spart in self.buildout:
        #        part = self.buildout[spart]
        #        if 'recipe' in part:
        #            for option in part:
        #                if option.startswith(requirement.project_name) \
        #                and ('patch' in option):
        #                    v, _, _, patches, _ = self._get_dist_patches(
        #                        requirement.project_name,
        #                        v,
        #                        part)
        #                    # we found the part with the set of patches  :D
        #                    if patches:
        #                        self.logger.info(
        #                            "Althought [%s] doesn't provide "
        #                            "appropriate patches for %s, we found "
        #                            "[%s] which provide them, "
        #                            "running it!" %(
        #                                self.name, requirement, part.name
        #                            )
        #                        )
        #                        self.buildout._install(part.name)
        #                        break

        if len(patches):
            # forge the patched requirement reporesentation
            # if we cant determine the version from the requirement, it was not
            # already patched, we must have a distribution or an available
            # source distribution to get the version from
            # Note that from the distribution, it canbe alraedy patched ;)
            if not get_orig_version(v):
                for project in dist, avail:
                    if project:
                        if v in project.version:
                            v = project.version
                        else:
                            v = "%s-%s" % (project.version, v)
                            break
            requirement = pkg_resources.Requirement.parse(
                "%s==%s" % (
                    requirement.project_name, v
                )
            )
            # Do we have a compiled distribution of the egg yet?
            dist, pavail = self.inst._satisfied(requirement)
            if dist:
                v = dist.version
                avail = None
            # now, in the 2 cases: we ran another part or the part itself.
            # But in all cases, we have feeded our patches list !
            # But we may not have installed yet the egg!
            elif avail is None:
                # do we come from elsewhere, in the contrary,
                # We are in the case where install the egg
                try:
                    avail = self._search_sdist(requirement,
                                               working_set)
                except zc.buildout.easy_install.MissingDistribution:
                    # if this is a minitage patched egg, there is a chance that the
                    # part which build the egg was not built yet.
                    # in this case, we try to find the egg without the patched
                    # version bits.
                    # The other case is when you have already fixed the
                    # version on the buildout, but you dont have already the
                    # egg, its just to be cool with users as we know how to
                    # do this egg, anyhow :)
                    version, patched_egg = get_requirement_version(requirement)
                    if patched_egg:
                        requirement = pkg_resources.Requirement.parse(
                            "%s==%s" % (
                                requirement.project_name, get_orig_version(v)
                            )
                        )
                        avail = self._search_sdist(requirement, working_set)
        # Mark buildout, recipes and installers to use our specific egg!
        # Even, if we have already installed, in case user or something else
        # removed it!
        if v and patches:
            self._pin_version(requirement.project_name, v)
        # We may have not found the distribution
        if (not dist) and (not avail):
            raise zc.buildout.easy_install.MissingDistribution(
                requirement, working_set)
        return dist, avail, requirement

    def _pin_version(self, name, version):
        sysargv = sys.argv[:]
        fconfig = 'buildout.cfg'
        # determine which buildout config has been run
        while sysargv:
            try:
                arg = sysargv.pop(0)
                if arg == '-c':
                    fconfig = sysargv.pop()
                    break
            except IndexError:
                fconfig = 'buildout.cfg'
        cfg = os.path.join(self.buildout._buildout_dir, fconfig)
        # patch runtime objects to fix version
        if self.buildout_versions:
            self.buildout[self.buildout_versions][name] = version
        self.versions[name] = version
        self.inst._versions[name] = version
        requirement = pkg_resources.Requirement.parse(
            '%s==%s' % (name, version)
        )
        if not os.path.exists(cfg):
            self.logger.error("""

It seems you are not using buildout.cfg as configuration file, as we have no mean to determine the buldout config file at runtime, you ll have to fix the version your self by adding : \n
[buildout]
extends = customversions.cfg
""")
            cfg = os.path.join(self.buildout._buildout_dir, 'customversions.cfg')

        versions_part = self.buildout.get('buildout', {}).get('versions', 'versions')
        config = ConfigParser.ConfigParser()
        try:
            self.logger.debug('Pinning custom egg version in buildout, trying to write the configuration')
            config.read(cfg)
            if not config.has_section('buildout'):
                config.add_section('buildout')
            config.set('buildout', 'versions', versions_part)
            if not config.has_section(versions_part):
                config.add_section(versions_part)

            existing_version = None
            try:
                existing_version = config.get(versions_part, name).strip()
            except NoOptionError:
                pass

            # only if version changed
            if existing_version != version:
                config.set(versions_part, requirement.project_name, version)
                backup_base = os.path.join(self.buildout._buildout_dir,
                                      '%s.before.fixed_version.bak' % fconfig)
                index = 0
                backup = backup_base
                while os.path.exists(backup):
                    index += 1
                    backup = '%s.%s' % (backup_base, index)
                self.logger.debug('CREATING buildout backup in %s' % backup)
                shutil.copy2(cfg, backup)
                config.write(open(cfg, 'w'))
            else:
                self.logger.debug('Version already pinned, nothing has been wroten.')
        except Exception, e:
            self.logger.error('Cant pin the specific versions for %s\n%s' % (requirement, e))

    def _constrain(self, requirements, dep=None):
        constrained_requirements = {}
        for requirement in requirements:
            if not isinstance(requirement, pkg_resources.Requirement):
                requirement = pkg_resources.Requirement.parse(requirement)
            constrained_req = self.inst._constrain(requirement)
            r = constrained_requirements.get(requirement.project_name,
                                             constrained_req)
            # constrain doesnt conserve extras :::
            r = merge_extras(r, requirement)
            # if an egg has precised some version stuff not controlled by
            # our version.cfg, let it do it !
            if not r.specs:
                r = merge_specs(r, requirement)
            constrained_requirements[r.project_name] = r
        return constrained_requirements.values()

    def _constrain_requirement(self, requirement, dep=None):
        return self._constrain([requirement], dep)[0]

    def filter_already_installed_requirents(self,
                                            requirements,
                                            already_installed_dependencies):
        items = []
        constrained_requirements = self._constrain(requirements)
        installed_requirements = already_installed_dependencies.values()
        if already_installed_dependencies:
            for requirement in constrained_requirements:
                similary_req = already_installed_dependencies.get(
                    requirement.project_name, None)
                found = True
                if not similary_req:
                    found = False
                else:
                    if requirement.extras and (similary_req.extras != requirement.extras):
                        found = False
                        requirement = merge_extras(requirement, similary_req)
                    # if an egg has precised some version stuff not controlled by
                    # our version.cfg, let it do it !
                    if requirement.specs and (not similary_req.specs):
                        found = False
                if not found:
                    items.append(requirement)
                    # something new on an already installed item, mark it to be
                    # reinstalled
                    if similary_req:
                        del already_installed_dependencies[requirement.project_name]
        else:
            items = constrained_requirements
        return items

    def ensure_dependencies_there(self,
                                  dest,
                                  working_set,
                                  already_installed_dependencies,
                                  first_call, dists):
        """Ensure all distributionss have their dependencies in the working set.
        Alsso ensure all eggs are at rights versions pointed out by buildout.
        @param dest the final egg cache path
        @param working_set the current working set
        @param already_installed_dependencies Requirements
                                              of already installed dependencies
        @param first_call instaernally parameter to show debug messages avoiding
                          dirts caused by recursivity

        """
        deps_reqs = []
        for dist in dists:
            r = self.inst._constrain(dist.as_requirement())
            already_installed_dependencies.setdefault(r.project_name, r)
            deps_reqs.extend(dist.requires())
        if deps_reqs:
            ideps_reqs = self.filter_already_installed_requirents(
                deps_reqs,
                already_installed_dependencies)
            d_rs, working_set = self._install_requirements(ideps_reqs,
                                            dest,
                                            working_set,
                                            already_installed_dependencies,
                                            first_call = False)

        if first_call:
            self.logger.debug('All egg dependencies seem to be installed!')
        return working_set

    def add_dist(self, dist):
        self.inst._env.add(dist)

    def _install_requirements(self, reqs, dest,
                              working_set=None,
                              already_installed_dependencies=None,
                              first_call=True):
        """Get urls of neccessary eggs to
        achieve a requirement.
        """
        if not already_installed_dependencies:
            already_installed_dependencies = {}

        # initialise working directories
        if not os.path.exists(self.tmp_directory):
            os.makedirs(self.tmp_directory)
        if working_set is None:
            working_set = pkg_resources.WorkingSet([])
        else:
            working_set = working_set

        requirements = self.filter_already_installed_requirents(
            reqs,
            already_installed_dependencies)
        # Maybe an existing dist is already the best dist that satisfies the
        # requirement
        if requirements:
            dists = []
            #self.logger.debug('Trying to install %s' % requirements)
            for requirement in requirements:
                dist, avail, maybe_patched_requirement = self._satisfied(requirement, working_set)
                # installing extras if required
                if dist is None:
                    fdist = self._get_dist(avail, working_set)
                    dist = self._install_distribution(fdist,
                                                      dest,
                                                      working_set,
                                                      already_installed_dependencies)
                    rname = requirement.project_name
                    # mark the distribution as installed
                    already_installed_dependencies[rname] = pkg_resources.Requirement.parse(
                        '%s==%s' % (dist.project_name, dist.version)
                    )
                    # advertise environements of our new dist
                    self.add_dist(dist)

                # honouring extra requirements
                if requirement.extras:
                    _, working_set = self._install_requirements(
                        dist.requires(requirement.extras),
                        dest,
                        working_set,
                        already_installed_dependencies,
                        first_call=False
                    )
                dists.append(dist)

            for dist in dists:
                # remove similar dists found in sys.path if we have ones, to
                # avoid conflict errors
                similar_dist = working_set.find(pkg_resources.Requirement.parse(dist.project_name))
                if similar_dist and (similar_dist != dist):
                    working_set.entries.remove(similar_dist.location)
                    if similar_dist.location in working_set.entry_keys:
                        del working_set.entry_keys[similar_dist.location]
                    if similar_dist.project_name in working_set.by_key:
                        del working_set.by_key[similar_dist.project_name]

                working_set.add(dist)
                # Check whether we picked a version and, if we did, report it:
                if not (
                    dist.precedence == pkg_resources.DEVELOP_DIST
                    or
                    (len(requirement.specs) == 1
                     and
                     requirement.specs[0][0] == '==')
                    ):
                    self.logger.info('Picked: %s = %s',
                                      dist.project_name,
                                      dist.version)
                    if not self.inst._allow_picked_versions:
                        raise zc.buildout.UserError(
                            'Picked: %s = %s' % (dist.project_name,
                                                 dist.version))
            working_set = self.ensure_dependencies_there(dest,
                                                working_set,
                                                already_installed_dependencies,
                                                first_call, dists )

        return already_installed_dependencies.values(), working_set


    def _install_distribution(self, dist, dest,
                              working_set=None, already_installed_dependencies = None):
        """Install a setuptool distribution
        into the eggs cache."""

        if not already_installed_dependencies:
            already_installed_dependencies = {}
        # where we put the builded  eggs
        tmp = os.path.join(self.tmp_directory, 'eggs')

        if not os.path.isdir(tmp):
            os.makedirs(tmp)
        # maybe extract time
        location = dist.location
        if not location.endswith('.egg'):
            location = tempfile.mkdtemp()
            self._unpack(dist.location, location)
            location = self._get_compil_dir(location)
        sub_prefix = self.options.get(
            '%s-build-dir' % ( dist.project_name.lower()),
            None
        )
        if sub_prefix:
            location = os.path.join(location, sub_prefix)

        self.options['compile-directory'] = location
        repackage = False
        patched = False
        if not location.endswith('.egg'):
            # maybe patch time
            patched, dist = self._patch(location, dist)
            #maybe we have a hook
            hooked = self._call_hook(
                '%s-pre-setup-hook' % (dist.project_name.lower()),
                location
            )
            if patched or hooked:
                patched = True
        # recursivly easy installing dependencies
        ez = easy_install.easy_install(distutils.core.Distribution())
        if os.path.isdir(location):
            oldcwd = os.getcwd()
            # generating metadata for source distributions
            try:
                os.chdir(location)
                ez.run_setup('', '', ['egg_info', '-e', '.'])
            except:
                os.chdir(oldcwd)

        # getting dependencies
        requires = []
        reqs_lists = [a.requires()
                      for a in pkg_resources.find_distributions(location)]

        # installing them
        for reqs_list in reqs_lists:
            requires.extend(self._constrain(reqs_list))

        # compile time
        dist_location = dist.location
        ttar = '/not/existing/file/muhahahahaha'
        if not (dist.precedence in (pkg_resources.EGG_DIST,
                                    pkg_resources.BINARY_DIST,
                                    pkg_resources.DEVELOP_DIST)):
            if patched:
                ttar = os.path.join(
                    tempfile.mkdtemp(), '%s-%s.%s' % (dist.project_name,
                                                      dist.version,
                                                      'tar.gz'
                                                     )
                )
                tar = tarfile.open(ttar, mode='w:gz')
                tar.add(location, os.path.basename(location))
                tar.close()
                dist_location = ttar

        # delete our require getter hackery mecanism because
        # it can pertubate the setuptools namespace handling
        if os.path.isdir(location):
            os.chdir(location)
            for f in os.listdir('.'):
                if f.endswith('.egg-info') and os.path.isdir(f):
                    shutil.rmtree(f)
            os.chdir(oldcwd)

        # mark the current distribution as installed to avoid circular calls
        if requires and not self.options.get('ez-nodependencies'):
            r = dist.as_requirement()
            if not r.project_name in already_installed_dependencies:
                already_installed_dependencies[r.project_name] = r
            _, working_set = self._install_requirements(requires,
                                       dest,
                                       working_set,
                                       already_installed_dependencies,
                                       first_call = False)

        self._run_easy_install(tmp, ['%s' % dist_location], working_set=working_set)
        if os.path.exists(ttar):
            os.remove(ttar)
        dists = []
        env = pkg_resources.Environment(
            [tmp],
            python=self.executable_version)

        for project in env:
            dists.extend(env[project])

        if not dists:
            raise zc.buildout.UserError("Couldn't install: %s" % dist)

        if len(dists) > 1:
            self.logger.warn("Installing %s\n"
                        "caused multiple distributions to be installed:\n"
                        "%s\n",
                        dist, '\n'.join(map(str, dists)))
        else:
            d = dists[0]
            if d.project_name != dist.project_name:
                self.logger.warn("Installing %s\n"
                            "Caused installation of a distribution:\n"
                            "%s\n"
                            "with a different project name.",
                            dist, d)
            if d.version != dist.version:
                self.logger.warn("Installing %s\n"
                            "Caused installation of a distribution:\n"
                            "%s\n"
                            "with a different version.",
                            dist, d)

        ## check if cache container is there.
        if not os.path.isdir(dest):
            os.makedirs(dest)
        # install eggs in the destination
        result = []
        for d in dists:
            newloc = os.path.join(
                dest,
                os.path.basename(d.location))
            # dont forget to skip zipped erggs, normally we dont have ones, but
            # in case
            if (d.project_name == dist.project_name) and (patched) and (not os.path.isfile(d.location)):
                # just rename the egg to match the patched name if any
                #r emove python version pat
                without_pyver_re = re.compile("(.*)-py\d+.\d+.*$", re.M|re.S)
                d_egg_name =    without_pyver_re.sub("\\1", d.egg_name())
                dist_egg_name = without_pyver_re.sub("\\1", dist.egg_name())
                newloc = newloc.replace(d_egg_name, dist_egg_name)
                pkginfo = os.path.join(d._provider.egg_info, 'PKG-INFO')
                pkginfo_contents = open(pkginfo, 'rU').readlines()
                version_pkginfo_re = re.compile('^(V|v)ersion: .*', re.M|re.U)
                patched_content = []
                for line in pkginfo_contents:
                    if version_pkginfo_re.match(line):
                        line = version_pkginfo_re.sub('Version: %s' % dist.version,
                                                      line)
                    patched_content.append(line)
                open(pkginfo, 'w').write(''.join(patched_content))
                d = d.clone(**{'version': dist.version})

            if os.path.exists(newloc):
                if os.path.isdir(newloc):
                    shutil.rmtree(newloc)
                else:
                    os.remove(newloc)

            os.rename(d.location, newloc)
            # regenerate pyc's in this directory
            redo_pyc(os.path.abspath(newloc), executable = self.executable)
            nd = pkg_resources.Distribution.from_filename(
                newloc, metadata=pkg_resources.PathMetadata(
                    newloc, os.path.join(newloc, 'EGG-INFO')
                )
            )
            result.append(nd)
        self._call_hook(
            '%s-post-setup-hook' % (d.project_name.lower()),
            newloc
        )
        if not dest in self.eggs_caches:
            self.eggs_caches += [dest]
        rdist = None
        if result:
            renv = pkg_resources.Environment([dest],
                                            python=self.executable_version)

            rdist = result[0]
        if not rdist:
            self.scan()
            rdist = self.inst._env.best_match(dist.as_requirement(), working_set)
        self.logger.debug("Got %s.", rdist)
        return rdist

    def _run_easy_install(self, prefix, specs, caches=None, working_set=None, dist=None):
        """Install a python egg using easy_install."""
        if not caches:
            caches = []

        ez_args = '-mU'
        # compatiblity thing: we test ez-dependencies to be there
        # new version of  the recipe implies dependencies installed prior to the
        # final ez install call via the require dance
        ez_args += 'N'

        ez_args += 'xd'

        args = ('-c', zc.buildout.easy_install._easy_install_cmd, ez_args,
                zc.buildout.easy_install. _safe_arg(prefix))
        if self.zip_safe:
            args += ('-Z', )
        else:
            args += ('-z', )

        args += ('-v', )

        if self.offline:
            args+= ('-H None', )

        for dir in caches + self.eggs_caches:
            args += ('-f %s' % dir,)

        self._sanitizeenv(working_set)

        cwd = os.getcwd()
        for spec in specs:
            largs = args + ('%s' % spec, )

            # installing from a path, cd inside
            if spec.startswith('/') and os.path.isdir(spec):
                os.chdir(spec)

            # ugly fix to avoid python namespaces conflicts
            if os.path.isdir('setuptools'):
                os.chdir('/')

            self.logger.debug('Running easy_install: \n%s "%s"\n',
                             self.executable,
                             '" "'.join(largs))

            try:
                sys.stdout.flush() # We want any pending output first
                lenv =  dict(os.environ)
                exit_code = subprocess.Popen( [self.executable]+list(largs), env = lenv).wait()
                if exit_code > 0:
                    raise core.MinimergeError('easy install '
                                              'failed !')
            except Exception, e:
                import pdb;pdb.set_trace()  ## Breakpoint ##
                raise core.MinimergeError(
                    'PythonPackage via easy_install '
                    'Install failed !\n%s' % e
                )

        os.chdir(cwd)

    def _get_dist(self, avail, working_set):
        """Get a distribution."""

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
        # download to cache/FIRSTLETTER/Archive
        filename = self._download(
            url=source,
            destination=self.download_cache,
        )
        dist = avail.clone(location=filename)

        if dist is None:
            raise zc.buildout.UserError(
                "Couln't download distribution %s." % avail)

        return dist

    def _get_dist_patches(self, name, version, options=None):
        """Get the patches for a distribution.
        returns a tuple
        patched_version_str, patch_cmd, patch_options, patches_list
        """
        if not version:
            version = ''
        # remove the minitage patch computation as we are rebuilding it!
        version = get_orig_version(version)
        if not options:
            options = self.options
        # patch for eggs are based on the project_name
        patch_cmd = options.get(
            '%s-patch-binary' % name,
            'patch'
        ).strip()

        patch_options = ' '.join(
            options.get(
                '%s-patch-options' % name, '-Np0'
            ).split()
        )
        patches = options.get(
            '%s-patches' % name,
            '').split()
        # conditionnaly add OS specifics patches.
        patches.extend(
            splitstrip(
                options.get(
                    '%s-%s-patches' % (name,
                                       self.uname.lower()),
                    ''
                )
            )
        )

        additionnal = ''
        if len(patches):
            # this will make this distribution, the newer one!for this release
            # number
            additionnal = PATCH_MARKER
            separator = 'IAMATEXTSEPARATORSTRING'
            for patch in patches:
                patch = patch.replace('.patch', '')
                patch = patch.replace('.diff', '')
                patch_name = os.path.basename(patch)
                # throw any unfriendly setuptools version name away :)
                for s in ('.', '_', '-', '(',
                          ')', '#', '*', '+', '~', '&', '?', ','
                          ';', ':', '!', '§', '$', '=', '@', '^'
                          '\\', '|'):
                    patch_name = patch_name.replace(s, separator)
                forged_name = ''
                for part in patch_name.split(separator):
                    fname=part
                    if len(part)>1:
                        fname = '%s%s' % (part[0].upper(), part[1:])
                    forged_name += fname
                additionnal = '%s-%s' % (additionnal, forged_name)
            if version:
                version += "-%s" % additionnal
            else:
                version = additionnal
        return version, patch_cmd, patch_options, patches, additionnal

    def _patch(self, location, dist):
        version, patch_cmd, patch_options, patches, additionnal = self._get_dist_patches(dist.project_name, dist.version)
        # not patched ?
        if len(patches):
            common. MinitageCommonRecipe._patch(
                self,
                location,
                patch_cmd = patch_cmd,
                patch_options = patch_options,
                patches = patches,
                download_dir = os.path.join(self.download_cache,
                                            'patches',
                                            dist.project_name,
                                            dist.version)
            )
            dist = dist.clone(**{'version': version})
        return bool(len(patches)), dist

    def _sanitizeenv(self, ws):
        """Get the env.in the right way to compile.
        Only the pypath may vary at each iteration, we zap the rest."""
        # get the working set into the env.
        self._set_py_path(ws)
        # use the common nice functions to
        # make our environement convenient to
        # build packages with dependencies
        if getattr(self, 'unsanitized', True):
            self._set_path()
            self._set_pkgconfigpath()
            self._set_compilation_flags()
            if self.uname == 'darwin':
                os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.5'
            setattr(self, 'unsanitized', False)

# vim:set et sts=4 ts=4 tw=80:
