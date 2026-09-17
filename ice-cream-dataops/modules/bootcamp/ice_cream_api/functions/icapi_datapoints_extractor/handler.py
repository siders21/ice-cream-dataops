from datetime import datetime, timedelta, timezone
from itertools import islice
from timeit import default_timer

from cognite.client import CogniteClient
from cognite.client.data_classes import ExtractionPipelineRun
from cognite.client.data_classes.data_modeling import NodeId, ViewId
from cognite.client.data_classes.data_modeling.cdm.v1 import CogniteAsset, CogniteTimeSeries
from cognite.client.data_classes.filters import ContainsAny, Equals

from ice_cream_factory_api import IceCreamFactoryAPI

from cognite.client.config import global_config
global_config.disable_pypi_version_check = True

from itertools import islice


def batcher(iterable, batch_size):
    iterator = iter(iterable)
    while batch := list(islice(iterator, batch_size)):
        yield batch


def get_time_series_for_site(client: CogniteClient, site):
    this_site = site.strip().lower()

    sub_tree_root = client.data_modeling.instances.retrieve_nodes(
        NodeId("icapi_dm_space", this_site),
        node_cls=CogniteAsset,
    )

    if not sub_tree_root:
        print(
            f"----No CogniteAssets in CDF for {site}!----\n"
            f"    Run the 'Create Cognite Asset Hierarchy' "
            f"transformation!"
        )
        return []

    sub_tree_nodes = get_asset_subtree(
        client,
        sub_tree_root,
    )

    print(
        f"ASSETS USED FOR TS SEARCH: "
        f"{len(sub_tree_nodes)} assets for {site}"
    )

    value_list = [
        {
            "space": node.space,
            "externalId": node.external_id,
        }
        for node in sub_tree_nodes
    ]

    time_series_batches = [
        client.data_modeling.instances.search(
            view=ViewId(
                "cdf_cdm",
                "CogniteTimeSeries",
                "v1",
            ),
            instance_type=CogniteTimeSeries,
            filter=ContainsAny(
                property=[
                    "cdf_cdm",
                    "CogniteTimeSeries/v1",
                    "assets",
                ],
                values=batch,
            ),
            limit=None,
        )
        for batch in batcher(value_list, 20)
    ]

    time_series = [
        node
        for batch_result in time_series_batches
        for node in batch_result
    ]

    print(
        f"FOUND {len(time_series)} TIME SERIES "
        f"BEFORE NAME FILTER FOR {site}"
    )

    time_series = [
        item
        for item in time_series
        if any(
            substring in item.external_id
            for substring in ["planned_status", "good"]
        )
    ]

    print(
        f"FOUND {len(time_series)} TARGET TIME SERIES FOR {site}"
    )

    print(
        "TARGET TIME SERIES:",
        [ts.external_id for ts in time_series],
    )

    return time_series

def get_asset_subtree(client: CogniteClient, root: CogniteAsset):
    all_nodes = [root]
    current_level = [root]

    while current_level:
        parent_ids = [
            {
                "space": node.space,
                "externalId": node.external_id,
            }
            for node in current_level
        ]

        next_level = []

        for parent_id in parent_ids:
            children = client.data_modeling.instances.list(
                instance_type=CogniteAsset,
                filter=Equals(
                    property=[
                        "cdf_cdm",
                        "CogniteAsset/v1",
                        "parent",
                    ],
                    value=parent_id,
                ),
                limit=None,
            )

            next_level.extend(children)
            print(f"PCR_Checkpoint")

        if not next_level:
            break

        existing_ids = {
            (node.space, node.external_id)
            for node in all_nodes
        }

        next_level = [
            node
            for node in next_level
            if (node.space, node.external_id) not in existing_ids
        ]

        if not next_level:
            break

        all_nodes.extend(next_level)
        current_level = next_level

    return all_nodes

def report_ext_pipe(client: CogniteClient, status, message=None):
    ext_pipe_run = ExtractionPipelineRun(
        extpipe_external_id="ep_icapi_datapoints",
        status=status,
        message=message
    )

    client.extraction_pipelines.runs.create(run=ext_pipe_run)

def handle(client: CogniteClient = None, data=None):
    report_ext_pipe(client, "seen")
    
    sites = None
    backfill = None
    hours = None
    max_hours = 336

    if data:
        sites = data.get("sites")
        backfill = data.get("backfill")
        hours = data.get("hours")

        if hours and hours > max_hours:
            print(f"{hours} > {max_hours}! The Ice Cream API can't serve more than {max_hours} hours of datapoints, setting hours to max")
            hours = max_hours

    all_sites = [
        "Houston",
        "Oslo",
        "Kuala_Lumpur",
        "Hannover",
        "Nuremberg",
        "Marseille",
        "Sao_Paulo",
        "Chicago",
        "Rotterdam",
        "London",
    ]

    sites = sites or all_sites
    backfill = backfill or True
    hours = hours or max_hours

    now = datetime.now(timezone.utc).timestamp() * 1000
    increment = timedelta(hours=hours).total_seconds() * 1000

    ice_cream_api = IceCreamFactoryAPI(base_url="https://ice-cream-factory.inso-internal.cognite.ai")

    try:
        for site in sites:
            print(f"Getting Data Points for {site}")
            big_start = default_timer()

            time_series = get_time_series_for_site(client, site)

            latest_dps = {
                dp.external_id: dp.timestamp
                for dp in client.time_series.data.retrieve_latest(
                    external_id=[ts.external_id for ts in time_series],
                    ignore_unknown_ids=True
                )
            } if not backfill else None

            to_insert = []
            for ts in time_series:
                # figure out the window of datapoints to pull for this Time Series
                latest = latest_dps[ts.external_id][0] if not backfill and latest_dps.get(ts.external_id) else None

                start = latest if latest else now - increment
                end = now
            
                dps_list = ice_cream_api.get_datapoints(timeseries_ext_id=ts.external_id, start=start, end=end)

                for dp_dict in dps_list:
                    dp_dict["instance_id"] = NodeId(space="icapi_dm_space", external_id=dp_dict["instance_id"])

                to_insert.extend(dps_list)

                if len(to_insert) > 50:
                    client.time_series.data.insert_multiple(datapoints=to_insert)
                    to_insert = []

            if to_insert:
                client.time_series.data.insert_multiple(datapoints=to_insert)
                print(f"  {hours}h of Datapoints took {default_timer() - big_start:.2f} seconds")
            else:
                print(f"  No TimeSeries, for {hours}h of Datapoints took {default_timer() - big_start:.2f} seconds")

        report_ext_pipe(client, "success")
    except Exception as e:
        report_ext_pipe(client, "failure", str(e))
        raise
