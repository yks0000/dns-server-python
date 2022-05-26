from typing import Union

import dns.resolver
from dnslib import QTYPE

import logpublisher

logger = logpublisher.logger()


class Forwarder:

    def __init__(self, forwarder: list = None):
        if forwarder is None:
            forwarder = ["8.8.8.8"]
        self.forwarder = forwarder
        logger.info(f"initializing DNS forwarder for CNAME chasing. Forwarder : {self.forwarder}")

    def _get_resolver(self):
        resolver = dns.resolver.Resolver()
        resolver.nameservers = self.forwarder
        resolver.timeout = 2
        resolver.lifetime = 2
        return resolver

    def nslookup(self, endpoint: str, qtype: Union[int, str, QTYPE.__class__] = QTYPE.A):
        logger.info(f"dns forward request received for {endpoint}, rtype={qtype}")
        try:
            resolver = self._get_resolver()
            answers = resolver.query(endpoint, qtype)
            response = [answer.to_text() for answer in answers]
            return response
        except (dns.exception.Timeout, dns.exception.DNSException) as dns_error:
            logger.error(f"forwarder error: {str(dns_error)}")
            return False
        except Exception as error:
            logger.error(f"generic error: {str(error)}")
            return False
