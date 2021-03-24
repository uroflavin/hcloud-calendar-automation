from hcloud import Client 

import hcloud_automation
import config

client = Client(token=config.API_TOKEN, poll_interval=config.HCLOUD_POOL_INTERVAL)

hcloud_automation.destroy_first_server(client, snapshot_token=config.IMAGE_TOKEN)