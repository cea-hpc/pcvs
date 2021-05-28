from flask import Flask, request, render_template
import requests

CommManager = None

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
        return requests.post("http://localhost:5000/submit", json=json, data=data)
    
    def recv(self):
        return requests.get("http://localhost:5000/submit")
    def __init__(self):
        #TODO
        pass