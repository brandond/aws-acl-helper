# -*- coding: utf-8 -*-

import os
import sys
import click
import asyncio

from asyncio.streams import StreamWriter, FlowControlMixin

from . import squid
from . import metadata
from . import aclmatch

reader, writer = None, None


@asyncio.coroutine
def stdio(loop=None):
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
def async_input(loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    global reader, writer
    if (reader, writer) == (None, None):
        reader, writer = yield from stdio()

    while True:
        line = yield from reader.readline()
        if line == b'':
            return
        
        loop.create_task(handle_line(line, writer))


@asyncio.coroutine
def handle_line(line, writer):
    request = None
    result = 'BH'
    pairs = {}
    try:
        # Get a Request object with parsed fields
        request = squid.Request(line)

        # Get metadata from back-end
        hostinfo = yield from metadata.lookup(request)

        # Use metadata to make access decision (OK or ERR)
        result, pairs = yield from aclmatch.test(request, hostinfo)
        
    except Exception as e:
        pairs = { 'log': 'Exception encountered handling request: '+str(e) }
        if request is None:
            request = squid.Request(b'- -')
        
    # Output response to Squid
    writer.write(request.make_response(result, pairs))
    yield from writer.drain()


@click.command()
def listen():
    asyncio.get_event_loop().run_until_complete(async_input())
