Mu - a "micro" editor
=====================

**This project works with Python 3 and the Qt UI library.**

This fork is to add functionality to the FileSystem panes and some minor bug fixes.  Double-click on a directory to navigate into the directory.  Double-click on a file in the local "Files in your Computer" to open the file in the editor.  When you flash, perform a soft-reboot so the code is refreshed on the micropython device.

Fixed issue of files/repl not showing when one of them is already displayed.  

Fixed issue in microfs when dragging a file from micropython device to local filesystem.



Installation
------------

Run Mu from source. You will need to install python3-pyqt5 and python3-serial

::

    $ sudo apt-get install python3-pyqt5
    $ sudo apt-get install python3-serial


Linux
+++++

Just make the file run.py executable and run it! :-)

We're in the process of creating official packages for both Debian and Fedora
based flavours of Linux.

What?
-----

Mu is a very simple code editor for kids, teachers and beginner programmers.
It's written in Python and works on Windows, OSX, Linux and Raspberry Pi.

Why?
----

There isn't a cross platform Python code editor that is:

* Easy to use;
* Accessible to everyone;
* Available on all major platforms;
* Well documented (even for beginners);
* Simply coded;
* Currently maintained; and,
* Thoroughly tested.

Mu addresses these needs.

In the Python world, teachers, students and other beginner programmers are
forced to use one of the following options:

* IDLE - the long-in-the-tooth, unmaintained and eccentric editor that comes with Python.
* A third party IDE (integrated development environment) for teaching. If "IDE" sounds complicated, that's because it is.
* A professional programmer's editor such as vi or emacs.

Such tools are fiddly, complicated and full of distracting "features". They
are completely inappropriate for teaching and learning ~ complexity impedes a
novice programmer's first steps.

How?
----

Mu's outlook is:

* Less is more (remove all unnecessary distractions);
* Keep it simple (so Mu is easy to understand);
* Walk the path of least resistance (Mu should be easy);
* Have fun (learning should be a positive experience).

Our first iteration targets MicroPython on the BBC micro:bit.

The BBC's micro:bit project is aimed at 11-year old children. It consists of a
small and simple programmable device. One option is the remarkable work of
Damien George in the form of MicroPython, a full re-implementation of Python 3
for microcontrollers including the BBC micro:bit.

The BBC's "blessed" solution for programming this device is web-based. However,
we have observed that this doesn't provide the optimum experience for Python:

* It requires you to use a web-browser as a text based code editor.
* You need to download the .hex file to flash onto the device and then drag it to the device's mount point on the filesystem. A rather clunky multi-part process.
* It doesn't allow you to connect to the device in order to live code in Python via the REPL.

The Mu editor addresses each of these problems: it is a native application
specifically designed as a text based coding environment. It makes it easy to
flash your code onto the device (it's only a click of a button). It has a built
in REPL client that automatically connects to the device.

Mu has been adapted from my previous work done with Damien George and Dan Pope
on the "Puppy" editor for kids. Mu is an ultra-slimmed down version of Puppy.

The code is simple and monolithic - it's commented and mostly found in a
a few obviously named Python files. This has been done on purpose: we want
teachers and kids to take ownership of this project and organising the code in
this way aids the first steps required to get involved (everything you need to
know is in four obvious files).

In terms of features - it's a case of less is more:

* Create a new Python script.
* Load an existing Python script.
* Save the existing Python script.
* Flash the device with the current script.
* Connect to the device via the REPL (will only work if a device is connected).
* Zoom in/out.
* Day / night (high contrast) modes.
* Built in help (HTML).
* Quit.

That's it!

Development
-----------

If you only want to use Mu then please ignore this section. If you'd like to
contribute to the development of Mu read on...

The source code is hosted on GitHub. Please feel free to fork the repository.
Assuming you have Git installed you can download the code from the canonical
repository with the following command::

    $ git clone https://github.com/ntoll/mu.git

For this to work you'll need to have Qt5 and Python 3 installed. On Debian
based systems this is covered by installing: python3-pyqt5, python3-pyqt5.qsci and python3-pyqt5.qtserialport.

Ensure you have the correct dependencies for development installed by creating
a virtualenv and running::

    $ pip install -r requirements.txt

To run the local development version of "mu", in the root of this repository
type::

    $ python3 run.py

There is a Makefile that helps with most of the common workflows associated
with development. Typing "make" on its own will list the options thus::

    $ make

    There is no default Makefile target right now. Try:

    make clean - reset the project and remove auto-generated assets.
    make pyflakes - run the PyFlakes code checker.
    make pep8 - run the PEP8 style checker.
    make test - run the test suite.
    make coverage - view a report on test coverage.
    make check - run all the checkers and tests.
    make docs - run sphinx to create project documentation.

Before contributing code please make sure you've read CONTRIBUTING.rst.
