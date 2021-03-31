from hcloud.actions.domain import ActionFailedException, ActionTimeoutException
from hcloud.images.domain import Image
from hcloud import Client
import config
import logging

logging.basicConfig(filename='error.log',
                    level=logging.DEBUG,
                    format='[%(filename)s:%(lineno)s - %(funcName)20s() ] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Application")

API_TOKEN = config.API_TOKEN
IMAGE_TOKEN = config.IMAGE_TOKEN


def create_snapshot_for_first_server(client: Client, snapshot_token: str = IMAGE_TOKEN) -> tuple:
    """Creates a snapshot for the first server

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: bool: success state / int: id of created image, None in case of error
    :rtype: tuple
    """
    try:
        response_server = client.servers.get_all(label_selector="token=" + snapshot_token)

        if len(response_server) >= 1:
            server = response_server[0]
        else:
            raise Exception("No Server found")

        # get all labels from the server 
        server_labels = server.labels
        # override the labels if neccessary, to match last production state
        server_labels.update(
            token=snapshot_token,
            server_name=server.name,
            server_type=server.server_type.name
        )

        if "server_location" not in server_labels:
            server_labels.update(
                server_location=server.datacenter.location.name
            )

        response = server.create_image(
            description="creation was automated for token " + snapshot_token,
            type="snapshot",
            labels=server_labels)

        # response is BoundAction, we also need image.id - lets find
        image_id = response.image.id

        try:
            client.actions.get_by_id(response.action.id).wait_until_finished(max_retries=300)
            logger.info("Snapshot for server '" + server.name + "' and token '" + snapshot_token + "' created.")
            return True, image_id

        except (ActionFailedException, ActionTimeoutException):
            logger.error("Snapshot for server '" + server.name + "' and token '" + snapshot_token + "' failed.")
            return False, None
    except:
        return False, None


def delete_all_snapshots_for_token(client: Client, snapshot_token: str = IMAGE_TOKEN,
                                   keep_snapshots: list = []) -> bool:
    """Delete all snapshots for the given snapshot_token, except all the snapshot_ids in keep_snapshot

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :param keep_snapshots: list of snapshot.ids which should not be deleted
    :type keep_snapshots: list
    :return: False in case of any error, otherwise True
    :rtype: bool
    """
    try:
        response = client.images.get_all(type="snapshot", label_selector="token=" + snapshot_token)
        for resp in response:
            # snapshot.token        in description
            # snapshot.id           not in keep_snapshots
            # snapshot.protection   not True

            if snapshot_token not in resp.description or resp.protection['delete']:
                continue
            if keep_snapshots is None:
                client.images.delete(Image(resp.id))
            elif resp.id not in keep_snapshots:
                client.images.delete(Image(resp.id))
        logger.info("delete all snapshots for token success")
        return True
    except:
        logger.error("delete all snapshots for token not possible")
        return False


def first_server_power_off(client: Client, snapshot_token: str = IMAGE_TOKEN) -> bool:
    """Shutdown the first server for the given snapshot_token

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: False in case of any error, otherwise True
    :rtype: bool
    """
    try:
        server = client.servers.get_all(label_selector="token=" + snapshot_token)[0]

        if server.status != "off":
            try:
                server.shutdown().wait_until_finished(max_retries=300)
            except (ActionFailedException, ActionTimeoutException):
                return False
        return True
    except:
        return False


def first_server_power_on(client: Client, snapshot_token: str = IMAGE_TOKEN) -> bool:
    """Power on the first server for the given snapshot_token

    :param client: instance of hcloud.client() :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: False in case of any error, otherwise True
    :rtype: bool
    """
    try:
        server = client.servers.get_all(label_selector="token=" + snapshot_token)[0]

        if server.status != "running":
            try:
                server.power_on().wait_until_finished(max_retries=300)
                return True

            except (ActionFailedException, ActionTimeoutException):
                return False
    except:
        return False


def delete_first_server(client: Client, snapshot_token: str = IMAGE_TOKEN) -> object:
    """Delete the first server found for given snapshot_token

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: False in case of any error, otherwise True
    :rtype: bool
    """
    try:
        # get first server
        response = client.servers.get_all(label_selector="token=" + snapshot_token)

        if len(response) > 0:
            server = response[0]
        # if no server left, everything is fine
        else:
            logger.info("delete_first_server no server left. done")
            return True
        client.servers.delete(server)
        logger.info("delete_first_server success")
        return True
    except (ActionFailedException, ActionTimeoutException):
        logger.critical("Exception during server deletion: Action Failed or Action Timeout")
        return False


def create_server_from_snapshot(client: Client, snapshot_token=IMAGE_TOKEN) -> bool:
    """Create a new server from first found snapshot for given snapshot_token

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: False in case of any error, otherwise True
    :raise: Error if no snapshot image found
    :rtype: bool
    """
    # grab image for server from first youngest snapshot
    response_image = client.images.get_all(type="snapshot",
                                           label_selector="token=" + snapshot_token,
                                           sort="created:desc")
    # grab floating ip
    response_floating_ip = client.floating_ips.get_all(label_selector="token=" + snapshot_token)
    # grab ssh_keys
    response_ssh_keys = client.ssh_keys.get_all(label_selector="token=" + snapshot_token)

    # No Image -> Cry
    if len(response_image) < 1:
        logger.critical("No Snapshot-Image for token " + snapshot_token)
        raise ("ERROR: No Snapshot-Image for token " + snapshot_token)
    # at least 1 Snapshot -> use first
    else:
        image = response_image[0]

    ssh_keys = None
    if len(response_ssh_keys) >= 1:
        ssh_keys = response_ssh_keys

    logger.info("Creating Server...")
    logger.info("Use :                 " + image.description)
    logger.info("Use server_name:      " + image.labels['server_name'])
    logger.info("Use server_type:      " + image.labels['server_type'])  # ccx31
    logger.info("Use server_location:  " + image.labels['server_location'])  # nbg1
    logger.info("Use ssh-keys:         ")

    user_data = "#cloud-config\nruncmd:\n- [touch, /root/POWER_ON]\n"

    try:
        response = client.servers.create(
            name=image.labels['server_name'],
            server_type=client.server_types.get_by_name(image.labels['server_type']),
            image=client.images.get_by_id(image.id),
            user_data=user_data,
            location=client.locations.get_by_name(image.labels['server_location']),
            start_after_create=True,
            ssh_keys=ssh_keys,
            labels=image.labels)

        # wait until server complete
        client.actions.get_by_id(response.action.id).wait_until_finished(max_retries=300)
        logger.info("Server '" + image.labels['server_name'] + "' for token '" + snapshot_token + "' created - Type is " + image.labels['server_type'])

    except (ActionFailedException, ActionTimeoutException) as e:
        logger.critical("Exception during server creation: Action Failed or Action Timeout")
        return False

    try:
        # assign floating ip
        if len(response_floating_ip) >= 1:
            floating_ip = response_floating_ip[0]
            logger.info("client.floating_ips.assign " +
                        floating_ip.ip +
                        " - " +
                        str(client.floating_ips.assign(floating_ip, response.server).wait_until_finished(max_retries=300)))
        return True

    except (ActionFailedException, ActionTimeoutException) as e:
        logger.critical("Exception during assigning floating ip: Action Failed or Action Timeout")
        return False


def first_server_assign_floating_ip(client: Client, snapshot_token=IMAGE_TOKEN) -> bool:
    """Assig floating ip for first found server for given snapshot_token

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: False in case of any error, otherwise True
    :raise: Error if no snapshot image found
    :rtype: bool
    """
    # grab image for server from first youngest snapshot
    response_image = client.images.get_all(type="snapshot",
                                           label_selector="token=" + snapshot_token,
                                           sort="created:desc")
    # grab floating ip
    response_floating_ip = client.floating_ips.get_all(label_selector="token=" + snapshot_token)

    server = client.servers.get_all(label_selector="token=" + snapshot_token)[0]
    # assign floating ip
    if len(response_floating_ip) >= 1:
        floating_ip = response_floating_ip[0]
        logger.info("client.floating_ips.assign " +
                    floating_ip.ip +
                    " - " +
                    str(client.floating_ips.assign(floating_ip, server).wait_until_finished(max_retries=300)))
    return True


def first_server_is_running_or_starting(client: Client, snapshot_token=IMAGE_TOKEN) -> bool:
    """Check if first found server for given snapshot_token is either starting or running

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: True if server is running or starting, otherwise False
    :raise: Error if no snapshot image found
    :rtype: bool
    """
    server_status = ["initializing", "starting", "running"]
    response_server = client.servers.get_all(label_selector="token=" + snapshot_token, status=server_status)

    if len(response_server) >= 1:
        return True
    else:
        return False

def destroy_first_server(client: Client, snapshot_token=IMAGE_TOKEN) -> bool:
    """Power off first server, create a snapshot, cleanup unused snapshots and lastly delete your server

    :param client: instance of hcloud.client()
    :type client: hcloud.Client()
    :param snapshot_token: unique token
    which identify all your resources. this is mainly because one project can contain multiple servers and resources
    at once
    :type snapshot_token: str
    :return: True on Success
    :raise: Error in case of any error
    :rtype: bool
    """
    try:
        if first_server_power_off(client, snapshot_token=snapshot_token):

            snapshot_created, image_id = create_snapshot_for_first_server(client, snapshot_token=snapshot_token)

            if snapshot_created:
                keep_snapshots = [image_id]

                delete_all_snapshots_for_token(client, snapshot_token=snapshot_token, keep_snapshots=keep_snapshots)

                delete_first_server(client, snapshot_token=snapshot_token)

        logger.info("Server destroyed")
        return True
    except:
        logger.error("Something went wrong during destroying server")
        raise Exception("Something went wrong during destroying server")