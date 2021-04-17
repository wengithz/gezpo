import xml.dom.minidom
import re
import os
import sys

###########################################################################################################
# Better pretty printing of xml
# Taken from http://ronrothman.com/public/leftbraned/xml-dom-minidom-toprettyxml-and-silly-whitespace/

def fixed_writexml(self, writer, indent="", addindent="", newl=""):
    # indent = current indentation
    # addindent = indentation to add to higher levels
    # newl = newline string
    writer.write(indent + "<" + self.tagName)

    attrs = self._get_attributes()
    a_names = sorted(attrs.keys())

    for a_name in a_names:
        writer.write(" %s=\"" % a_name)
        xml.dom.minidom._write_data(writer, attrs[a_name].value)
        writer.write("\"")
    if self.childNodes:
        if len(self.childNodes) == 1 \
           and self.childNodes[0].nodeType == xml.dom.minidom.Node.TEXT_NODE:
            writer.write(">")
            self.childNodes[0].writexml(writer, "", "", "")
            writer.write("</%s>%s" % (self.tagName, newl))
            return
        writer.write(">%s" % newl)
        for node in self.childNodes:
            # skip whitespace-only text nodes
            if node.nodeType == xml.dom.minidom.Node.TEXT_NODE and \
                    (not node.data or node.data.isspace()):
                continue
            node.writexml(writer, indent + addindent, addindent, newl)
        writer.write("%s</%s>%s" % (indent, self.tagName, newl))
    else:
        writer.write("/>%s" % newl)


# replace minidom's function with ours
xml.dom.minidom.Element.writexml = fixed_writexml
###################################################################################################
common_xacro_xml='''
<sdf version="1.7">
    <!--macro defination:box_inertia-->
    <xacro_macro_define macro_name="box_inertia" params="m x y z">
        <mass>${m}</mass>
        <inertia>
            <ixx>${m*(y*y+z*z)/12}</ixx>
            <ixy>0</ixy>
            <ixz>0</ixz>
            <iyy>${m*(x*x+z*z)/12}</iyy>
            <iyz>0</iyz>
            <izz>${m*(x*x+y*y)/12}</izz>
        </inertia>
    </xacro_macro_define>
    <!--macro defination:cylinder_inertia-->
    <xacro_macro_define macro_name="cylinder_inertia" params="m r h">
        <mass>${m}</mass>
        <inertia>
            <ixx>${m*(3*r*r+h*h)/12}</ixx>
            <ixy>0</ixy>
            <ixz>0</ixz>
            <iyy>${m*(3*r*r+h*h)/12}</iyy>
            <iyz>0</iyz>
            <izz>${m*r*r/2}</izz>
        </inertia>
    </xacro_macro_define>
    <!--macro defination:geometry cylinder-->
    <xacro_macro_define macro_name="geometry_cylinder" params="r l">
        <geometry>
            <cylinder>
                <radius>${r}</radius>
                <length>${l}</length>
            </cylinder>
        </geometry>
    </xacro_macro_define>
    <!--macro defination:geometry box-->
    <xacro_macro_define macro_name="geometry_box" params="x y z">
        <geometry>
            <box>
                <size>${x} ${y} ${z}</size>
            </box>
        </geometry>
    </xacro_macro_define>
    <!--macro defination:geometry mesh-->
    <xacro_macro_define macro_name="geometry_mesh" params="filename">
        <geometry>
            <mesh>
                <uri>${filename}</uri>
            </mesh>
        </geometry>
    </xacro_macro_define>
    <!--macro defination:visual_collision_with_mesh-->
    <xacro_macro_define macro_name="visual_collision_with_mesh" params="prefix filename">
        <visual name="${prefix}_visual">
            <geometry>
                <mesh>
                    <uri>${filename}</uri>
                </mesh>
            </geometry>
        </visual>
        <collision name="${prefix}_collision">
            <geometry>
                <mesh>
                    <uri>${filename}</uri>
                </mesh>
            </geometry>
        </collision>
    </xacro_macro_define>
</sdf>
'''

g_property_table = {}
local_property_table = {}
g_macro_params_table = {}
g_macro_node_table = {}

def try2number(str):
    try:
        return float(str)
    except ValueError:
        return str

def get_xacro(root):
    # only find in <sdf>...</sdf>
    for node in root.childNodes:
        if node.nodeType == xml.dom.Node.ELEMENT_NODE:
            if node.tagName == 'xacro_property':
                name = node.getAttribute("name")
                g_property_table[name] = try2number(node.getAttribute("value"))
                root.removeChild(node)
            elif node.tagName == 'xacro_macro_define':
                name = node.getAttribute("macro_name")
                g_macro_params_table[name] = node.getAttribute(
                    "params").split(' ')
                g_macro_node_table[name] = node.toxml()
                root.removeChild(node)

def re_eval_fn(obj):
    result = eval(obj.group(1), g_property_table, local_property_table)
    return str(result)

def eval_text(xml_str):
    pattern = re.compile(r'[$][{](.*?)[}]', re.S)
    return re.sub(pattern, re_eval_fn, xml_str)

def replace_macro_node(node):
    parent = node.parentNode
    if not node.hasAttribute("macro_name"):
        print("check <xacro_macro> block,not find attr macro_name!")
        sys.exit(1)
    name = node.getAttribute("macro_name")
    # get xml string
    xml_str = g_macro_node_table[name]
    # get local table
    local_property_table.clear()
    for param in g_macro_params_table[name]:
        local_property_table[param] = try2number(node.getAttribute(param))
    # replace macro(insert and remove)
    xml_str = eval_text(xml_str)
    new_node = xml.dom.minidom.parseString(xml_str).documentElement
    for cc in list(new_node.childNodes):
        parent.insertBefore(cc, node)
    parent.removeChild(node)

#reference: https://github.com/ros/xacro/blob/noetic-devel/src/xacro/__init__.py
def addbanner(doc,input_file_name):
    # add xacro auto-generated banner
    banner = [xml.dom.minidom.Comment(c) for c in
              [" %s " % ('=' * 83),
               " |    This document was autogenerated by xacro4sdf from %-26s | " % input_file_name,
               " |    EDITING THIS FILE BY HAND IS NOT RECOMMENDED  %-30s | " % "",
               " %s " % ('=' * 83)]]
    first = doc.firstChild
    for comment in banner:
        doc.insertBefore(comment, first)

def xacro4sdf(inputfile, outputfile):
    doc = xml.dom.minidom.parse(inputfile)
    root = doc.documentElement
    # get common xacro
    get_xacro(xml.dom.minidom.parseString(common_xacro_xml).documentElement)
    # get xacro
    get_xacro(root)
    # replace xacro property
    local_property_table.clear()
    xml_str = root.toxml()
    xml_str = eval_text(xml_str)
    new_doc = xml.dom.minidom.parseString(xml_str)
    # replace xacro macro
    for _ in range(5):
        nodes = new_doc.getElementsByTagName("xacro_macro")
        if nodes.length == 0:
            break
        else:
            for node in list(nodes):
                replace_macro_node(node)
    if new_doc.getElementsByTagName("xacro_macro").length != 0:
        print("Error:The nesting of macro defination is much deep! only support <=5")
    # output
    addbanner(new_doc,inputfile)
    try:
        with open(outputfile, 'w', encoding='UTF-8') as f:
            new_doc.writexml(f, indent='', addindent='\t', newl='\n', encoding='UTF-8')
    except Exception as err:
        print('output error:{0}'.format(err))

def error_with_exit():
    print("usage:python xacro4sdf.py inputfile \n(the name of inputfile must be xxx.xacro)")
    sys.exit(2)

if __name__ == '__main__':
    if(len(sys.argv) < 2):
        error_with_exit()
    inputfile = sys.argv[1]
    outputfile = os.path.splitext(inputfile)[0]
    if os.path.splitext(inputfile)[1] != '.xacro':
        error_with_exit()
    # run xacro4sdf
    xacro4sdf(inputfile, outputfile)
