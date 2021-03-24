from hcloud import Client

import hcloud_automation
import config

client = Client(token=config.API_TOKEN, poll_interval=config.HCLOUD_POOL_INTERVAL)

hcloud_automation.delete_all_snapshots_for_token(
    client,
    snapshot_token=config.IMAGE_TOKEN,
    keep_snapshots=None)
