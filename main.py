import argparse
import datetime
import json
import socketserver
import threading
import traceback
import sys
import logpublisher
from dnslib import *
import load_zones
import zone_monitor

load_zones.init()

logger = logpublisher.logger()


def add_soa_records(reply: DNSRecord, record: dict):
    logger.debug(f"Adding SOA as authoritative record to DNS response for {reply.questions}")
    mname = record['mname']
    ttl = 600
    mail_addr = record['rname']
    serial = record['serial']
    refresh = record['refresh']
    retry = record['retry']
    expire = record['expire']
    minimum = record['minimum']
    reply.add_auth(*RR.fromZone(f"{mname} {ttl} IN SOA {mname} {mail_addr} {serial} {refresh} {retry} {expire} {minimum}"))


def filter_records(qtype, record_name, zone_info):
    logger.debug(f"Filtering records for {qtype} {record_name}")
    available_records = zone_info[str(qtype).lower()]
    answer_records = list(filter(lambda d: d['name'] == record_name, available_records))
    return answer_records


def dns_response(data):
    zone_info = load_zones.zone_info
    request = DNSRecord.parse(data)

    logger.info(f'----> QUESTIONS: {request.questions}')
    reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)

    qname = request.q.qname
    qn = str(qname)
    q_type = request.q.qtype
    qt_class = QTYPE[q_type]

    answer_records = filter_records(qtype=qt_class, record_name=qn, zone_info=zone_info)
    cname_response = None
    for records in answer_records:
        reply.add_answer(RR(rname=qname, rtype=getattr(QTYPE, qt_class), rclass=1, ttl=records.get("ttl", 300),
                            rdata=getattr(sys.modules[__name__], str(qt_class).upper())(records['value'])))
        if qt_class == "CNAME":
            cname_response = records['value']
            if not str(cname_response).endswith("."):
                cname_response = f"{cname_response}."

    if cname_response:
        answer_records = filter_records(qtype="A", record_name=cname_response, zone_info=zone_info)
        if answer_records:
            for record in answer_records:
                reply.add_answer(RR(rname=cname_response, rtype=QTYPE.A, rclass=1, ttl=300, rdata=A(record['value'])))
        else:
            logger.debug(f"No record found for {cname_response} as authoritative server.")

    add_soa_records(reply, zone_info['soa'])
    logger.debug(f"---->ANSWERS:\n{reply}")
    return reply.pack()


class BaseRequestHandler(socketserver.BaseRequestHandler):

    def get_data(self):
        raise NotImplementedError

    def send_data(self, data):
        raise NotImplementedError

    def handle(self):
        now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
        logger.info(f"{self.__class__.__name__[:3]} request {now} ({self.client_address[0]} {self.client_address[1]}):")
        try:
            data = self.get_data()
            self.send_data(dns_response(data))
        except Exception as error:
            logger.error(f"Error: {str(error)}")
            traceback.print_exc(file=sys.stderr)


class UDPRequestHandler(BaseRequestHandler):

    def get_data(self):
        return self.request[0].strip()

    def send_data(self, data):
        return self.request[1].sendto(data, self.client_address)


def main():
    parser = argparse.ArgumentParser(description='Start a DNS implemented in Python. Usually DNSs use UDP on port 53.')
    parser.add_argument('--port', default=5053, type=int, help='The port to listen on.')
    args = parser.parse_args()
    logger.info(f"Starting nameserver on port {args.port}. Protocol: UDP")

    servers = [socketserver.ThreadingUDPServer(('', args.port), UDPRequestHandler)]

    for s in servers:
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
        for s in servers:
            s.shutdown()
        thread.join()


if __name__ == '__main__':
    main()
