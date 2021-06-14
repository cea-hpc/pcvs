from abc import abstractmethod
from pcvs.testing.test import Test
from flask import Flask, request, render_template
import json
import requests

sendData = False

class GenericServer:

    def __init__(self):
        self._waitlist = []
        self._metadata = {
            "rootdir": "remote server",
            "count": {
            }
        }

    @abstractmethod
    def send(self, data):
        pass

    @abstractmethod
    def recv(self):
        pass


class EmbeddedServer(GenericServer):

    def __init__(self):
        super().__init__()

    def send(self):
        pass

    def recv(self):
        pass


class RemoteServer(GenericServer):

    def __init__(self, server_address):
        super().__init__()
        if not server_address.startswith("http"):
            self._serv = "http://" + server_address

    def send(self, test):
        if self._send_unitary_test(test):
            self.retry_pending()
        else:
            self._waitlist.append(test)

    def retry_pending(self):
        while len(self._waitlist) > 0:
            prev_test = self._waitlist.pop()
            if not self._send_unitary_test(prev_test):
                self._waitlist.append(prev_test[1])

    def _send_unitary_test(self, test):
        assert(isinstance(test, Test))
        to_send = {"metadata": self._metadata,
                   "test_data": test.to_json(),
                   "state": test.state}
        try:
            requests.post(self._serv + "/submit", json=to_send, timeout=1)
            return True
        except requests.exceptions.ConnectionError:
            return False
