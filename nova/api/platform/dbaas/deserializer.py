# Copyright 2010 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from xml.dom import minidom


from nova import exception
from nova import flags
from nova import utils


FLAGS = flags.FLAGS


class RequestJSONDeserializer(object):
    """
    Deserialize Json requests
    """

    def deserialize_create(self, body):
        """Just load the request body as json"""
        request = self._add_image_ref(utils.loads(body))
        return utils.dumps({'server': request['dbcontainer']})

    def _add_image_ref(self, body):
        body['dbcontainer']['imageRef'] = FLAGS.reddwarf_imageRef
        return body


class RequestXMLDeserializer(object):
    """
    Deserializer to handle xml-formatted requests
    """

    def deserialize_create(self, string):
        """Deserialize an xml formatted server create request"""
        dom = minidom.parseString(string)
        dbcontainer = self._extract_dbcontainer(dom)
        server_node = self._rename_to_server(dom)
        server_body = self._add_image_ref(server_node)
        return {'dbcontainer': dbcontainer}, server_body

    def _add_image_ref(self, node):
        imageRef = minidom.Attr("imageRef")
        imageRef.value = FLAGS.reddwarf_imageRef
        node.setAttributeNode(imageRef)
        return node.toxml()

    def deserialize_databases(self, string):
        """Deserialize an xml formatted create databases request"""
        dom = minidom.parseString(string)
        return {'databases': self._extract_databases(dom)}

    def deserialize_users(self, string):
        """Deserialize an xml formatted create users request"""
        dom = minidom.parseString(string)
        return {'users': self._extract_users(dom)}

    def _rename_to_server(self, node):
        """Rename dbcontainer to server for processing by the serves code"""
        dbcontainer_node = self._find_first_child_named(node, "dbcontainer")
        node.renameNode(dbcontainer_node, "", "server")
        return dbcontainer_node

    def _extract_dbcontainer(self, node):
        """Marshal the dbcontainer attributes of a parsed request"""
        dbcontainer = {}
        dbcontainer_node = self._find_first_child_named(node, "dbcontainer")
        for attr in ["name", "port", "imageRef", "flavorRef"]:
            dbcontainer[attr] = dbcontainer_node.getAttribute(attr)
        #dbtype = self._extract_dbtype(dbcontainer_node)
        databases = self._extract_databases(dbcontainer_node)
        if databases is not None:
            dbcontainer["databases"] = databases
        #dbcontainer["dbtype"] = dbtype
        return dbcontainer

    def _extract_dbtype(self, node):
        """Marshal the dbtype attributes of a parsed request"""
        dbtype_node = self._find_first_child_named(node, "dbtype")
        if dbtype_node is None:
            raise exception.ApiError("Required element 'dbtype' not specified")
        dbtype = {}
        for attr in ["name", "version"]:
            dbtype[attr] = dbtype_node.getAttribute(attr)
        return dbtype

    def _extract_databases(self, node):
        """Extract the databases attributes"""
        databases = self._find_first_child_named(node, "databases")
        if databases is None:
            database_nodes = self._find_children_named(node, "database")
        else:
            database_nodes = self._find_children_named(databases, "database")
        if database_nodes is None:
            return None

        databases = []
        for database in database_nodes:
            db = dict()
            for attr in ["name", "character_set", "collate"]:
                db[attr] = database.getAttribute(attr)
            databases.append(db)
        return databases

    def _extract_users(self, node):
        """Extract user attributes"""
        users = self._find_first_child_named(node, "users")
        if users is None:
            return None
        else:
            user_nodes = self._find_children_named(users, "user")

        users = []
        for user in user_nodes:
            user_data = dict()
            for attr in ["name", "password", "database"]:
                if user.hasAttribute(attr):
                    user_data[attr] = user.getAttribute(attr)
            dbs_node = self._find_first_child_named(user, "databases")
            if dbs_node is not None:
                databases = self._extract_databases(dbs_node)
                if databases:
                    user_data["databases"] = databases
            users.append(user_data)
        return users

    def _find_first_child_named(self, parent, name):
        """Search a nodes children for the first child with a given name"""
        for node in parent.childNodes:
            if node.nodeName.lower() == name.lower():
                return node
        return None

    def _find_children_named(self, parent, name):
        """Return all of a nodes children who have the given name"""
        for node in parent.childNodes:
            if node.nodeName.lower() == name.lower():
                yield node

    def _extract_text(self, node):
        """Get the text field contained by the given node"""
        if len(node.childNodes) == 1:
            child = node.childNodes[0]
            if child.nodeType == child.TEXT_NODE:
                return child.nodeValue
        return ""
