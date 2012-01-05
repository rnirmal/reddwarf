"""Creates a report for the test.
"""

import atexit
import os
import shutil
import sys
import time
from os import path


class Reporter(object):

    def __init__(self, root_path):
        self.root_path = root_path
        if not path.exists(self.root_path):
            os.mkdir(self.root_path)
        for file in os.listdir(self.root_path):
            if file.endswith(".log"):
                os.remove(path.join(self.root_path, file))

    def find_all_instance_ids(self):
        instances = []
        for dir in os.listdir("/vz/private"):
            instances.append(dir)
        return instances

    def log(self, msg):
        with open("%s/report.log" % self.root_path, 'a') as file:
            file.write(msg)

    def save_syslog(self):
        try:
            shutil.copyfile("/var/log/syslog", "host-syslog.log")
        except (shutil.Error, IOError) as err:
            self.log("ERROR logging syslog : %s" % (err))

    def update_instance(self, id):
        root = "%s/%s" % (self.root_path, id)
        try:
            shutil.copyfile("/vz/private/%s/var/log/firstboot" % id,
                            "%s-firstboot.log" % root)
        except (shutil.Error, IOError) as err:
            self.log("ERROR logging firstboot for instance id %s! : %s"
                     % (id, err))
        try:
            shutil.copyfile("/vz/private/%s/var/log/syslog" % id,
                            "%s-syslog.log" % root)
        except (shutil.Error, IOError) as err:
            self.log("ERROR logging firstboot for instance id %s! : %s"
                     % (id, err))

    def update_instances(self):
        for id in self.find_all_instance_ids():
            self.update_instance(id)

    def update(self):
        self.update_instances()
        self.save_syslog()


if __name__=="__main__":
    if len(sys.argv) < 2:
        print("No report file path specified.")
    else:
        reporter = Reporter(sys.argv[1])
        atexit.register(reporter.update)
        while(True):
            time.sleep(10)
            reporter.update()

