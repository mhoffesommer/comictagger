""" Simple Plugin implementation in Python
"""

# Adapted from https://github.com/gdiepen/python_plugin_example

# MIT License
#
# Copyright (c) 2020 Guido Diepen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import inspect
import os
import os.path
import pkgutil
import sys


class PluginCollection:
    """Upon creation, this class will read the plugins package for modules
    that contain a class definition that is inheriting from the Plugin class
    """

    def __init__(self, plugin_packages, classtype):
        """Constructor that initiates the reading of all available plugins
        when an instance of the PluginCollection object is created
        """
        if getattr(sys, 'frozen', False):
            if os.path.dirname(sys.executable) not in sys.path:
                sys.path.append(os.path.dirname(sys.executable))
        self.plugin_packages = plugin_packages
        self.plugins = []
        self.seen_paths = []
        self.class_type = classtype

        self.reload_plugins()

    def reload_plugins(self):
        """Reset the list of all plugins and initiate the walk over the main
        provided plugin package to load all available plugins
        """
        self.plugins = []
        self.seen_paths = []
        for package in self.plugin_packages:
            print()
            print(f"Looking for plugins under package {package}")
            self.walk_package(package)

    def apply_all_plugins_on_value(self, argument):
        """Apply all of the plugins on the argument supplied to this function"""
        print()
        print(f"Applying all plugins on value {argument}:")
        for plugin in self.plugins:
            print(f"    Applying {plugin.description} on value {argument} yields value {plugin.perform_operation(argument)}")

    def walk_package(self, package):
        """Recursively walk the supplied package to retrieve all plugins"""
        try:
            imported_package = __import__(package, fromlist=["something"])
        except ModuleNotFoundError:
            return

        for _, pluginname, ispkg in pkgutil.iter_modules(imported_package.__path__, imported_package.__name__ + "."):
            # print(pluginname, ispkg)
            if not ispkg:
                try:
                    plugin_module = __import__(pluginname, fromlist=["something"])
                    clsmembers = inspect.getmembers(plugin_module, inspect.isclass)
                    for (_, c) in clsmembers:
                        # Only add classes that are a sub class of Plugin, but NOT Plugin itself
                        if issubclass(c, self.class_type) & (c is not self.class_type):
                            print(f"    Found plugin class: {c.__module__}.{c.__name__}")
                            self.plugins.append(c)
                except ModuleNotFoundError:
                    continue

        # Now that we have looked at all the modules in the current package, start looking
        # recursively for additional modules in sub packages
        all_current_paths = []
        if isinstance(imported_package.__path__, str):
            all_current_paths.append(imported_package.__path__)
        else:
            all_current_paths.extend(list(imported_package.__path__))

        # for pkg_path in all_current_paths:
        #     if pkg_path not in self.seen_paths:
        #         self.seen_paths.append(pkg_path)
        #
        #         # Get all sub directory of the current package path directory
        #         child_pkgs = [p for p in os.listdir(pkg_path) if os.path.isdir(os.path.join(pkg_path, p))]
        #
        #         # For each sub directory, apply the walk_package method recursively
        #         for child_pkg in child_pkgs:
        #             self.walk_package(package + "." + child_pkg)
