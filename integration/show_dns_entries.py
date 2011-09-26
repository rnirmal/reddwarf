import sys

from nova import flags
from nova import utils
from nova.dns.rsdns.driver import RsDnsDriver

if __name__ == "__main__":
    print("Loading flags...")
    utils.default_flagfile(str("/home/vagrant/nova.conf"))
    FLAGS = flags.FLAGS
    FLAGS(sys.argv)

    print("Initializing RS DNS Driver...")
    driver = RsDnsDriver(raise_if_zone_missing=False)
    entries = driver.get_entries() #_by_name("admin-1")
    
    print("Showing all DNS entries:")
    for entry in entries:
        print(entry)