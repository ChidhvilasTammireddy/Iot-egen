
""" This Python script helps making a connection to GCP IoT core via MQTT protocol.
Used JWT for device authentication. Post connection the device publishes 100 messages 
to the topic created at rate of 1 msg/sec and then stops. 
"""

import argparse
import datetime
import os
import time

import jwt
import paho.mqtt.client as mqtt

import random

def create_jwt(project_id, private_key_file, algorithm):
    """ This function creates a JWT to make a MQTT connection with GCP. 
    It takes in following
    Args:
        project_id: The project we're developing the data pipeline.
        private_key_file: path to 'RS256' private key.
        algorithm: The encryption algorithm to use (in our case 'RS256')
    Returns:
        This function returns an MQTT generated from the given project_id and private_key,
        whose expiration is set to 20 mins and past that the client will be disconnected.
        And a new JWT will be generated.
    """

    token = {
            # Token issue time
            'iat': datetime.datetime.utcnow(),
            # Token expiration time
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
            # Audience field is set to the project_id
            'aud': project_id
    }

    # Read the private key file.
    with open(private_key_file, 'r') as f:
        private_key = f.read()

    print('Creating JWT using {} from private key file {}'.format(
            algorithm, private_key_file))

    return jwt.encode(token, private_key, algorithm=algorithm)


def error_str(rc):
    """Convert a Paho error to a human readable string."""
    return '{}: {}'.format(rc, mqtt.error_string(rc))


def on_connect(unused_client, unused_userdata, unused_flags, rc):
    """Callback for when a device connects."""
    print('on_connect', error_str(rc))


def on_disconnect(unused_client, unused_userdata, rc):
    """Paho callback for when a device disconnects."""
    print('on_disconnect', error_str(rc))


def on_publish(unused_client, unused_userdata, unused_mid):
    """Paho callback when a message is sent to the broker."""
    print('on_publish')


def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=(
            'Example Google Cloud IoT Core MQTT device connection code.'))
    parser.add_argument(
            '--project_id',
            default=os.environ.get('GOOGLE_CLOUD_PROJECT'),
            help='GCP cloud project name')
    parser.add_argument(
            '--registry_id', required=True, help='Cloud IoT Core registry id')
    parser.add_argument(
            '--device_id', required=True, help='Cloud IoT Core device id')
    parser.add_argument(
            '--private_key_file',
            required=True, help='Path to private key file.')
    parser.add_argument(
            '--algorithm',
            choices=('RS256', 'ES256'),
            required=True,
            help='Which encryption algorithm to use to generate the JWT.')
    parser.add_argument(
            '--cloud_region', default='us-central1', help='GCP cloud region')
    parser.add_argument(
            '--ca_certs',
            default='roots.pem',
            help=('CA root from https://pki.google.com/roots.pem'))
    parser.add_argument(
            '--num_messages',
            type=int,
            default=100,
            help='Number of messages to publish.')
    parser.add_argument(
            '--message_type',
            choices=('event', 'state'),
            default='event',
            required=True,
            help=('Indicates whether the message to be published is a '
                  'telemetry event or a device state message.'))
    parser.add_argument(
            '--mqtt_bridge_hostname',
            default='mqtt.googleapis.com',
            help='MQTT bridge hostname.')
    parser.add_argument(
            '--mqtt_bridge_port',
            default=8883,
            type=int,
            help='MQTT bridge port.')

    return parser.parse_args()


def main():
    args = parse_command_line_args()

    # Create our MQTT client. The client_id is a unique string that identifies
    # this device.
    client = mqtt.Client(
            client_id=('projects/{}/locations/{}/registries/{}/devices/{}'
                       .format(
                               args.project_id,
                               args.cloud_region,
                               args.registry_id,
                               args.device_id)))

    # With Google Cloud IoT Core, the username field is ignored, and the
    # password field is used to transmit a JWT to authorize the device.
    client.username_pw_set(
            username='unused',
            password=create_jwt(
                    args.project_id, args.private_key_file, args.algorithm))

    # Enable SSL/TLS support.
    client.tls_set(ca_certs=args.ca_certs)

    # Register message callbacks. https://eclipse.org/paho/clients/python/docs/
    # describes additional callbacks that Paho supports. In this example, the
    # callbacks just print to standard out.
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    # Connect to the Google MQTT bridge.
    client.connect(args.mqtt_bridge_hostname, args.mqtt_bridge_port)

    # Start the network loop.
    client.loop_start()

    # Publish to the events or state topic based on the flag.
    sub_topic = 'events' if args.message_type == 'event' else 'state'

    mqtt_topic = '/devices/{}/{}'.format(args.device_id, sub_topic)

    random.seed(args.device_id)  # A given device ID will always generate
                                 # the same random data

    simulated_temp = 10 + random.random() * 20

    if random.random() > 0.5:
        temperature_trend = +1     # temps will slowly rise
    else:
        temperature_trend = -1     # temps will slowly fall

    # Publish num_messages mesages to the MQTT bridge once per second.
    for i in range(1, args.num_messages + 1):

        simulated_temp = simulated_temp + temperature_trend * random.normalvariate(0.01,0.005)
        payload = '{}/{}-payload-{:.2f}'.format(
                args.registry_id, args.device_id, simulated_temp)
        print('Publishing message {}/{}: \'{}\''.format(
                i, args.num_messages, payload))
        # Publish "payload" to the MQTT topic. qos=1 means at least once
        # delivery. Cloud IoT Core also supports qos=0 for at most once
        # delivery.
        client.publish(mqtt_topic, payload, qos=1)

        # Send events every second. State should not be updated as often
        time.sleep(1 if args.message_type == 'event' else 5)

    # End the network loop and finish.
    client.loop_stop()
    print('Finished.')


if __name__ == '__main__':
    main()
