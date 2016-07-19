import asyncio
import aioredis
import pickle
import sys

loop = asyncio.get_event_loop()
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
def lookup(request):
    global pool

    if request.client is None:
        return None

    instance_data = None

    redis = yield from aioredis.create_redis(('localhost', 6379))
    pickle_data = yield from redis.eval(KEY_SCRIPT, args=[KEY_IP, str(request.client), KEY_ID])

    if pickle_data is not None:
        instance_data = pickle.loads(pickle_data)

    redis.close()
    yield from redis.wait_closed()
    return instance_data


@asyncio.coroutine
def store(instance_data):
    redis = yield from aioredis.create_redis(('localhost', 6379))
    pipe = redis.pipeline()
    instance_id = instance_data['instance_id']
    
    pipe.setex(KEY_ID + instance_id, 1800.0, pickle.dumps(instance_data))

    for interface in instance_data.get('network_interfaces', []):
        for address in interface.get('private_ip_addresses', []):
            pipe.setex(KEY_IP + address['private_ip_address'], 1800.0, instance_id)
            if 'association' in interface:
                pipe.setex(KEY_IP + interface['association']['public_ip'], 1800.0, instance_id)

    yield from pipe.execute()
    redis.close()
    yield from redis.wait_closed()
