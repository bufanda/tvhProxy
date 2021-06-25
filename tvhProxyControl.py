import StringIO
import argparse
import os
import socket
import struct

import crc32c

HDHOMERUN_DISCOVER_UDP_PORT = 65001
HDHOMERUN_CONTROL_TCP_PORT = 65001
HDHOMERUN_MAX_PACKET_SIZE = 1460
HDHOMERUN_MAX_PAYLOAD_SIZE = 1452

HDHOMERUN_TYPE_DISCOVER_REQ = 0x0002
HDHOMERUN_TYPE_DISCOVER_RPY = 0x0003
HDHOMERUN_TYPE_GETSET_REQ = 0x0004
HDHOMERUN_TYPE_GETSET_RPY = 0x0005
HDHOMERUN_TAG_DEVICE_TYPE = 0x01
HDHOMERUN_TAG_DEVICE_ID = 0x02
HDHOMERUN_TAG_GETSET_NAME = 0x03
HDHOMERUN_TAG_GETSET_VALUE = 0x04
HDHOMERUN_TAG_GETSET_LOCKKEY = 0x15
HDHOMERUN_TAG_ERROR_MESSAGE = 0x05
HDHOMERUN_TAG_TUNER_COUNT = 0x10
HDHOMERUN_TAG_DEVICE_AUTH_BIN = 0x29
HDHOMERUN_TAG_BASE_URL = 0x2A
HDHOMERUN_TAG_DEVICE_AUTH_STR = 0x2B

HDHOMERUN_DEVICE_TYPE_WILDCARD = 0xFFFFFFFF
HDHOMERUN_DEVICE_TYPE_TUNER = 0x00000001
HDHOMERUN_DEVICE_ID_WILDCARD = 0xFFFFFFFF

config = {
    'tvhproxyIpAddress': os.getenv('TVHPROXY_IP_ADDRESS',
                                   '127.0.0.1'),
    # a hexadecimal string
    'deviceId':          os.getenv('TVHPROXY_DEVICE_ID',
                                   '12345678'),
    # number of tuners in tvheadend
    'tunerCount':        os.getenv('TVHPROXY_TUNER_COUNT',
                                   4),
    # the tvheadend ip address(es), tvheadend crashes
    # when it discovers the tvhproxy (TODO: Fix this)
    'ignoreIpAddresses': os.getenv('TVHPROXY_IGNORE_IP_ADDRESSES',
                                   '127.0.0.1').split(',')
}
config['tvhproxyUrl'] = 'http://' + config['tvhproxyIpAddress'] + ':80'


def retrieveTypeAndPayload(packet):
    header = packet[:4]
    checksum = packet[-4:]
    payload = packet[4:-4]

    packetType, payloadLength = struct.unpack('>HH', header)
    if payloadLength != len(payload):
        print('Bad packet payload length')
        return False

    if checksum != struct.pack('>I', crc32c.cksum(header + payload)):
        print('Bad checksum')
        return False

    return(packetType, payload)


def createPacket(packetType, payload):
    header = struct.pack('>HH', packetType, len(payload))
    data = header + payload
    checksum = crc32c.cksum(data)
    packet = data + struct.pack('>I', checksum)

    return packet


def processPacket(packet, client, logPrefix=''):
    packetType, requestPayload = retrieveTypeAndPayload(packet)

    if packetType == HDHOMERUN_TYPE_DISCOVER_REQ:
        print(logPrefix + 'Discovery request received from ' + client[0])
        # Device Type Filter (tuner)
        responsePayload = struct.pack('>BBI', HDHOMERUN_TAG_DEVICE_TYPE, 0x04,
                                      HDHOMERUN_DEVICE_TYPE_TUNER)
        # Device ID Filter (any)
        responsePayload += struct.pack('>BBI', HDHOMERUN_TAG_DEVICE_ID, 0x04,
                                       int(config['deviceId'], 16))
        # Device ID Filter (any)
        responsePayload += struct.pack('>BB{0}s'.format(len
                                       (config['tvhproxyUrl'])),
                                       HDHOMERUN_TAG_GETSET_NAME,
                                       len(config['tvhproxyUrl']),
                                       config['tvhproxyUrl'])
        # Device ID Filter (any)
        responsePayload += struct.pack('>BBB', HDHOMERUN_TAG_TUNER_COUNT,
                                       0x01, config['tunerCount'])

        return createPacket(HDHOMERUN_TYPE_DISCOVER_RPY, responsePayload)

    # TODO: Implement request types
    if packetType == HDHOMERUN_TYPE_GETSET_REQ:
        print(logPrefix + 'Get set request received from ' + client[0])
        getSetName = None
        getSetValue = None
        payloadIO = StringIO.StringIO(requestPayload)
        while True:
            header = payloadIO.read(2)
            if not header:
                break
            tag, length = struct.unpack('>BB', header)
            # TODO: If the length is larger than 127 the following bit
            # is also needed to determine length
            if length > 127:
                print(logPrefix + 'Unable to determine tag length, the \
                       correct way to determine a length larger than 127 \
                       must still be implemented.')
                return False
            # TODO: Implement other tags
            if tag == HDHOMERUN_TAG_GETSET_NAME:
                getSetName = struct.unpack('>{0}s'.format(length),
                                           payloadIO.read(length))[0]
            if tag == HDHOMERUN_TAG_GETSET_VALUE:
                getSetValue = struct.unpack('>{0}s'.format(length),
                                            payloadIO.read(length))[0]

        if getSetName is None:
            return False
        else:
            responsePayload = struct.pack('>BB{0}s'.format(len(getSetName)),
                                          HDHOMERUN_TAG_GETSET_NAME,
                                          len(getSetName), getSetName)

            if getSetValue is not None:
                responsePayload += struct.pack('>BB{0}s'.format(
                                               len(getSetValue)),
                                               HDHOMERUN_TAG_GETSET_VALUE,
                                               len(getSetValue), getSetValue)

            return createPacket(HDHOMERUN_TYPE_GETSET_RPY, responsePayload)

    return False


def tcpServer():
    logPrefix = 'TCP Server - '
    print(logPrefix + 'Starting tcp server')
    controlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    controlSocket.bind((config['tvhproxyIpAddress'],
                       HDHOMERUN_CONTROL_TCP_PORT))
    controlSocket.listen(1)

    print(logPrefix + 'Listening...')
    try:
        while True:
            connection, client = controlSocket.accept()
            try:
                packet = connection.recv(HDHOMERUN_MAX_PACKET_SIZE)
                if not packet:
                    print(logPrefix + 'No packet received')
                    break
                if client[0] not in config['ignoreIpAddresses']:
                    responsePacket = processPacket(packet, client)
                    if responsePacket:
                        print(logPrefix + 'Sending control reply over tcp')
                        connection.send(responsePacket)
                    else:
                        print(logPrefix + 'No known control request received, \
                               nothing to send to client')
                elif args.verbose > 1:
                    print(logPrefix + 'Ignoring tcp client %s' % client[0])
            finally:
                connection.close()
    except Exception as e:
        print(logPrefix + 'Exception occured ' + repr(e))

    print(logPrefix + 'Stopping server')
    controlSocket.close()


def udpServer():
    logPrefix = 'UDP Server - '
    print(logPrefix + 'Starting udp server')
    discoverySocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discoverySocket.bind(('0.0.0.0', HDHOMERUN_DISCOVER_UDP_PORT))
    print(logPrefix + 'Listening...')
    while True:
        packet, client = discoverySocket.recvfrom(HDHOMERUN_MAX_PACKET_SIZE)
        if not packet:
            print(logPrefix + 'No packet received')
            break
        if client[0] not in config['ignoreIpAddresses']:
            responsePacket = processPacket(packet, client)
            if responsePacket:
                print(logPrefix + 'Sending discovery reply over udp')
                discoverySocket.sendto(responsePacket, client)
            else:
                print(logPrefix + 'No discovery request received, \
                       nothing to send to client')
        elif args.verbose > 1:
            print(logPrefix + 'Ignoring udp client %s' % client[0])

    discoverySocket.close()


parser = argparse.ArgumentParser()
parser.add_argument('--port_type')
parser.add_argument('--verbose', type=int, default=0)
args = parser.parse_args()

if __name__ == '__main__':
    try:
        if args.port_type == 'tcp':
            tcpServer()
        else:
            udpServer()
    except KeyboardInterrupt:
        exit(0)
