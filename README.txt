******************************************************************************
Recipe for compiling and installing software with or without minitage
******************************************************************************

.. contents::

=======================
Introduction
=======================

This is a collection of recipe which can be use inside or outside a minitage environment.
What is interresting in using them in minitage is that you ll have all your system dependencies in
the build environment automaticly.

The egg has those entry point:
    - *cmmi*: install configure/make/make install softwares
    - *fetch*: fetch something, somewhere, with git, http, frp, static, hg, svn or bzr.
    - *egg*: install python eggs / packages 'setuptoolisables'
    - *printer*: print or dump to a file all versions needed to achieve eggs
      requirements (versions.cfg made easy)
    - *scripts*: install scripts from an egg and install egg dependencies if they
      are not already in the cache
    - *wsgi*: Make a Python paste configuration file eatable by mod_wsgi with
      all the eggs dependencies you need.

The reasons why i have rewrite yet another buildout recipes builder are:
    - Support for downloading stuff
    - Do not rely on easy_install dependency system
    - Support on the fly patchs for eggs and other distribution.
    - Support multiple hooks at each stage of the build system.
    - Support for distutils
    - Robust offline mode
    - We like pypi, but offer a mode to scan for eggs without need to check
      the index,
    - Support malformed or not indexed distributions.
      In other terms, we provide an url, and the recipe builds it, that's all.
    - All recipes must support automaticly minitage dependencies and rpath linking.

You can browse the code on minitage's following resources:

    - http://git.minitage.org/git/minitage/eggs/minitage.recipe/
    - http://www.minitage.org/trac/browser/minitage/eggs/minitage.recipe

You can migrate your buldouts without any effort with buildout.minitagificator:

    * http://pypi.python.org/pypi/buildout.minitagificator

======================================
Makina Corpus sponsored software
======================================
|makinacom|_

* `Planet Makina Corpus <http://www.makina-corpus.org>`_
* `Contact us <mailto:python@makina-corpus.org>`_

  .. |makinacom| image:: http://depot.makina-corpus.org/public/logo.gif
  .. _makinacom:  http://www.makina-corpus.com



