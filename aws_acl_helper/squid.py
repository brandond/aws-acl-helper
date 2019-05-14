import ipaddress
from urllib.parse import quote, unquote

# Valid response keywords
_squid_keywords = frozenset(['clt_conn_tag', 'group', 'log', 'message', 'password', 'tag', 'ttl', 'user'])


class Request:
    """Container object for Squid ACL lookup request"""
    _channel = -1
    _client = None
    _acl = list()

    def __init__(self, line):
        """Parse a lookup request from Squid into its constituent parts"""
        parts = line.decode().replace('\n', '').split(' ')

        # See if we're using concurrency; if so the first token is the integer channel ID
        try:
            self._channel = int(parts[0])
            parts.pop(0)
        except ValueError:
            pass

        # First non-channel argument must be the client IP address
        # Failure to parse the client address is handled later on
        # by detecting the object's client property being None.
        addr = parts.pop(0)
        if addr != '-':
            try:
                self._client = ipaddress.ip_address(addr)
            except ValueError:
                pass

        # Everything else is ACL arguments
        self._acl = [unquote(p) for p in parts]

    @property
    def client(self):
        """IP address of the client that made the current request"""
        return self._client

    @property
    def acl(self):
        """List of ACL entries to test the current request against"""
        return self._acl

    def make_response(self, result='BH', pairs=dict()):
        """Create a response to this request
            result: ACL result (OK, ERR, or BH)
            pairs: dictionary of keywords to append to the response.

            See the Squid documentation for valid keywords:
            http://wiki.squid-cache.org/Features/AddonHelpers#Access_Control_.28ACL.29
        """
        chan = None
        pair = None
        keywords = {}

        # Check for valid keywords; underscore suffix is reserved for admin use
        # reference: http://wiki.squid-cache.org/Features/AddonHelpers#Access_Control_.28ACL.29
        for key, value in pairs.items():
            if key[-1] == '_' or key in _squid_keywords:
                keywords[key] = value
            else:
                # FIXME - log this
                pass

        # Include channel if it was specified in the request
        if self._channel != -1:
            chan = str(self._channel)

        # Join together valid keywords
        if len(keywords) > 0:
            pair = ' '.join([f'{item[0]}={quote(item[1])}' for item in keywords.items()])

        # Only include defined items in response line
        line = ' '.join([p for p in [chan, result, pair] if p is not None])+'\n'
        return line.encode()
