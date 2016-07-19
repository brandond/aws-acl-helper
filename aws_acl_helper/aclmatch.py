import asyncio
from . import squid

@asyncio.coroutine
def test(request, metadata):
    if metadata is None or len(metadata) == 0:
        return squid.Response(channel=request.channel, result='BH', pairs={'log': 'Metadata not available'})
    else:
        return squid.Response(channel=request.channel, result='OK', pairs={'user': metadata['instance_id']})

