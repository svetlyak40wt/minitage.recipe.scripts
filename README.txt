*********************************************
Recipe for compiling and installing software
*********************************************

.. contents::

=======================
README
=======================


The recipe has those entry point:
    - cmmi: install configure/make/make install softwares
    - du: install distutils based python packages
    - eggs: install python eggs / packages 'setuptoolisables'
    - scripts: install scripts from an egg.

The reasons why i have rewrite yet another buildout recipe builder are:
    - Support on the fly patchs
    - Support hookss
    - Support for distutils
    - Robust offline mode
    - We like pypi, but offer a mode to not use it if we do not want to.

