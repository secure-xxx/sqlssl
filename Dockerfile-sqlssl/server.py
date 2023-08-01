#!/usr/bin/env python

import sys, socket, _thread, ssl
from select import select

HOST = '0.0.0.0'
PORT = 3306
BUFSIZE = 4096

def wrap_sockets(client_sock, server_sock, cafile):
  return (ssl.wrap_socket(client_sock,
              server_side=True,
              suppress_ragged_eofs=True,
              cafile=cafile),
          ssl.wrap_socket(
              server_sock,
              suppress_ragged_eofs=True))


def do_relay(client_sock, server_sock, cafile):
  print('PROXYING')
  while True:
    try:
      # Peek for the beginnings of an ssl handshake
      try:
        maybe_handshake = client_sock.recv(
            BUFSIZE, socket.MSG_PEEK | socket.MSG_DONTWAIT)
        if maybe_handshake.startswith('\x16\x03'):
          print('Wrapping sockets.')
          client_sock, server_sock = wrap_sockets(client_sock,
              server_sock, cafile)
      except:
        pass
      receiving, _, _ = select([client_sock, server_sock], [], [])
      if client_sock in receiving:
        p = client_sock.recv(BUFSIZE)
        server_sock.send(p)
        if len(p) != 0:
          print("QUERY CLIENT ---> DB", len(p), str(p))

      if server_sock in receiving:
        p = server_sock.recv(BUFSIZE)
        client_sock.send(p)
        if len(p) != 0:
          print("QUERY DB ---> CLIENT", len(p), str(p))
    except socket.error as e:
      if "timed out" not in str(e):
        raise e


# Relay information, peeking at the data on every read for an SSL
# handshake header. Assume that the _client_ initiates the
# handshaking, so it's safe to just peek at the client's packets.
#
# When the client initiates a handshake, assume that the server has no
# data left to send. (This assumption works for XMPP starttls but
# probably not for other protocols.)
def child(clientsock,target,cafile):
  targetsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  targetsock.connect((target,PORT))

  do_relay(clientsock, targetsock, cafile)

if __name__=='__main__': 
  if len(sys.argv) < 2:
    sys.exit('Usage: %s TARGETHOST <cafile>\n' % sys.argv[0])
  target = sys.argv[1]
  cafile = sys.argv[2]
  myserver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  myserver.bind((HOST, PORT))
  myserver.listen(2)
  print('LISTENER START ON', PORT)
  while True:
    client, addr = myserver.accept()
    print('CLIENT CONNECT FROM:', addr)
    _thread.start_new_thread(child, (client,target,cafile))