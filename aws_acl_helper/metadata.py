import asyncio
import pickle

import aioredis

pool = None
lock = asyncio.Lock()

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


async def lookup(config, request):
    global pool
    global lock

    if request.client is None:
        return None

    metadata = None

    # standard check/lock/check pattern to ensure only one thread creates a connection pool
    if pool is None:
        async with lock:
            if pool is None:
                pool = await aioredis.create_pool((config.redis_host, config.redis_port), minsize=2, maxsize=20)

    # Call the eval script to lookup IP and retrieve instance data.
    # Could probably optimize this by storing the script server-side
    # during initial pool creation.
    with await pool as conn:
        pickle_data = await aioredis.Redis(conn).eval(KEY_SCRIPT, args=[KEY_IP, str(request.client)])
        if pickle_data is not None:
            metadata = pickle.loads(pickle_data)

    return metadata


async def store_instance(config, instance):
    redis = await aioredis.create_redis((config.redis_host, config.redis_port))
    pipe = redis.pipeline()
    instance_id = instance['instance_id']

    # Store pickled instance data keyed off instance ID
    pipe.set(key=KEY_I + instance_id, value=pickle.dumps(instance), expire=int(config.redis_ttl))

    # Store intermediate key lookups so that we can find an instance given only its IP address
    for interface in instance.get('network_interfaces', []):
        await store_interface(config, interface, KEY_I + instance_id, None)

    await pipe.execute()
    redis.close()
    await redis.wait_closed()


async def store_interface(config, interface, key=None, exist='SET_IF_NOT_EXIST'):
    redis = await aioredis.create_redis((config.redis_host, config.redis_port))
    pipe = redis.pipeline()
    interface_id = interface['network_interface_id']

    # Only store picked interface data if using default key (not fixed key from instance)
    if not key:
        key = KEY_ENI + interface_id
        pipe.set(key=KEY_ENI + interface_id, value=pickle.dumps(interface), expire=int(config.redis_ttl))

    # Store intermediate key lookups so that we can find metadata given only an IP address
    if 'association' in interface:
        pipe.set(key=KEY_IP + interface['association']['public_ip'], value=key, expire=int(config.redis_ttl), exist=exist)

    for address in interface.get('private_ip_addresses', []):
        pipe.set(key=KEY_IP + address['private_ip_address'], value=key, expire=int(config.redis_ttl), exist=exist)

    await pipe.execute()
    redis.close()
    await redis.wait_closed()


async def close():
    global pool
    global lock

    if pool is not None:
        async with lock:
            if pool is not None:
                # Wait for all pool connections to become free, indicating that no tasks are currently using it
                while pool.freesize != pool.size:
                    await asyncio.sleep(1)

                # Ask the connection pool to close any open connections, and wait for it to do so
                pool.close()
                await pool.wait_closed()
                pool = None
