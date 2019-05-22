import asyncio
import logging
import pickle

import aioredis

logger = logging.getLogger(__name__)

# Redis key prefixes
KEY_ENI = __name__ + '^interface^'
KEY_IP = __name__ + '^ip-to-md^'
KEY_I = __name__ + '^instance^'

# Note - this script will not work with clustered Redis due to
# use of dynamic key names. Should be fine as long as we're only
# useing a single local node.
KEY_SCRIPT = """
local metadata_key = redis.call('get', ARGV[1]..ARGV[2])
if metadata_key then
  return redis.call('get', metadata_key)
end
"""


class RedisMetadataReader(object):
    def __init__(self, config):
        self.config = config
        self.pool = None

    async def __aenter__(self):
        try:
            self.pool = await aioredis.create_pool((self.config.redis_host, self.config.redis_port), minsize=1, maxsize=20)
            return self
        except Exception as e:
            logger.error(f'Unable to connect to Redis server: {e}')
            raise SystemExit(1)

    async def __aexit__(self, exc_type, exc, tb):
        if self.pool is not None:
            # Wait for all pool connections to become free, indicating that no tasks are currently using it
            while self.pool.freesize != self.pool.size:
                await asyncio.sleep(1)

            # Ask the connection pool to close any open connections, and wait for it to do so
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None

    async def lookup(self, request):
        if request.client is None:
            return None

        metadata = None

        # Call the eval script to lookup IP and retrieve instance data.
        # Could probably optimize this by storing the script server-side
        # during initial pool creation.
        with await self.pool as conn:
            pickle_data = await aioredis.Redis(conn).eval(KEY_SCRIPT, args=[KEY_IP, str(request.client)])
            if pickle_data is not None:
                metadata = pickle.loads(pickle_data)

        return metadata


class RedisMetadataWriter(object):
    def __init__(self, config):
        self.config = config
        self.conn = None

    async def __aenter__(self):
        try:
            self.conn = await aioredis.create_connection((self.config.redis_host, self.config.redis_port))
            await self.conn.execute('MULTI')
            return self
        except Exception as e:
            logger.error(f'Unable to connect to Redis server: {e}')
            raise SystemExit(1)

    async def __aexit__(self, exc_type, exc, tb):
        if self.conn is not None:
            await self.conn.execute('EXEC')
            self.conn.close()
            await self.conn.wait_closed()
            self.conn = None

    async def store_instance(self, instance):
        instance_id = instance['instance_id']

        for interface in instance.get('network_interfaces', []):
            await self.store_interface(interface, KEY_I + instance_id)

        redis = aioredis.Redis(self.conn)

        # Store pickled instance data keyed off instance ID
        await redis.set(key=KEY_I + instance_id, value=pickle.dumps(instance, pickle.HIGHEST_PROTOCOL), expire=int(self.config.redis_ttl))

    async def store_interface(self, interface, key=None):
        redis = aioredis.Redis(self.conn)
        interface_id = interface['network_interface_id']

        # Only store picked interface data if using default key (not fixed key from instance)
        if not key:
            key = KEY_ENI + interface_id
            await redis.set(key=KEY_ENI + interface_id, value=pickle.dumps(interface, pickle.HIGHEST_PROTOCOL), expire=int(self.config.redis_ttl))

        # Store intermediate key lookups so that we can find metadata given only an IP address
        if 'association' in interface:
            await redis.set(key=KEY_IP + interface['association']['public_ip'], value=key, expire=int(self.config.redis_ttl))

        for address in interface.get('private_ip_addresses', []):
            await redis.set(key=KEY_IP + address['private_ip_address'], value=key, expire=int(self.config.redis_ttl))
