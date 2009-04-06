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
import distutils
import os
import shutil
import sys
import tempfile

import pkg_resources
import setuptools.archive_util
from setuptools.command import easy_install
import zc.buildout.easy_install

from minitage.recipe import common
from minitage.core.fetchers.interfaces import IFetcherFactory
from minitage.core import core
from minitage.core.common import splitstrip


def merge_extras(a, b):
    a.extras += b.extras
    a.extras = tuple(set(a.extras))
    return a

def merge_specs(a, b):
    a.specs += b.specs
    a.specs = list(set(a.specs))
    return a

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
        self.download_cache = os.path.abspath(
            os.path.join(self.download_cache, 'eggs')
        )

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

        self._env = pkg_resources.Environment(
            self.eggs_caches,
            python=self.executable_version
        )

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
        self._dest= os.path.abspath(
            self.buildout['buildout']['eggs-directory']
        )

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

        env = pkg_resources.Environment(self.eggs_caches,
                                        python=self.executable_version)

        return requirements, working_set

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
            fname = self._download(url=url, scm = self.scm)
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
                self.inst._env.scan([dest])
                sdist, savail = self.inst._satisfied(requirement)
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
        return requirements, working_set

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
                # first try with what we have in binary form
                # force env rescanning if egg was not there at init.
                self.inst._env.scan([self._dest])
                dist, avail = self.inst._satisfied(requirement)
                # installing extras if required
                if dist is None:
                    if avail is None:
                        env = pkg_resources.Environment(
                            [self.download_cache],
                            python=self.executable_version)
                        sdists = []
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
                        msg = 'We found a source distribution for \'%s\' in \'%s\'.'
                        self.logger.info(msg % (requirement, avail.location))
                    fdist = self._get_dist(avail, working_set)
                    dist = self._install_distribution(fdist,
                                                      dest,
                                                      working_set,
                                                      already_installed_dependencies)
                already_installed_dependencies[requirement.project_name] = requirement
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
                similar_dist = working_set.find(pkg_resources.Requirement.parse(dist.project_name))
                if similar_dist and (similar_dist != dist):
                    working_set.entries.remove(similar_dist.location)

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
        if not os.path.isdir(location):
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
        if not location.endswith('.egg'):
            # maybe patch time
            self._patch(location, dist)
            #maybe we have a hook
            self._call_hook(
                '%s-pre-setup-hook' % (dist.project_name.lower()),
                location
            )
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

        # compile time
        self._run_easy_install(tmp, ['%s' % location], working_set=working_set)
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
            if os.path.exists(newloc):
                if os.path.isdir(newloc):
                    shutil.rmtree(newloc)
                else:
                    os.remove(newloc)

            os.rename(d.location, newloc)
            # regenerate pyc's in this directory
            zc.buildout.easy_install.redo_pyc(os.path.abspath(newloc))
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
            self._env.scan(self.eggs_caches)
            rdist = self._env.best_match(dist.as_requirement(), working_set)
        self.logger.debug("Got %s.", rdist)
        return rdist

    def _run_easy_install(self, prefix, specs, caches=None, working_set=None):
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

                largs += (dict(os.environ),)
                exit_code = os.spawnle(
                    os.P_WAIT,
                    self.executable,
                    zc.buildout.easy_install._safe_arg (self.executable),
                    *largs)
                if exit_code > 0:
                    raise core.MinimergeError( "easy install failed")
            except Exception, e:
                raise core.MinimergeError(
                    'PythonPackage via easy_install Install failed'
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
        if not source.startswith('/'):
            # download to cache/FIRSTLETTER/Archive
            filename = self._download(
                source,
                self.download_cache,
            )
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

        return dist

    def _patch(self, location, dist):
        # patch for eggs are based on the project_name
        patch_cmd = self.options.get(
            '%s-patch-binary' % dist.project_name,
            'patch'
        ).strip()

        patch_options = ' '.join(
            self.options.get(
                '%s-patch-options' % dist.project_name, '-p0'
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

    def _sanitizeenv(self, ws):
        """Get the env. right to compile."""
        # use the common nice functions to make our environement convenient to
        # build packages with dependencies
        self._set_py_path(ws)
        self._set_path()
        self._set_pkgconfigpath()
        self._set_compilation_flags()
        if self.uname == 'darwin':
            os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.5'

# vim:set et sts=4 ts=4 tw=80:
