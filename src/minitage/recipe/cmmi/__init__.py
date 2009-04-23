# Copyright (C)2008 'Mathieu PASQUET <kiorky@cryptelium.net> '
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program; see the file COPYING. If not, write to the
# Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import shutil
try:
    from hashlib import sha1
except ImportError: # Python < 2.5
    from sha import new as sha1

from minitage.recipe import common
from minitage.core import core

class Recipe(common.MinitageCommonRecipe):
    """zc.buildout recipe for compiling and installing software"""

    def __init__(self, buildout, name, options):

        common.MinitageCommonRecipe.__init__(self,
                                             buildout, name, options)
        # handle share mode, compatibility with zc.recipe.cmmi
        self.shared = False
        self.shared_top = os.path.join(self.download_cache, 'cmmi')
        if not os.path.isdir(self.shared_top):
                os.makedirs(self.shared_top)
        if 'shared' in self.options:
            self.shared = os.path.join(self.shared_top,
                         self._state_hash())
            self.prefix = options['location'] = self.shared

    def install(self):
        """Install the recipe."""
        # initialise working directories
        for path in [self.prefix, self.tmp_directory]:
            if not os.path.exists(path):
                os.makedirs(path)
        try:
            cwd = os.getcwd()
            # downloading or get the path
            # in the cache if we are offline
            fname = self._download()

            # preconfigure hook
            self._call_hook('pre-unpack-hook')

            # unpack
            self._unpack(fname)

            # get default compilation directory
            self.compil_dir = self._get_compil_dir(self.tmp_directory)

            # set path
            self._set_path()

            # set pkgconfigpath
            self._set_pkgconfigpath()

            # set compile path
            self._set_compilation_flags()

            # set pypath
            self._set_py_path()

            # preconfigure hook
            self._call_hook('post-unpack-hook')

            # choose configure
            self.configure = self._choose_configure(self.compil_dir)
            self.options['compile-directory'] = self.build_dir

            # apply patches
            self._patch(self.build_dir)

            # preconfigure hook
            self._call_hook('pre-configure-hook')

            # autogen, maybe
            self._autogen()

            # run configure
            self._configure(self.configure)

            # postconfigure/premake hook
            self._call_hook('pre-make-hook')

            # running make
            self._make(self.build_dir, self.make_targets)

            # post build hook
            self._call_hook('post-build-hook')

            # installing
            self._make_install(self.build_dir)

            # post hook
            self._call_hook('post-make-hook')

            # cleaning
            for path in self.build_dir, self.tmp_directory:
                if os.path.isdir(path):
                    shutil.rmtree(path)

            # regaining original cwd in case we changed build directory
            # during build process.
            os.chdir(cwd)
            self.logger.info('Completed install.')
        except Exception, e:
            raise
            self.logger.error('Compilation error. '
                              'The package is left as is at %s where '
                      'you can inspect what went wrong' % self.tmp_directory)
            self.logger.error('Message was:\n\t%s' % e)
            raise core.MinimergeError('Recipe failed, cant install.')

        return []

    def update(self):
        """Update the recipe.
        wrapper to install"""
        self.install()

    def _state_hash(self):
        # hash of our configuration state, so that e.g. different
        # ./configure options will get a different build directory
        env = ''.join(['%s%s' % (key, value) for key, value
                       in os.environ.items()])
        state = [self.url,
                 self.configure_options,
                 self.autogen,
                 ''.join(self.patches),
                 self.patch_options,
                 env]
        return sha1(''.join(state)).hexdigest()


