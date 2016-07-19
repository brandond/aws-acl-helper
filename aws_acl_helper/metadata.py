import asyncio
import aioredis
import pickle

loop = asyncio.get_event_loop()
pool = None

@asyncio.coroutine
def lookup(request):
    global pool

    if request.client is None:
        return None;

    if pool is None:
        pool = yield from aioredis.create_pool(('localhost', 6379), minsize=1, maxsize=20)

    with (yield from pool) as redis:
        instance_id = yield from redis.get('{0!s}^ip-to-id^{1!s}'.format(__name__, request.client))

        if instance_id is not None:
            instance_data = yield from redis.get('{0!s}^instance^{1!s}'.format(__name__, instance_id.decode()))

            if instance_data is not None:
                return pickle.loads(instance_data)

        return None


@asyncio.coroutine
def store(instance_data):
    redis = yield from aioredis.create_redis(('localhost', 6379))
    instance_id = instance_data['instance_id']

    for interface in instance_data['network_interfaces']:
        yield from redis.set('{0!s}^ip-to-id^{1!s}'.format(__name__, interface['private_ip_address']), instance_id)
        if 'ip_address' in interface:
            yield from redis.set('{0!s}^ip-to-id^{1!s}'.format(__name__, interface['ip_address']), instance_id)

    yield from redis.set('{0!s}^instance^{1!s}'.format(__name__, instance_id), pickle.dumps(instance_data))
    redis.close()
    yield from redis.wait_closed()

