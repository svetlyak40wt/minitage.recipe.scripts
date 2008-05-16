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
import zc.buildout
import urlparse
import tempfile
import logging
import urllib
import shutil
import md5
import imp
import os

import hexagonit.recipe.download
import hexagonit.recipe.cmmi as parent

class Recipe(parent.Recipe):
    """zc.buildout recipe for compiling and installing software"""

    def install(self):
        log = logging.getLogger(self.name)
        parts = []

        make_cmd = self.options.get('make-binary', 'make').strip()
        # if gmake is setted. taking it as the make cmd !
        # be careful to have a 'gmake' in your path
        # we have to make it only in non linux env.
        if os.uname()[0] != 'Linux':
            if self.buildout.has_key('part'):
                if self.buildout['part'].get('gmake',None):
                    make_cmd='gmake'

        make_targets = ' '.join(self.options.get('make-targets', 'install').split())
        if self.options.get('noinstall') and make_targets== 'install':
            make_targets = None
        additionnal_make_targets=[]
        if self.options.get('additionnal-make-targets'):
            additionnal_make_targets=self.options.get('additionnal-make-targets').strip().split('\n')

        configure_options = ' '.join(self.options.get('configure-options','').split())

        patch_cmd = self.options.get('patch-binary', 'patch').strip()
        patch_options = ' '.join(self.options.get('patch-options', '-p0').split())
        patches = self.options.get('patches', '').split()
        uname=os.uname()[0]
        # conditionnaly add OS specifics patches.
        patches+=self.options.get('%s-patches'%(uname.lower()), '').split() 
        
        # Download the source using hexagonit.recipe.download
        if self.options['url']:
            compile_dir = self.options['compile-directory']
            os.mkdir(compile_dir)

            try:
                opt = self.options.copy()
                opt['destination'] = compile_dir
                hexagonit.recipe.download.Recipe(
                    self.buildout, self.name, opt).install()
            except:
                shutil.rmtree(compile_dir)
                raise
        else:
            log.info('Using local source directory: %s' % self.options['path'])
            compile_dir = self.options['path']

        os.mkdir(self.options['location'])
        os.chdir(compile_dir)

        try:
            configure="%s/configure"%os.getcwd()
            if os.path.isdir(compile_dir):
                contents = os.listdir(compile_dir)
                if len(contents) == 1:
                    os.chdir(contents[0])
                    # openssl fools put a "./Configure
                    if os.path.isfile('config') :
                            configure="%s/config"%os.getcwd()
                    if os.path.isfile('./dist/configure') :
                         configure="%s/dist/configure"%os.getcwd()
                    if self.options.has_key('build-dir'):
                        if not os.path.isdir(self.options['build-dir']):
                            os.mkdir(self.options['build-dir'])
                        os.chdir(self.options['build-dir'])
                    if os.path.isfile('configure') :
                        configure="%s/configure"%os.getcwd() 
                    if not os.path.isfile('configure') and not os.path.isfile(configure) and not self.options.has_key('noconfigure'):
                        log.error('Unable to find the configure script')
                        raise zc.buildout.UserError('Invalid package contents')

            if patches:
                log.info('Applying patches')
                for patch in patches:
                    self.run('%s %s < %s' % (patch_cmd, patch_options, patch))

            if 'pre-configure-hook' in self.options and len(self.options['pre-configure-hook'].strip()) > 0:
                log.info('Executing pre-configure-hook')
                self.call_script(self.options['pre-configure-hook'])

            if not self.options.has_key('noconfigure'):
                self.run('%s --prefix=%s %s' % (configure,self.options['prefix'], configure_options))

            if 'pre-make-hook' in self.options and len(self.options['pre-make-hook'].strip()) > 0:
                log.info('Executing pre-make-hook')
                self.call_script(self.options['pre-make-hook'])

            if not self.options.has_key('nomake'):
                self.run(make_cmd)
            if make_targets:
                print '* Running now:    %s %s' % (make_cmd, make_targets)
                self.run('%s %s' % (make_cmd, make_targets))
            for target in additionnal_make_targets:
                print '* Running now additionnal target:    %s %s' % (make_cmd, target)
                self.run('%s %s' % (make_cmd, target))


            if 'post-make-hook' in self.options and len(self.options['post-make-hook'].strip()) > 0:
                log.info('Executing post-make-hook')
                self.call_script(self.options['post-make-hook'])

        except:
            log.error('Compilation error. The package is left as is at %s where '
                      'you can inspect what went wrong' % os.getcwd())
            raise

        if self.options['url']:
            if self.options.get('keep-compile-dir', '').lower() in ('true', 'yes', '1', 'on'):
                # If we're keeping the compile directory around, add it to
                # the parts so that it's also removed when this recipe is
                # uninstalled.
                parts.append(self.options['compile-directory'])
            else:
                shutil.rmtree(compile_dir)
                del self.options['compile-directory']

        parts.append(self.options['location'])
        return parts
