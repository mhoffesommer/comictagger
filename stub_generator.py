import os
import sys
import xml.etree.ElementTree


def generate_stubs(file):
    root = xml.etree.ElementTree.parse(file).getroot()
    print("Stub for file: " + os.path.basename(file))
    print()
    print("    def __stubs(self):")
    print("        # pylint: disable=all")
    print('        """ This just enables code completion. It should never be called """')

    for widget in root.findall(".//widget"):
        name = widget.get("name")
        # if len(name) > 3 and name[:2] == 'ui' and name[2].isupper():
        cls = widget.get("class")
        print("        self.{} = QtWidgets.{}()".format(name, cls))
    for widget in root.findall(".//action"):
        name = widget.get("name")
        # if len(name) > 3 and name[:2] == 'ui' and name[2].isupper():
        # cls = widget.get('class')
        print("        self.{} = QtWidgets.QAction()".format(name))

    print('        raise AssertionError("This should never be called")')
    print()


def main():
    for file in sys.argv[1:]:
        generate_stubs(file)


if __name__ == "__main__":
    main()
