from gevent import monkey

monkey.patch_all()

import argparse  # noqa: E402
import time  # noqa: E402
import os  # noqa: E402
import requests  # noqa: E402
from gevent.pywsgi import WSGIServer  # noqa: E402
from flask import Flask, Response, request, \
    jsonify, abort, render_template  # noqa: E402
from operator import itemgetter  # noqa: E402

app = Flask(__name__)

# URL format: <protocol>://<username>:<password>@<hostname>:<port>,
# example: https://test:1234@localhost:9981
config = {
    'tvhproxyIpAddress':   str(os.getenv('TVHPROXY_IP_ADDRESS',
                               '127.0.0.1')),
    'friendlyName':        str(os.getenv('TVHPROXY_FRIENDLY_NAME',
                               'HDHR Emulator')),
    'modelNumber':         str(os.getenv('TVHPROXY_MODEL_NUMBER',
                               'HDTC-2US')),
    'manufacturer':        str(os.getenv('TVHPROXY_MANUFACTURER',
                               'Silicondust')),
    'firmwareName':        str(os.getenv('TVHPROXY_FIRMWARE_NAME',
                               'hdhomeruntc_atsc')),
    'firmwareVersion':     str(os.getenv('TVHPROXY_FIRMWARE_VERSION',
                               '20150826')),
    'deviceId':            str(os.getenv('TVHPROXY_DEVICE_ID',
                               '12345678')),
    'deviceAuth':          str(os.getenv('TVHPROXY_DEVICE_AUTH',
                               'test1234')),
    'tvheadendUrl':        str(os.getenv('TVHPROXY_TVHEADEND_URL',
                               'http://127.0.0.1:9981')),
    'directStream':        str(os.getenv('TVHPROXY_DIRECT_STREAM',
                               'YES')).upper(),
    # specifiy a stream profile that you want to use for adhoc
    # transcoding in tvh, e.g. mp4
    'streamProfile':       str(os.getenv('TVHPROXY_TVHEADEND_PROFILE',
                               'pass')),
    # number of tuners in tvheadend
    'tunerCount':          int(os.getenv('TVHPROXY_TUNER_COUNT',
                               4)),
    # subscription priority
    'subscriptionWeight':  int(os.getenv('TVHPROXY_SUBSCRIPTION_WEIGHT',
                               300)),
    'chunkSize':           int(os.getenv('TVHPROXY_CHUNK_SIZE',
                               1024 * 1024)),
    'sortChannelsByField': str(os.getenv('TVHPROXY_SORT_CHANNELS_BY_FIELD',
                               'NONE')),
    'sortChannelsOrder':   str(os.getenv('TVHPROXY_SORT_CHANNELS_ORDER',
                               'ASC'))
}
config['tvhproxyUrl'] = 'http://' + config['tvhproxyIpAddress'] + ':80'

discoverData = {
    'FriendlyName':    config['friendlyName'],
    'ModelNumber':     config['modelNumber'],
    'FirmwareName':    config['firmwareName'],
    'TunerCount':      config['tunerCount'],
    'FirmwareVersion': config['firmwareVersion'],
    'DeviceID':        config['deviceId'],
    'DeviceAuth':      config['deviceAuth'],
    'BaseURL':         config['tvhproxyUrl'],
    'LineupURL':       '%s/lineup.json' % config['tvhproxyUrl']
}
logPrefix = 'HTTP Server - '


@app.route('/')
@app.route('/discover.json')
def discover():
    return jsonify(discoverData)


@app.route('/')
@app.route('/device.xml')
def device():
    return render_template('device.xml', data=discoverData), \
        {'Content-Type': 'application/xml'}


@app.route('/lineup_status.json')
def status():
    return jsonify({
        'ScanInProgress': 0,
        'ScanPossible':   1,
        'Source':         'Cable',
        'SourceList':     ['Cable']
    })


@app.route('/lineup.json')
def lineup():
    lineup = []
    for tvheadendChannel in _get_tvheadend_channels():
        if tvheadendChannel['enabled']:
            if config['directStream'] == 'YES':
                url = '%s/stream/channel/%s?profile=%s&weight=%s' % \
                    (config['tvheadendUrl'], tvheadendChannel['uuid'],
                     config['streamProfile'], config['subscriptionWeight'])
            else:
                url = '%s/auto/v%s' % (config['tvhproxyUrl'],
                                       tvheadendChannel['number'])

            lineup.append({'GuideNumber': str(tvheadendChannel['number']),
                           'GuideName':   tvheadendChannel['name'],
                           'URL':         url
                           })

    return jsonify(lineup)


@app.route('/lineup.post')
def lineup_post():
    return ''


@app.route('/auto/<channel>')
@app.route('/tuner0/<channel>')
@app.route('/tuner1/<channel>')
@app.route('/tuner2/<channel>')
@app.route('/tuner3/<channel>')
def stream(channel):
    print(logPrefix + 'Request received at ' + channel)
    url = ''
    channel = channel.replace('v', '')
    duration = request.args.get('duration', default=0, type=int)

    if not duration == 0:
        duration += time.time()

    for tvheadendChannel in _get_tvheadend_channels():
        if str(tvheadendChannel['number']) == channel:
            url = '%s/stream/channel/%s?profile=%s&weight=%s' % \
                (config['tvheadendUrl'], tvheadendChannel['uuid'],
                 config['streamProfile'], config['subscriptionWeight'])

    if not url:
        abort(404)
    else:
        tvheadendRequest = requests.get(url, stream=True)

        def generate():
            yield ''
            for chunk in tvheadendRequest.iter_content(
                    chunk_size=config['chunkSize']):
                if not duration == 0 and not time.time() < duration:
                    tvheadendRequest.close()
                    break
                yield chunk

        return Response(generate(), content_type=tvheadendRequest.
                        headers['content-type'],
                        direct_passthrough=True)


@app.route('/<path:path>')
def path_undefined(path):
    print(logPrefix + 'Path undefined: %s' % path)
    abort(404)


def _get_tvheadend_channels():
    url = '%s/api/channel/grid?start=0&limit=999999' % config['tvheadendUrl']

    try:
        response = requests.get(url)
        tvheadendChannels = response.json()['entries']
        if config['sortChannelsOrder'] == 'DESC':
            reverseOrder = True
        else:
            reverseOrder = False

        if config['sortChannelsByField'] != 'NONE':
            tvheadendChannels = sorted(tvheadendChannels,
                                       key=itemgetter(config[
                                                      'sortChannelsByField']),
                                       reverse=reverseOrder)

        return tvheadendChannels

    except Exception as e:
        print(logPrefix + 'An error occured: ' + repr(e))


parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=5004)
parser.add_argument('--verbose', type=int, default=0)
args = parser.parse_args()

if __name__ == '__main__':
    http = WSGIServer(('', args.port), app.wsgi_app)
    http.serve_forever()
