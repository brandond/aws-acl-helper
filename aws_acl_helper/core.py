# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import socket
import stat
import sys
from asyncio.streams import FlowControlMixin, StreamWriter

import click

from . import aclmatch, squid
from .config import Config
from .metadata import RedisMetadataStore

reader, writer = None, None
logger = logging.getLogger(__name__)


def squid_inherited_socket():
    """Detect socket passed from squid via fds 0 and 1"""
    stat_in = os.fstat(0)
    stat_out = os.fstat(1)
    if os.path.samestat(stat_in, stat_out) and stat.S_ISSOCK(stat_in.st_mode):
        return socket.socket(fileno=0)
    else:
        return None


async def stdio(loop=None):
    """Set up stdin/stdout stream handlers"""
    if loop is None:
        loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)

    writer_transport, writer_protocol = await loop.connect_write_pipe(FlowControlMixin, os.fdopen(0, 'wb'))
    writer = StreamWriter(writer_transport, writer_protocol, None, loop)

    await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

    return reader, writer


async def accept_socket(sock, loop=None):
    """Setup stream handlers for an already accepted socket"""
    if loop is None:
        loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    transport, _ = await loop.connect_accepted_socket(
        lambda: protocol, sock=sock)
    writer = StreamWriter(transport, protocol, reader, loop)
    return reader, writer


async def async_input(config):
    """Handle reading lines from stdin and handing off to background task for processing"""
    loop = asyncio.get_event_loop()

    global reader, writer
    if (reader, writer) == (None, None):
        sock = squid_inherited_socket()
        if sock:
            reader, writer = await accept_socket(sock)
        else:
            logger.warn('aws-acl-helper did not detect squid socket, using stdio. See brandond/aws-acl-helper#2')
            reader, writer = await stdio()

    async with RedisMetadataStore(config) as metadata:
        while True:
            line = await reader.readline()
            logger.debug(f'STDIN: {line}')

            # Readline returns empty bystes string when the socket is closed
            if line == b'':
                return

            # Process line in background task
            loop.create_task(handle_line(metadata, line))


async def handle_line(metadata, line):
    """Run an ACL lookup request line from Squid through the processing pipeline."""
    global writer

    request = None
    result = 'BH'
    pairs = {}
    try:
        # Get a Request object with parsed fields
        request = squid.Request(line)

        # Get metadata from Redis back-end
        hostinfo = await metadata.lookup(request)

        # Use metadata to make access decision (OK, ERR, or BH)
        result, pairs = await aclmatch.test(request, hostinfo)

    except Exception as e:
        logger.error(f'Exception encountered handling request: {e}', exc_info=True)
        pairs = {'log': f'Exception encountered handling request: {e}'}
        # Only discard the request if we failed to parse the input from Squid - ensures
        # that errors are reported properly when using concurrency.
        if request is None:
            request = squid.Request(b'- -')

    # Output response to Squid
    response = request.make_response(result, pairs)
    logger.debug(f'STDOUT: {line}')

    writer.write(response)
    await writer.drain()


@click.option(
    '--debug',
    is_flag=True,
    help="Enable debug logging to STDERR."
)
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
@click.command(short_help='Handle ACL lookup requests from Squid.')
def listen(**args):
    listen_config = Config(**args)
    loop = asyncio.get_event_loop()
    if listen_config.debug_enabled:
        loop.set_debug(1)
        logging.basicConfig(level='DEBUG', format='%(message)s')
    else:
        logging.basicConfig(level='WARNING', format='%(message)s')
    loop.run_until_complete(async_input(listen_config))
