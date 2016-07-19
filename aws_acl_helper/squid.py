import ipaddress
from urllib.parse import quote, unquote

squid_tags = frozenset(['clt_conn_tag', 'group', 'log', 'message', 'password', 'tag', 'ttl', 'user'])

class Request:
    channel = -1
    client = None
    acl = list()

    def __init__(self, line):
        parts = line.decode().replace('\r', '').replace('\n', '').split(' ')
        try:
            self.channel = int(parts[0])
            parts.pop(0)
        except ValueError:
            pass

        self.client = ipaddress.ip_address(parts.pop(0))
        self.acl = parts

class Response:
    channel = -1
    result = 'BH'
    kv_pairs = dict()

    def __init__(self, channel=-1, result='BH', pairs=dict()):
        self.channel = channel
        self.result = result

        for key, value in pairs.items():
            if key[0] == '_' or key in squid_tags:
                self.kv_pairs[key] = value
            else:
                # FIXME - log this
                pass

    def __str__(self):
        chan = None
        pair = None

        if self.channel != -1:
            chan = str(self.channel)
        
        if len(self.kv_pairs) > 0:
            pair = ' '.join(['{}={}'.format(item[0], quote(item[1])) for item in self.kv_pairs.items()])

        return ' '.join([p for p in [chan, self.result, pair] if p is not None])+'\r\n'
