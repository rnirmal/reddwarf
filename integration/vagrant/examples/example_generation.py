import httplib2
import json
import xml.dom.minidom
import sys
import os
from urlparse import urlparse
import time

DIRECTORY = None
HOST = None
ID = None
CONF = None
HEADERS={}
USERNAME=None
PASSWORD=None
TENANT=None

def http_call(name, url, method, body={}, extra=None, output=True):
    h = httplib2.Http()
    req_headers = {'User-Agent': "python-example-client",
                   'Content-Type': "application/json",
                   'Accept': "application/json"
                  }
    req_headers.update(extra)

    content_type = 'json'
    request_body = body.get(content_type, None)
    if output:
        output_request(name, url, req_headers, request_body, content_type, method=method)
    json_resp = resp, resp_content = h.request(url, method, body=request_body, headers=req_headers)
    if output:
        output_response(name, resp, resp_content, content_type)

    content_type = 'xml'
    req_headers['Accept'] = 'application/xml'
    req_headers['Content-Type'] = 'application/xml'
    request_body = body.get(content_type, None)
    if output:
        output_request(name, url, req_headers, request_body, content_type, method=method)
    xml_resp = resp, resp_content = h.request(url, method, body=request_body, headers=req_headers)
    if output:
        output_response(name, resp, resp_content, content_type)

    return json_resp, xml_resp

def output_request(name, url, headers, body, type, method='POST'):
    parsed = urlparse(url)
    with open("%srequest_%s.%s" % (DIRECTORY,name, type), "w") as f:
        f.write("%s %s HTTP/1.1\n" % (method, parsed.path))
        f.write("User-Agent: %s\n" % headers['User-Agent'])
        f.write("Host: %s\n" % parsed.netloc)
        f.write("X-Auth-Token: %s\n" % headers['X-Auth-Token'])
        f.write("X-Auth-Project-ID: %s\n" % headers['X-Auth-Project-ID'])
        f.write("Accept: %s\n" % headers['Accept'])
        f.write("Content-Type: %s\n" % headers['Content-Type'])

        if type == 'json':
            try:
                pretty_body = json.dumps(json.loads(body),sort_keys=True, indent=4)
            except Exception:
                pretty_body = ""
        else:
            try:
                pretty_body = xml.dom.minidom.parseString(body).toprettyxml()
            except Exception:
                pretty_body = ""
        f.write("\n%s\n" % pretty_body)

def output_response(name, resp, body, type):
    with open("%sresponse_%s.%s" % (DIRECTORY,name, type), "w") as f:
        version = "1.1" if resp.version == 11 else "1.0"
        f.write("HTTP/%s %s %s\n" % (version, resp.status, resp.reason))
        f.write("Content-Type: %s\n" % resp['content-type'])
        f.write("Content-Length: %s\n" % resp['content-length'])
        f.write("Date: %s\n" % resp['date'])
        if body:
            print "\n---------%s body---------\n%s\n" % (name, body)
            if type == 'json':
                try:
                    f.write("\n%s\n" % json.dumps(json.loads(body),sort_keys=True, indent=4))
                except Exception:
                    f.write("\n%s\n" % body)
            else:
                try:
                    x = xml.dom.minidom.parseString(body)
                    f.write("\n%s\n" % x.toprettyxml())
                except Exception:
                    f.write("\n%s\n" % body)

def get_auth_token_id(url, username, password, tenant):
    body = '{"passwordCredentials": {"username": "%s", "password": "%s", "tenantId": "%s"}}' % (username, password, tenant)
    h = httplib2.Http()
    req_headers = {'User-Agent': "python-example-client",
                   'Content-Type': "application/json",
                   'Accept': "application/json",
                  }
    resp, body = h.request(url, 'POST', body=body, headers=req_headers)
    auth = json.loads(body)
    id = auth['auth']['token']['id']
    return id

def load_example_configuration(file_path):
    if not os.path.exists(file_path):
        raise RuntimeError("Could not find Example CONF at " + file_path + ".")
    file_contents = open(file_path, "r").read()
    try:
        return json.loads(file_contents)
    except Exception as exception:
        raise RuntimeError("Error loading conf file \"" + file_path + "\".",
            exception)


def wait_for_instances():
    example_instances = []
    # wait for instances
    while True:
        url = "%s/v1.0/%s/instances" % (HOST, TENANT)
        resp_json, resp_xml = http_call("get_instances", url, 'GET', extra=HEADERS, output=False)
        resp_content = json.loads(resp_json[1])
        print "resp_json : %s" % json.dumps(resp_content, sort_keys=True, indent=4)
        instances = resp_content['instances']
        list_id_status = [(instance['id'], instance['status']) for instance in instances if
                                                               instance['status'] in ['ACTIVE', 'ERROR', 'FAILED']]
        print "\nlist of id's and status -----\n%s\n" % list_id_status
        if len(list_id_status) == 2:
            statuses = [item[1] for item in list_id_status]
            if statuses.count('ACTIVE') != 2:
                break
            example_instances = [inst[0] for inst in list_id_status]
            print "\ninstance id list ---\n%s\n" % example_instances
            break
        else:
            time.sleep(15)
        # instances should be ready now.
    return example_instances

def check_clean():
    url = "%s/v1.0/%s/instances" % (HOST, TENANT)
    resp_json, resp_xml = http_call("get_instances", url, 'GET', extra=HEADERS, output=False)
    resp_content = json.loads(resp_json[1])
    instances = resp_content['instances']
    if len(instances) > 0:
        raise Exception("Environment must be clean to run the example generator.")
    print "\n\nClean environment building examples...\n\n"


def setup():
    global DIRECTORY, HOST, USERNAME, PASSWORD, TENANT, HEADERS
    DIRECTORY = CONF.get("directory", None)
    if DIRECTORY[-1] != '/':
        DIRECTORY += '/'
    print "DIRECTORY = %s" % DIRECTORY
    HOST = CONF.get("api_url", None)
    print "HOST = %s" % HOST
    #auth
    url = CONF.get("auth_url", None)
    print "url = %s" % url
    USERNAME = CONF.get("username", None)
    print "USERNAME = %s" % USERNAME
    PASSWORD = CONF.get("password", None)
    print "PASSWORD = %s" % PASSWORD
    TENANT = CONF.get("tenant", None)
    print "TENANT = %s" % TENANT
    ID = get_auth_token_id(url, USERNAME, PASSWORD, TENANT)
    print "ID = %s" % ID
    HEADERS['X-Auth-Token'] = ID
    HEADERS['X-Auth-Project-ID'] = TENANT


def main():

    # Setup the global variables and authenticate
    setup()
    check_clean()

    #no auth required
    #list versions
    url = "%s/" % HOST
    http_call("versions", url, 'GET', extra=HEADERS)

    #requires auth
    #list version
    url = "%s/v1.0/" % HOST
    http_call("version", url, 'GET', extra=HEADERS)

    # flavors
    url = "%s/v1.0/%s/flavors" % (HOST, TENANT)
    http_call("flavors", url, 'GET', extra=HEADERS)

    #flavors details
    url = "%s/v1.0/%s/flavors/detail" % (HOST, TENANT)
    http_call("flavors_detail", url, 'GET', extra=HEADERS)

    #flavors by id
    url = "%s/v1.0/%s/flavors/1" % (HOST, TENANT)
    http_call("flavors_by_id", url, 'GET', extra=HEADERS)

    #create instance json
    url = "%s/v1.0/%s/instances" % (HOST, TENANT)
    JSON_DATA = {
        "instance": {
        "name": "json_rack_instance",
            "flavorRef": "%s/v1.0/%s/flavors/1" % (HOST, TENANT),
            "databases": [
                {
                    "name": "sampledb",
                    "character_set": "utf8",
                    "collate": "utf8_general_ci"
                },
                {
                    "name": "nextround"
                }
            ],
            "volume":
                {
                    "size": "2"
                }
        }
    }
    XML_DATA = '<?xml version="1.0" ?>' \
               '<instance xmlns="http://docs.openstack.org/database/api/v1.0" name="xml_rack_instance" flavorRef="%s/v1.0/%s/flavors/1">' \
                    '<databases>' \
                        '<database name="sampledb" character_set="utf8" collate="utf8_general_ci" />' \
                        '<database name="nextround" />' \
                    '</databases>' \
                    '<volume size="2" />' \
               '</instance>' % (HOST, TENANT)
    print "=====xml body======\n%s\n" % XML_DATA
    body = {'xml': XML_DATA,'json': json.dumps(JSON_DATA)}
    http_call("create_instance", url, 'POST', body=body, extra=HEADERS)

    # this will be used later to make instance related calls
    example_instances = wait_for_instances()
    if len(example_instances) != 2:
        print("------------------------------------------------------------")
        print("------------------------------------------------------------")
        print("SOMETHING WENT WRONG CREATING THE INSTANCES FOR THE EXAMPLES")
        print("------------------------------------------------------------")
        print("------------------------------------------------------------")
        return 1

    instance_id = example_instances[0]
#    instance_id = "c4a69fae-0aa0-4041-b0fc-f61cc03c01f6"
    database_name = "exampledb"
    user_name = "testuser"
    print "\nusing instance id(%s) for these calls\n" % instance_id

    # create database on instance
    url = "%s/v1.0/%s/instances/%s/databases" % (HOST, TENANT, instance_id)
    JSON_DATA = {
        "databases": [
            {
                "name": "testingdb",
                "character_set": "utf8",
                "collate": "utf8_general_ci"
            },

            {
                "name": "sampledb"
            }
        ]
    }
    XML_DATA = '<?xml version="1.0" ?>' \
               '<Databases xmlns="http://docs.openstack.org/database/api/v1.0">' \
                '<Database name="%s" character_set="utf8" collate="utf8_general_ci" />' \
                '<Database name="anotherexampledb" />' \
            '</Databases>' % database_name
    body = {'xml': XML_DATA,'json': json.dumps(JSON_DATA)}
    http_call("create_databases", url, 'POST', body=body, extra=HEADERS)

    # list databases on instance
    url = "%s/v1.0/%s/instances/%s/databases" % (HOST, TENANT, instance_id)
    http_call("list_databases", url, 'GET', extra=HEADERS)

    # delete databases on instance
    url = "%s/v1.0/%s/instances/%s/databases/%s" % (HOST, TENANT, instance_id, database_name)
    http_call("delete_databases", url, 'DELETE', extra=HEADERS)

    # create user
    url = "%s/v1.0/%s/instances/%s/users" % (HOST, TENANT, instance_id)
    JSON_DATA = {
        "users": [
            {
                "name": "dbuser3",
                "password": "password",
                "database": "databaseA"
            },
            {
                "name": "dbuser4",
                "password": "password",
                "databases": [
                    {
                        "name": "databaseB"
                    },
                    {
                        "name": "databaseC"
                    }
                ]
            }
        ]
    }
    XML_DATA = '<?xml version="1.0" ?>' \
               '<users xmlns="http://docs.openstack.org/database/api/v1.0">' \
                   '<user name="%s" password="password" database="databaseC"/>' \
                   '<user name="userwith2dbs" password="password">' \
                       '<databases>' \
                           '<database name="databaseA"/>' \
                           '<database name="databaseB"/>' \
                       '</databases>' \
                   '</user>' \
               '</users>' % user_name
    body = {'xml': XML_DATA,'json': json.dumps(JSON_DATA)}
    http_call("create_users", url, 'POST', body=body, extra=HEADERS)

    # list users on instance
    url = "%s/v1.0/%s/instances/%s/users" % (HOST, TENANT, instance_id)
    http_call("list_users", url, 'GET', extra=HEADERS)

    # delete user on instance
    url = "%s/v1.0/%s/instances/%s/users/%s" % (HOST, TENANT, instance_id, user_name)
    http_call("delete_users", url, 'DELETE', extra=HEADERS)

    # enable root access on instance
    url = "%s/v1.0/%s/instances/%s/root" % (HOST, TENANT, instance_id)
    http_call("enable_root_user", url, 'POST', extra=HEADERS)

    # check root user access on instance
    url = "%s/v1.0/%s/instances/%s/root" % (HOST, TENANT, instance_id)
    http_call("check_root_user", url, 'GET', extra=HEADERS)

    # list instances index call
    url = "%s/v1.0/%s/instances" % (HOST, TENANT)
    http_call("instances_index", url, 'GET', extra=HEADERS)

    # list instances details call
    url = "%s/v1.0/%s/instances/detail" % (HOST, TENANT)
    http_call("instances_detail", url, 'GET', extra=HEADERS)

    # get instance details
    url = "%s/v1.0/%s/instances/%s" % (HOST, TENANT, instance_id)
    http_call("instance_status_detail", url, 'GET', extra=HEADERS)

    # delete instance
    url = "%s/v1.0/%s/instances/%s" % (HOST, TENANT, instance_id)
    http_call("delete_instance", url, 'DELETE', extra=HEADERS)

    # clean up other instance
    url = "%s/v1.0/%s/instances/%s" % (HOST, TENANT, example_instances[1])
    http_call("delete_instance", url, 'DELETE', extra=HEADERS, output=False)


if __name__ == "__main__":
    print("RUNNING ARGS :  " + str(sys.argv))
    for arg in sys.argv[1:]:
        conf_file = os.path.expanduser(arg)
        print("Setting CONF to " + conf_file)
        CONF = load_example_configuration(conf_file)
    main()
