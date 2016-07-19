import asyncio
import aioredis
import pickle
import sys

loop = asyncio.get_event_loop()

@asyncio.coroutine
def lookup(request):
    global pool

    if request.client is None:
        return None;

    instance_data = None

    redis = yield from aioredis.create_redis(('localhost', 6379))
    instance_id = yield from redis.get('{0!s}^ip-to-id^{1!s}'.format(__name__, request.client))

    if instance_id is not None:
        pickle_data = yield from redis.get('{0!s}^instance^{1!s}'.format(__name__, instance_id.decode()))

        if pickle_data is not None:
            instance_data = pickle.loads(pickle_data)

    redis.close()
    yield from redis.wait_closed()
    return instance_data


@asyncio.coroutine
def store(instance_data):
    redis = yield from aioredis.create_redis(('localhost', 6379))
    instance_id = instance_data['instance_id']

    for interface in instance_data['network_interfaces']:
        yield from redis.setex('{0!s}^ip-to-id^{1!s}'.format(__name__, interface['private_ip_address']), 1800.0, instance_id)
        if 'public_ip' in interface:
            yield from redis.setex('{0!s}^ip-to-id^{1!s}'.format(__name__, interface['public_ip']), 1800.0, instance_id)

    yield from redis.setex('{0!s}^instance^{1!s}'.format(__name__, instance_id), 1800.0, pickle.dumps(instance_data))
    redis.close()
    yield from redis.wait_closed()
