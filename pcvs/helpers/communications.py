from abc import abstractmethod

import requests

from pcvs.backend.session import Session
from pcvs.helpers.system import MetaConfig
from pcvs.testing.test import Test

sendData = False


class GenericServer:

    def __init__(self, session_id):
        self._waitlist = []
        self._metadata = {
            "rootdir": "remote server",
            "sid": session_id,
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

    def __init__(self, sid):
        super().__init__(sid)

    def send(self):
        pass

    def recv(self):
        pass


class RemoteServer(GenericServer):

    DEFAULT_SRV_ADDR = "http://localhost:5000"

    def __init__(self, sid, server_address):
        super().__init__(sid)
        if not server_address:
            server_address = self.DEFAULT_SRV_ADDR

        self._serv = server_address

        if not server_address.startswith("http"):
            self._serv = "http://" + server_address

        self.open_connection()

    def open_connection(self):
        self._json_send("/submit/session_init", {
            "sid": self._metadata['sid'],
            "state": Session.State.IN_PROGRESS,
            "buildpath": MetaConfig.root.validation.output,
            "dirs": MetaConfig.root.validation.dirs
        })

    def close_connection(self):
        self._json_send("/submit/session_fini", {
            "sid": self._metadata['sid'],
            "state": Session.State.COMPLETED
        })

    @property
    def endpoint(self):
        return self._serv

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
        return self._json_send("/submit/test", to_send)

    def _json_send(self, prefix, json_data):
        try:
            requests.post(self._serv + prefix, json=json_data, timeout=1)
            return True
        except requests.exceptions.ConnectionError:
            return False
