# -*- coding: utf-8 -*-

import os
import sys
import click
import asyncio
import concurrent.futures

from asyncio.streams import StreamWriter, FlowControlMixin

from . import squid
from . import metadata
from . import aclmatch
from . import config

reader, writer = None, None


@asyncio.coroutine
def stdio(loop=None):
    """Set up stdin/stdout stream handlers"""
    if loop is None:
        loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)

    fdno = 0 if sys.stdin.isatty() else 1

    writer_transport, writer_protocol = yield from loop.connect_write_pipe(FlowControlMixin, os.fdopen(fdno, 'wb'))
    writer = StreamWriter(writer_transport, writer_protocol, None, loop)

    yield from loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

    return reader, writer


@asyncio.coroutine
def async_input(config,):
    """Handle reading lines from stdin and handing off to background task for processing"""
    loop = asyncio.get_event_loop()

    global reader, writer
    if (reader, writer) == (None, None):
        reader, writer = yield from stdio()

    while True:
        line = yield from reader.readline()

        # Readline returns empty bystes string when the socket is closed
        if line == b'':
            yield from metadata.close()
            return
        
        # Process line in background task
        loop.create_task(handle_line(config, line))


@asyncio.coroutine
def handle_line(config, line):
    """Run an ACL lookup request line from Squid through the processing pipeline."""
    global writer

    request = None
    result = 'BH'
    pairs = {}
    try:
        # Get a Request object with parsed fields
        request = squid.Request(line)

        # Get metadata from Redis back-end
        hostinfo = yield from metadata.lookup(config, request)

        # Use metadata to make access decision (OK, ERR, or BH)
        result, pairs = yield from aclmatch.test(request, hostinfo)
        
    except Exception as e:
        pairs = { 'log': 'Exception encountered handling request: '+str(e) }
        # Only discard the request if we failed to parse the input from Squid - ensures
        # that errors are reported properly when using concurrency.
        if request is None:
            request = squid.Request(b'- -')
        
    # Output response to Squid
    writer.write(request.make_response(result, pairs))
    yield from writer.drain()

@click.option(
    '--port',
    default=6379,
    type=int,
    help='Redis server port.'
)
@click.option(
    '--host',
    default='localhost',
    type=str,
    help='Redis server hostname.'
)
@click.command()
def listen(host, port):
    """Listen for ACL lookup request lines on stdin and write the responses on stdout"""
    redis_config = config.Config(host=host, port=port)
    asyncio.get_event_loop().run_until_complete(async_input(redis_config))
