# tvhProxy
A small flask app to proxy requests between Plex Media Server and Tvheadend.

#### tvhProxy configuration
1. In tvhProxy.py configure options as per your setup.
2. Create a virtual enviroment: ```$ virtualenv venv```
3. Activate the virtual enviroment: ```$ . venv/bin/activate```
4. Install the requirements: ```$ pip install -r requirements.txt```
5. Finally run the app with: ```$ python tvhProxy.py```

#### systemd service configuration
A startup script for Ubuntu can be found in tvhProxy.service (change paths in tvhProxy.service to your setup), install with:

    $ sudo cp tvhProxy.service /etc/systemd/system/tvhProxy.service
    $ sudo systemctl daemon-reload
    $ sudo systemctl enable tvhProxy.service
    $ sudo systemctl start tvhProxy.service

#### Plex configuration
Enter the IP of the host running tvhProxy including port 5004, eg.: ```192.168.1.50:5004```

#### How to run tvhProxyControl
The full instructions of how to run this python script is not available yet. For now it is recommend to run
it with docker and set the following environment variables:
* *TVHPROXY_IP_ADDRESS* - the IP address of the tvhProxy, you can run with --net=host option if port 80 and 5004, 65001 is available on the host or create a macvlan docker network and give the container its own IP.
* *TVHPROXY_TVHEADEND_URL* - the full url to tvheadend for example
* *TVHPROXY_IGNORE_IP_ADDRESSES* - the IP address of Tvheadend, Tvheadend crashes when it discovers the tvhProxy via udp.