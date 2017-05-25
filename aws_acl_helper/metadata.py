import asyncio
import pickle
import sys

import aioredis

pool = None
lock = asyncio.Lock()

# Redis key prefixes
KEY_IP = __name__ + '^ip-to-id^'
KEY_ID = __name__ + '^instance^'

# Note - this script will not work with clustered Redis due to
# use of dynamic key names. Should be fine as long as we're only
# useing a single local node.
KEY_SCRIPT = """
local instance = redis.call('get', ARGV[1]..ARGV[2])
if instance then
  return redis.call('get', ARGV[3]..instance)
end
"""


@asyncio.coroutine
def lookup(config, request):
    global pool
    global lock

    if request.client is None:
        return None

    instance_data = None

    # standard check/lock/check pattern to ensure only one thread creates a connection pool
    if pool is None:
        with (yield from lock):
            if pool is None:
                pool = yield from aioredis.create_pool((config.redis_host, config.redis_port), minsize=2, maxsize=20)

    # Call the eval script to lookup IP and retrieve instance data.
    # Could probably optimize this by storing the script server-side
    # during initial pool creation.
    with (yield from pool) as redis:
        pickle_data = yield from redis.eval(KEY_SCRIPT, args=[KEY_IP, str(request.client), KEY_ID])
        if pickle_data is not None:
            instance_data = pickle.loads(pickle_data)

    return instance_data


@asyncio.coroutine
def store(config, instance_data):
    redis = yield from aioredis.create_redis((config.redis_host, config.redis_port))
    pipe = redis.pipeline()
    instance_id = instance_data['instance_id']

    # Store pickled data keyed off instance ID
    pipe.setex(KEY_ID + instance_id, float(config.redis_ttl), pickle.dumps(instance_data))

    # Store intermediate key lookups so that we can find an instance given only its IP address
    for interface in instance_data.get('network_interfaces', []):
        for address in interface.get('private_ip_addresses', []):
            pipe.setex(KEY_IP + address['private_ip_address'], float(config.redis_ttl), instance_id)
            if 'association' in interface:
                pipe.setex(KEY_IP + interface['association']['public_ip'], float(config.redis_ttl), instance_id)

    yield from pipe.execute()
    redis.close()
    yield from redis.wait_closed()


@asyncio.coroutine
def close():
    global pool
    global lock

    if pool is not None:
        with (yield from lock):
            if pool is not None:
                # Wait for all pool connections to become free, indicating that no tasks are currently using it
                while pool.freesize != pool.size:
                    yield from asyncio.sleep(1)

                # Ask the connection pool to close any open connections, and wait for it to do so
                pool.close()
                yield from pool.wait_closed()
                pool = None
