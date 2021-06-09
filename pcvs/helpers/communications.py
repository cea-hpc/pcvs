from flask import Flask, request, render_template
import json
import requests

CommManager = None
sendData = False

def initserver(kind="remote"):
    global CommManager
    if kind=="remote":
        CommManager = RemoteServer()
    elif kind == "embedded":
        CommManager = EmbeddedServer()
class GenericServer:
    def __init__(self):
        self.labels=[]
        self.tags = []
        self.waiting = []
        self.metadata = {
            "rootdir": "remote server",
            "count": {
                "tests": 0,
                "labels": 0,
                "tags": 0,
                "files": 0
            }
        }
        
        pass
    def send(self, data):
        #TODO
        pass
    def recv(self):
        #TODO
        pass
class EmbeddedServer(GenericServer):
    def __init__(self):
        super().__init__()
        #TODO
        pass
    def send(self):
        #TODO
        pass
    def recv(self):
        #TODO
        pass
class RemoteServer(GenericServer):
    def send(self, label, test):
        self.metadata["count"]["tests"] += 1
        self.addLabel(test)
        self.addTags(test)
        if self._send(label, test):
            self.sendWaiting()
        else:
            self.waiting.append((label, test))

    def sendWaiting(self):
        while len(self.waiting) > 0:
            prev_test = self.waiting.pop()
            if not self._send(prev_test[0], prev_test[1]):
                self.waiting.append(prev_test[0], prev_test[1])


    def _send(self, label, test):
        to_send = {"metadata": self.metadata,
                   "test_data": test,
                   "state": label}
        try:
            requests.post("http://localhost:5000/submit", json=to_send, timeout=1)
            return True
        except Exception:
            return False

    def addTags(self, test):
        if("tags" in test["id"] and test["id"]["tags"] not in self.tags):
            self.labels.append(test["id"]["label"])
            self.metadata["count"]["tags"] = len(self.tags)

    def addLabel(self, test):
        if("label" in test["id"] and test["id"]["label"] not in self.labels):
            self.labels.append(test["id"]["label"])
            self.metadata["count"]["labels"] = len(self.labels)
    
    def recv(self):
        return requests.get("http://localhost:5000/submit")
    def __init__(self):
        super().__init__()
        #TODO
        pass
