/* MAPPING_MODE_ENABLED: false */
/* {"version":1,"sourceType":"raw","mappings":[{"from":"","to":"externalId","asType":"STRING"},{"from":"","to":"_type","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"},{"from":"","to":"aliases","asType":"ARRAY<STRING>"},{"from":"","to":"name","asType":"STRING"},{"from":"","to":"source","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"},{"from":"","to":"path","asType":"ARRAY<STRUCT<`space`:STRING, `externalId`:STRING>>"},{"from":"","to":"root","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"},{"from":"","to":"assetClass","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"},{"from":"","to":"sourceUpdatedUser","asType":"STRING"},{"from":"","to":"pathLastUpdatedTime","asType":"TIMESTAMP"},{"from":"","to":"sourceUpdatedTime","asType":"TIMESTAMP"},{"from":"","to":"type","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"},{"from":"","to":"sourceCreatedUser","asType":"STRING"},{"from":"","to":"parent","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"},{"from":"","to":"description","asType":"STRING"},{"from":"","to":"tags","asType":"ARRAY<STRING>"},{"from":"","to":"sourceCreatedTime","asType":"TIMESTAMP"},{"from":"","to":"sourceContext","asType":"STRING"},{"from":"","to":"sourceId","asType":"STRING"},{"from":"","to":"object3D","asType":"STRUCT<`space`:STRING, `externalId`:STRING>"}]} */select
  `external_id` as externalId,
  `name` as name,
  `description` as description,
  if(
      `parent_external_id` == ''
      OR `parent_external_id` == null,
      null,
      node_reference('icapi_dm_space', `parent_external_id`)
  ) as parent
  from
  `ice-cream-factory-db`.`assets`