import argparse
import codecs
import datetime
import ipaddress
import socketserver
import sys
import threading
import traceback

from dnslib import *

import load_zones
import logpublisher
import zone_monitor
from forwarder import Forwarder

load_zones.init()

dns_forwarder = Forwarder()
logger = logpublisher.logger()


def add_soa_records(reply: DNSRecord, record: dict):
    logger.debug(f"Adding SOA as authoritative record to DNS response for {reply.questions}")
    reply.add_auth(
        *RR.fromZone(
            f"{record['mname']} 600 IN SOA {record['mname']} {record['rname']} "
            f"{record['serial']} {record['refresh']} {record['retry']} "
            f"{record['expire']} {record['minimum']}"
        )
    )


def filter_records(qtype, record_name, zone_info):
    logger.debug(f"Filtering records for {qtype} {record_name}")
    available_records = zone_info[str(qtype).lower()]
    answer_records = list(filter(lambda d: d["name"] == record_name, available_records))
    return answer_records


class BaseRequestHandler(socketserver.BaseRequestHandler):
    def get_data(self):
        raise NotImplementedError

    def send_data(self, data):
        raise NotImplementedError

    def handle(self):
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        logger.info(f"{self.__class__.__name__[:3]} request {now} ({self.client_address[0]} {self.client_address[1]}):")
        try:
            data = self.get_data()
            self.send_data(self.dns_response(data))
        except Exception as error:
            logger.error(f"Error: {str(error)}")
            traceback.print_exc(file=sys.stderr)

    @staticmethod
    def dns_response(data):
        zone_info = load_zones.zone_info
        request = DNSRecord.parse(data)

        logger.info(f"----> QUESTIONS: {request.questions}")
        reply = DNSRecord(
            DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q
        )

        qname = request.q.qname
        qn = str(qname)
        q_type = request.q.qtype
        qt_class = QTYPE[q_type]

        answer_records = filter_records(
            qtype=qt_class, record_name=qn, zone_info=zone_info
        )
        cname_response = None
        for records in answer_records:
            reply.add_answer(
                RR(
                    rname=qname,
                    rtype=getattr(QTYPE, qt_class),
                    rclass=1,
                    ttl=records.get("ttl", 300),
                    rdata=getattr(sys.modules[__name__], str(qt_class).upper())(
                        records["value"]
                    ),
                )
            )
            if qt_class == "CNAME":
                cname_response = records["value"]
                if not str(cname_response).endswith("."):
                    cname_response = f"{cname_response}."

        if cname_response:
            answer_records = filter_records(
                qtype="A", record_name=cname_response, zone_info=zone_info
            )
            if answer_records:
                for record in answer_records:
                    reply.add_answer(
                        RR(
                            rname=cname_response,
                            rtype=QTYPE.A,
                            rclass=1,
                            ttl=300,
                            rdata=A(record["value"]),
                        )
                    )
            else:
                logger.debug(f"No record found for {cname_response} as authoritative server. Querying forwarder")
                answer_records = dns_forwarder.nslookup(cname_response, qtype=QTYPE.A)
                if answer_records:
                    logger.debug(f"dns response from forwarder for {cname_response}: {answer_records}")
                    for record in answer_records:
                        reply.add_answer(
                            RR(
                                rname=cname_response,
                                rtype=QTYPE.A,
                                rclass=1,
                                ttl=300,
                                rdata=A(record),
                            )
                        )
                else:
                    logger.debug(f"no dns response from forwarder for {cname_response}")

        add_soa_records(reply, zone_info["soa"])
        short_reply = reply.short().replace("\n", " ")
        logger.debug(f"----> ANSWERS: {short_reply}")
        return reply.pack()


class TCPRequestHandler(BaseRequestHandler):
    def get_data(self):
        data = self.request.recv(8192)
        sz = int(codecs.encode(data[:2], "hex"), 16)
        if sz < len(data) - 2:
            raise Exception("Wrong size of TCP packet")
        elif sz > len(data) - 2:
            raise Exception("Too big TCP packet")
        return data[2:]

    def send_data(self, data):
        sz = codecs.decode(hex(len(data))[2:].zfill(4), "hex")
        return self.request.sendall(sz + data)


class UDPRequestHandler(BaseRequestHandler):
    def get_data(self):
        return self.request[0]

    def send_data(self, data):
        return self.request[1].sendto(data, self.client_address)


class StartDNS:
    def __init__(self, address: str, port: int):
        # for convenience, we can also use trlib.ipconstants
        self.address = str(ipaddress.ip_address(address))
        self.port = port

        if ipaddress.ip_address(self.address).version == 6:
            logger.info("Starting DNS Server on IPv6 address")
            socketserver.TCPServer.address_family = socket.AF_INET6
        else:
            logger.info("Starting DNS Server on IPv4 address")

        self.servers = [
            socketserver.ThreadingTCPServer((self.address, self.port), TCPRequestHandler),
            socketserver.ThreadingUDPServer((self.address, self.port), UDPRequestHandler),
        ]
        self.start_server()

    def start_server(self):
        logger.info(f"Starting nameserver {self.address}:{self.port}.")
        for s in self.servers:
            thread = threading.Thread(target=s.serve_forever)  # that thread will start one more thread for each request
            thread.daemon = True  # exit the server thread when the main thread terminates
            thread.start()
            logger.info(f"{s.RequestHandlerClass.__name__[:3]} server loop running in thread: {thread.name}")

        # Start Zone Monitor
        thread = threading.Thread(target=zone_monitor.monitor)
        thread.start()
        logger.info(f"Zone Monitor started in thread: {thread.name}")

        try:
            while 1:
                time.sleep(1)
                sys.stderr.flush()
                sys.stdout.flush()

        except KeyboardInterrupt:
            pass
        finally:
            for s in self.servers:
                s.shutdown()
            thread.join()


def main():
    parser = argparse.ArgumentParser(description="Start a DNS implemented in Python. Usually DNSs use UDP on port 53.")
    parser.add_argument("--address", default="127.0.0.1", type=str, help="The address to listen on.")
    parser.add_argument("--port", default=5053, type=int, help="The port to listen on.")
    args = parser.parse_args()
    StartDNS(address=args.address, port=args.port)



if __name__ == "__main__":
    main()
