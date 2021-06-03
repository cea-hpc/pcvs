from flask import Flask, request, render_template
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
        #TODO
        pass
    def send(self, data):
        #TODO
        pass
    def recv(self):
        #TODO
        pass
class EmbeddedServer(GenericServer):
    def __init__(self):
        #TODO
        pass
    def send(self):
        #TODO
        pass
    def recv(self):
        #TODO
        pass
class RemoteServer(GenericServer):
    def send(self, data=None, json=None):
        try:
            requests.post("http://localhost:5000/submit", json=json, data=data, timeout=1)
            return True
        except Exception:
            return False
    
    def recv(self):
        return requests.get("http://localhost:5000/submit")
    def __init__(self):
        #TODO
        pass