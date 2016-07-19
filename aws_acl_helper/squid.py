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

        addr = parts.pop(0)
        if addr != '-':
            try:
                self.client = ipaddress.ip_address(addr)
            except ValueError:
                pass

        self.acl = parts

    def make_response(self, result='BH', pairs=dict()):
        chan = None
        pair = None
        valid_pairs = {}

        for key, value in pairs.items():
            if key[0] == '_' or key in squid_tags:
                valid_pairs[key] = value
            else:
                # FIXME - log this
                pass

        if self.channel != -1:
            chan = str(self.channel)
        
        if len(valid_pairs) > 0:
            pair = ' '.join(['{}={}'.format(item[0], quote(item[1])) for item in valid_pairs.items()])

        line = ' '.join([p for p in [chan, result, pair] if p is not None])+'\r\n'
        return line.encode()
