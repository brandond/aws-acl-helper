
class Config:
    """Configuration object to store command-line options or defaults"""
    _redis_host = 'localhost'
    _redis_port = 6379
    _redis_ttl = 1800
    _profile_name = None
    _region_name = None
    _debug = False

    def __init__(self, host=None, port=None, ttl=None, profile=None, region=None, debug=False):
        if host is not None:
            self._redis_host = host
        if port is not None:
            self._redis_port = port
        if ttl is not None:
            self._redis_ttl = ttl
        if profile is not None:
            self._profile_name = profile
        if region is not None:
            self._region_name = region
        if debug is not False:
            self._debug = True

    @property
    def redis_host(self):
        """Hostname or address of Redis server"""
        return self._redis_host

    @property
    def redis_port(self):
        """Port of Redis server"""
        return self._redis_port

    @property
    def redis_ttl(self):
        """Expiration time for AWS metadata stored in Redis"""
        return self._redis_ttl

    @property
    def profile_name(self):
        """AWS Configuration Profile name"""
        return self._profile_name

    @property
    def region_name(self):
        """AWS Region name"""
        return self._region_name

    @property
    def debug_enabled(self):
        """Debug Flag Status"""
        return self._debug
