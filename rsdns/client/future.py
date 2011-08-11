

class FutureResource(object):
    """Polls a callback url to return a resource."""
    
    def __init__(self, manager, jobId, callbackUrl):
        self.manager = manager
        self.jobId = jobId
        self.callbackUrl = unicode(callbackUrl)
        self.result = None
        management_url = unicode(self.manager.api.client.management_url)
        import sys
        sys.__stdout__.write("AU:" + management_url + "\n")
        sys.__stdout__.write("CBURL:" + self.callbackUrl + "\n")
        if self.callbackUrl.startswith(management_url):
            self.callbackUrl = self.callbackUrl[len(management_url):]

    def call_callback(self):
        return self.manager.api.client.get(self.callbackUrl)

    def convert_callback(self, resp, body):
        raise NotImplementedError()

    def poll(self):
        if not self.result:
            resp, body = self.call_callback()
            if resp.status == 202:
                return None
            self.result = self.convert_callback(resp, body)
        return self.resource

    @property
    def ready(self):
        return (self.result or self.poll()) != None

    @property
    def resource(self):
        return self.result or self.poll()

