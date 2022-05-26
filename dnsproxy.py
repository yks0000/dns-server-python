import socket
import struct
import time

from dnslib import DNSRecord
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger

import logpublisher

logger = logpublisher.logger()


class ProxyResolver(BaseResolver):
    """
        Proxy resolver - passes all requests to upstream DNS server and
        returns response
        Note that the request/response will be each be decoded/re-encoded
        twice:
        a) Request packet received by DNSHandler and parsed into DNSRecord
        b) DNSRecord passed to ProxyResolver, serialised back into packet
           and sent to upstream DNS server
        c) Upstream DNS server returns response packet which is parsed into
           DNSRecord
        d) ProxyResolver returns DNSRecord to DNSHandler which re-serialises
           this into packet and returns to client
        In practice this is actually fairly useful for testing but for a
        'real' transparent proxy option the DNSHandler logic needs to be
        modified (see PassthroughDNSHandler)
    """

    def __init__(self, address, port):
        self.address = address
        self.port = port

    def resolve(self, request, handler):
        if handler.protocol == 'udp':
            proxy_r = request.send(self.address, self.port)
        else:
            proxy_r = request.send(self.address, self.port, tcp=True)
        reply = DNSRecord.parse(proxy_r)
        return reply


class PassthroughDNSHandler(DNSHandler):
    """
        Modify DNSHandler logic (get_reply method) to send directly to
        upstream DNS server rather then decoding/encoding packet and
        passing to Resolver (The request/response packets are still
        parsed and logged but this is not inline)
    """

    def get_reply(self, data):
        host, port = self.server.resolver.address, self.server.resolver.port

        request = DNSRecord.parse(data)
        print(f"Request: {request}")

        if self.protocol == 'tcp':
            data = struct.pack("!H", len(data)) + data
            response = self.send_tcp(data, host, port)
            response = response[2:]
        else:
            response = self.send_udp(data, host, port)

        reply = DNSRecord.parse(response)
        print(f'Reply:,{reply}')

        return response

    @staticmethod
    def send_tcp(data, host, port):
        """
            Helper function to send/receive DNS TCP request
            (in/out packets will have prepended TCP length header)
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.sendall(data)
        response = sock.recv(8192)
        length = struct.unpack("!H", bytes(response[:2]))[0]
        while len(response) - 2 < length:
            response += sock.recv(8192)
        sock.close()
        return response

    @staticmethod
    def send_udp(data, host, port):
        """
            Helper function to send/receive DNS UDP request
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(data, (host, port))
        response, server = sock.recvfrom(8192)
        sock.close()
        return response


def start_proxy_server(address="", port=8053, upstream_address="8.8.8.8",
                       upstream_port=53, pass_through=True, dns_log_prefix=False, dns_log="request,reply,truncated,error"):

    print(f"Starting Proxy Resolver ( -> {upstream_address}:{upstream_port}) [UDP]")

    resolver = ProxyResolver(upstream_address, upstream_port)
    handler = PassthroughDNSHandler if pass_through else DNSHandler
    dns_logger = DNSLogger(dns_log, dns_log_prefix)
    udp_server = DNSServer(resolver,
                           port=port,
                           address=address,
                           logger=dns_logger,
                           handler=handler)
    udp_server.start_thread()

    while udp_server.isAlive():
        time.sleep(1)


start_proxy_server()
