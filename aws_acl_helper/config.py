
class Config:
    """Configuration object to store command-line options or defaults"""
    _redis_host = 'localhost'
    _redis_port = 6379
    _redis_ttl = 1800

    def __init__(self, host=None, port=None, ttl=None):
        if host is not None:
            self._redis_host = host
        if port is not None:
            self._redis_port = port
        if ttl is not None:
            self._redis_ttl = ttl

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

